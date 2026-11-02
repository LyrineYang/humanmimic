"""Private CUDA evaluation. Never import this module into an estimator worker."""
import math
import torch
from r4_gpu_geometry import mesh_samples, nearest_distance


def quaternion_matrix(q):
    q = q / q.norm()
    w, x, y, z = q.unbind()
    return torch.stack([1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w),
                        2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w),
                        2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]).reshape(3, 3)


def sample_truth(scene, device, generator, count=4096):
    if scene.get("geometry_role") != "evaluation_only" or scene.get("split") not in {"debug", "readiness"}:
        raise ValueError("Private development evaluation geometry required")
    tensor = lambda x: torch.tensor(x, device=device, dtype=torch.float64)
    parts = []
    for spec in scene["collision_parts"]:
        size = tensor(spec["size"])
        position = tensor(spec.get("position", [0, 0, 0]))
        rotation = quaternion_matrix(tensor(spec.get("quaternion", [1, 0, 0, 0])))
        if spec["type"] == "box":
            area = 8*(size[0]*size[1]+size[0]*size[2]+size[1]*size[2])
        elif spec["type"] == "cylinder":
            area = 4*math.pi*size[0]*size[1]+2*math.pi*size[0]**2
        else:
            raise ValueError("Evaluator supports procedural boxes/cylinders only; do not substitute a hull")
        parts.append((spec["type"], size, position, rotation, area))
    areas = torch.stack([part[4] for part in parts])
    samples, outward_normals = [], []
    for kind, size, position, rotation, area in parts:
        n = max(32, int(math.ceil(count*6*float(area/areas.sum()))))
        random = torch.rand((n, 4), device=device, dtype=torch.float64, generator=generator)
        if kind == "box":
            face_weights = torch.stack([size[1]*size[2], size[0]*size[2], size[0]*size[1]])
            axis = torch.multinomial(face_weights, n, replacement=True, generator=generator)
            points = (random[:, :3]*2-1)*size
            normals = torch.zeros_like(points)
            for k in range(3):
                mask = axis == k
                sign = torch.where(random[mask, 3] > .5, torch.ones_like(random[mask, 3]), -torch.ones_like(random[mask, 3]))
                points[mask, k] = sign*size[k]
                normals[mask, k] = sign
        else:
            radius, half_height = size
            side = random[:, 0] < (4*math.pi*radius*half_height)/area
            angle = random[:, 1]*2*math.pi
            radial = torch.where(side, radius, radius*random[:, 2].sqrt())
            z = torch.where(side, (random[:, 2]*2-1)*half_height, torch.where(random[:, 3] > .5, half_height, -half_height))
            points = torch.stack([radial*angle.cos(), radial*angle.sin(), z], -1)
            normals = torch.stack([side*angle.cos(), side*angle.sin(), torch.where(side, 0., z.sign())], -1)
        samples.append(points@rotation.T + position)
        outward_normals.append(normals@rotation.T)
    samples = torch.cat(samples)
    outward_normals = torch.cat(outward_normals)
    def union_distance(points):
        signed = []
        for kind, size, position, rotation, _ in parts:
            local = (points-position)@rotation
            if kind == "box":
                excess = local.abs()-size
            else:
                excess = torch.stack([local[:, :2].norm(dim=-1)-size[0], local[:, 2].abs()-size[1]], -1)
            signed.append(excess.clamp_min(0).norm(dim=-1) + excess.max(-1).values.clamp_max(0))
        return torch.stack(signed).min(0).values
    # min(SDF)==0 also holds on an internal face where primitives exactly meet.
    # A union boundary must expose free space along the source face's outward
    # normal. Several scale-relative offsets avoid stepping across a narrow gap.
    scale = min(float(part[1].min()) for part in parts)
    tolerance = max(scale*1e-10, 1e-13)
    exposed = torch.zeros(len(samples), device=device, dtype=torch.bool)
    for fraction in [1e-4, 1e-6, 1e-8]:
        exposed |= union_distance(samples+outward_normals*(scale*fraction)) > tolerance
    surface = samples[(union_distance(samples) >= -tolerance) & exposed]
    if len(surface) < count:
        raise ValueError("Insufficient exposed union surface samples")
    return surface[torch.randperm(len(surface), device=device, generator=generator)[:count]]


def score_surfaces(estimate, truth):
    pred_distance, truth_distance = nearest_distance(estimate, truth), nearest_distance(truth, estimate)
    result = {"surface_mean_m": float(pred_distance.mean()), "surface_p95_m": float(torch.quantile(pred_distance, .95)),
              "symmetric_chamfer_m": float((pred_distance.mean()+truth_distance.mean())/2)}
    for threshold in [.001, .002, .005]:
        precision, recall = (pred_distance <= threshold).double().mean(), (truth_distance <= threshold).double().mean()
        result[f"fscore_{int(threshold*1000)}mm"] = float(2*precision*recall/(precision+recall).clamp_min(1e-12))
    return result


def evaluate_beliefs(result, prior, scene, actual, device):
    if device.type != "cuda":
        raise RuntimeError("GPU evaluation only")
    generator = torch.Generator(device=device).manual_seed(31701)
    tensor = lambda x: torch.tensor(x, device=device, dtype=torch.float64)
    records = tensor(actual)
    truth_surface = sample_truth(scene, device, generator)
    initial_index = int((records[:, 0]-prior["initial_time_s"]).abs().argmin())
    if abs(float(records[initial_index, 0])-prior["initial_time_s"]) > .0021:
        raise ValueError("Prior/evaluation time mismatch")
    initial_truth = torch.eye(4, device=device, dtype=torch.float64)
    initial_truth[:3, :3] = quaternion_matrix(records[initial_index, 4:8])
    initial_truth[:3, 3] = records[initial_index, 1:4]
    fixed_roi_gauge = torch.linalg.inv(initial_truth)@tensor(prior["T_world_object_initial"])
    valid = [belief for belief in result["beliefs"] if belief["state_updated"]]
    metrics, reference_estimate, reference_truth = [], None, None
    for belief in valid:
        sample = int((records[:, 0]-belief["time_s"]).abs().argmin())
        if abs(float(records[sample, 0])-belief["time_s"]) > .0021:
            raise ValueError("Evaluation state has no synchronized physics sample")
        true_pose = torch.eye(4, device=device, dtype=torch.float64)
        true_pose[:3, :3], true_pose[:3, 3] = quaternion_matrix(records[sample, 4:8]), records[sample, 1:4]
        pose = tensor(belief["T_world_object"][-1])
        if reference_estimate is None:
            reference_estimate, reference_truth = pose.clone(), true_pose.clone()
        vertices = tensor(belief["vertices_object_m"])
        faces = torch.tensor(belief["faces"], device=device, dtype=torch.long)
        surface = mesh_samples(vertices, faces, 4096, generator)
        world_surface = surface@pose[:3, :3].T+pose[:3, 3]
        world_truth = truth_surface@true_pose[:3, :3].T+true_pose[:3, 3]
        relative_estimate = pose@torch.linalg.inv(reference_estimate)
        relative_truth = true_pose@torch.linalg.inv(reference_truth)
        angular = ((torch.trace(relative_estimate[:3, :3]@relative_truth[:3, :3].T)-1)/2).clamp(-1, 1).acos()
        roi = torch.tensor(prior["roi_vertex_indices"], device=device, dtype=torch.long)
        roi_mask = torch.zeros(len(vertices), device=device, dtype=torch.bool)
        roi_mask[roi] = True
        roi_faces = faces[roi_mask[faces].any(-1)]
        roi_surface = mesh_samples(vertices, roi_faces, 2048, generator)@pose[:3, :3].T+pose[:3, 3]
        coarse_roi = tensor(prior["vertices_object_m"])[roi]
        # Freeze ROI correspondence from the shared PRIOR pose gauge; never select
        # ROI using final error, changed vertices, or a successful outcome.
        coarse_roi_true = coarse_roi@fixed_roi_gauge[:3, :3].T+fixed_roi_gauge[:3, 3]
        truth_roi = truth_surface[nearest_distance(truth_surface, coarse_roi_true) <= .015]
        entry = {"time_s": belief["time_s"], "world_surface": score_surfaces(world_surface, world_truth),
            "relative_pose_translation_error_m": float((relative_estimate[:3, 3]-relative_truth[:3, 3]).norm()),
            "relative_pose_angle_error_deg": float(angular*180/math.pi), "roi_vertex_count": len(roi),
            "roi": score_surfaces(roi_surface, truth_roi@true_pose[:3, :3].T+true_pose[:3, 3]) if len(truth_roi) else None,
            "observed_rank": belief["observed_rank"], "active_parameters": belief["active_parameters"],
            "compliance_observable": belief["compliance_observable"], "wall_s": belief["wall_s"], "peak_cuda_bytes": belief["peak_cuda_bytes"]}
        metrics.append(entry)
    return {"status": "awaiting_verification", "evaluation_status": "completed", "metrics": metrics,
            "missing_or_unobservable_outputs": len(result["beliefs"])-len(valid), "all_outputs_denominator": len(result["beliefs"]),
            "heldout_used": False, "sampling": "4096-point CUDA exposed union boundary sampling; outward occupancy excludes internal interfaces; finite-sampling bias remains",
            "pose_convention": "Relative SE3 motion from first estimated output; no claim of an observed canonical CAD pose",
            "compliance_ground_truth": None, "compliance_note": "MuJoCo soft contact is not a known single linear material compliance",
            "operation_accuracy": "Not measured by E1; requires unchanged T1/T2 physical evaluation in E2"}
