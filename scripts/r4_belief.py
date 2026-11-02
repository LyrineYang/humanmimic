"""CUDA-only, bounded sliding-window SE3 / local mesh / compliance inference.

This module accepts public tensors only. It does not import MuJoCo or read files.
Geometry is a normal-displacement mesh with local RBF modes, not a neural SDF.
The implicit surface is a local oriented-surface approximation, valid only near
the coarse mesh. Data information and regularization are reported separately.
"""
from __future__ import annotations

import math
import time
import torch

from r4_public import validate_calibration, validate_frame, validate_prior
from r4_modalities import observation_view


def skew(v):
    zero = torch.zeros_like(v[..., 0])
    x, y, z = v.unbind(-1)
    return torch.stack([zero, -z, y, z, zero, -x, -y, x, zero], -1).reshape(*v.shape[:-1], 3, 3)


def so3(v):
    return torch.matrix_exp(skew(v))


def rotation_vector(r):
    """CUDA SO3 log for fixed initialization; reject the ambiguous pi branch."""
    w = torch.stack([r[2, 1]-r[1, 2], r[0, 2]-r[2, 0], r[1, 0]-r[0, 1]])/2
    sine, cosine = w.norm(), ((torch.trace(r)-1)/2).clamp(-1, 1)
    if sine < 1e-8 and cosine < 0:
        raise ValueError("Ambiguous 180-degree initialization; require an explicit pose branch")
    return w * torch.where(sine < 1e-8, torch.ones_like(sine), torch.atan2(sine, cosine)/sine.clamp_min(1e-12))


def unit(v):
    return v / torch.linalg.vector_norm(v, dim=-1, keepdim=True).clamp_min(1e-12)


class BeliefEstimator:
    def __init__(self, prior, calibration, config, device, modality="VF", ablation="joint"):
        if device.type != "cuda":
            raise RuntimeError("Object belief requires CUDA; CPU execution is disabled")
        if modality not in {"V", "VB", "VF"} or ablation not in {"joint", "pose_only", "shape_only", "rigid_contact"}:
            raise ValueError("Unknown modality/ablation")
        validate_prior(prior)
        validate_calibration(calibration)
        self.device, self.cfg, self.cal = device, config, calibration
        self.modality, self.ablation = modality, ablation
        self.v = self.tensor(prior["vertices_object_m"])
        self.n = self.tensor(prior["normals_object"])
        self.faces = torch.tensor(prior["faces"], device=device, dtype=torch.long)
        self.initial = self.transform(prior["T_world_object_initial"])
        self.initial_c = float(prior["compliance_initial_m_per_n"])
        if not 0 <= self.initial_c < config["maximum_compliance_m_per_n"]:
            raise ValueError("Compliance prior outside configured bounds")
        if self.v.ndim != 2 or self.v.shape[1] != 3 or not 16 <= len(self.v) <= config["maximum_vertices"]:
            raise ValueError("Invalid mesh budget")
        if self.n.shape != self.v.shape or not torch.allclose(self.n.norm(dim=1), torch.ones_like(self.n[:, 0]), atol=1e-4):
            raise ValueError("Require unit mesh normals")
        if self.faces.ndim != 2 or self.faces.shape[1] != 3 or self.faces.min() < 0 or self.faces.max() >= len(self.v):
            raise ValueError("Invalid triangular topology")
        roi = torch.tensor(prior["roi_vertex_indices"], device=device, dtype=torch.long)
        if roi.ndim != 1 or len(roi) < 8 or len(roi.unique()) != len(roi) or roi.min() < 0 or roi.max() >= len(self.v):
            raise ValueError("Invalid declared refinement ROI")
        self.roi = roi
        count = min(config["shape_modes"], len(roi) - 6)
        # Deterministic farthest-point centers; no truth-based ROI or sampling.
        selected = [0]
        distances = ((self.v[roi] - self.v[roi[0]]) ** 2).sum(-1)
        for _ in range(1, count):
            index = int(distances.argmax())
            selected.append(index)
            distances = torch.minimum(distances, ((self.v[roi] - self.v[roi[index]]) ** 2).sum(-1))
        centers = self.v[roi[torch.tensor(selected, device=device)]]
        basis = torch.exp(-torch.cdist(self.v, centers).square() / (2 * config["kernel_radius_m"] ** 2))
        mask = torch.zeros(len(self.v), device=device, dtype=self.v.dtype)
        mask[roi] = 1
        basis *= mask[:, None]
        centered = self.v - self.v.mean(0)
        radius = centered.norm(dim=1).max().clamp_min(.001)
        rigid = torch.cat([self.n, torch.linalg.cross(centered, self.n) / radius], 1) * mask[:, None]
        # Fix the six rigid-motion gauge directions in local normal offsets.
        basis -= rigid @ (torch.linalg.pinv(rigid) @ basis)
        u, singular, _ = torch.linalg.svd(basis, full_matrices=False)
        rank = int((singular > singular.max() * 1e-7).sum())
        if rank < 1:
            raise ValueError("No nonrigid shape modes in selected ROI")
        self.basis = u[:, :rank] / u[:, :rank].abs().amax(0).clamp_min(1e-9)
        self.support = {finger: self.calibrate_surface(pad["triangles_sensor_m"])
                        for finger, pad in calibration["pads"].items()}
        self.previous = None
        self.coarse_prior = prior
        self.independent_pose_estimator = None

    def tensor(self, value):
        result = torch.as_tensor(value, dtype=torch.float64, device=self.device)
        if not torch.isfinite(result).all():
            raise ValueError("Nonfinite public tensor")
        return result

    def transform(self, value):
        transform = self.tensor(value)
        if transform.shape != (4, 4) or not torch.allclose(transform[3], self.tensor([0, 0, 0, 1]), atol=1e-6):
            raise ValueError("Invalid homogeneous transform")
        r = transform[:3, :3]
        if not torch.allclose(r.T @ r, torch.eye(3, device=self.device, dtype=r.dtype), atol=1e-5) or abs(float(torch.linalg.det(r)) - 1) > 1e-5:
            raise ValueError("Transform is not right-handed SE3")
        return transform

    def calibrate_surface(self, triangles):
        """CUDA rays intersect known hand geometry, never the manipulated object.

        3x3 rays per angular bin; spatial support includes spread plus calibration
        margin. Edge bins with missing rays are invalid, not exact contact points.
        Finite sampling is an approximation to calibrate in P1, not ground truth.
        """
        tri = self.tensor(triangles)
        if tri.ndim != 3 or tri.shape[1:] != (3, 3):
            raise ValueError("Invalid calibrated hand triangles")
        width, height = self.cal["size"]
        fov = self.tensor(self.cal["fov_deg"]) * math.pi / 180
        yy, xx = torch.meshgrid(torch.arange(height, device=self.device), torch.arange(width, device=self.device), indexing="ij")
        fractions = self.tensor([[x, y] for y in [.05, .5, .95] for x in [.05, .5, .95]])
        a = ((xx.reshape(-1, 1) + fractions[:, 0]) / width * 2 - 1) * fov[0]
        e = ((yy.reshape(-1, 1) + fractions[:, 1]) / height * 2 - 1) * fov[1]
        rays = torch.stack([e.cos() * a.sin(), e.sin(), -e.cos() * a.cos()], -1).reshape(-1, 3)
        edge1, edge2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
        p = torch.linalg.cross(rays[:, None, :], edge2[None, :, :], dim=-1)
        determinant = (p * edge1).sum(-1)
        inverse = torch.where(determinant.abs() > 1e-10, 1 / determinant, torch.zeros_like(determinant))
        distance_to_origin = -tri[:, 0]
        u = (p * distance_to_origin).sum(-1) * inverse
        q = torch.linalg.cross(distance_to_origin, edge1)
        v = (rays[:, None, :] * q).sum(-1) * inverse
        distance = (edge2 * q).sum(-1)[None, :] * inverse
        valid = (determinant.abs() > 1e-10) & (u >= 0) & (v >= 0) & (u + v <= 1) & (distance > 0)
        distance = torch.where(valid, distance, torch.zeros_like(distance))
        far, triangle_id = distance.max(-1)  # outer envelope of the known hand
        near = torch.where(valid, distance, torch.full_like(distance, torch.inf)).min(-1).values
        near = torch.where(torch.isfinite(near), near, torch.zeros_like(near))
        # A bin can hit several known collision pieces. Include their full depth
        # interval rather than inventing a contact on only the outermost piece.
        near_points = (rays * near[:, None]).reshape(width * height, 9, 3)
        far_points = (rays * far[:, None]).reshape(width * height, 9, 3)
        points = torch.cat([near_points, far_points], 1)
        all_normals = unit(torch.linalg.cross(edge1, edge2))
        normals = all_normals[triangle_id].reshape(width * height, 9, 3)
        centers = (near_points[:, 4] + far_points[:, 4]) / 2
        spread = (points - centers[:, None, :]).norm(dim=-1).max(-1).values
        reference_normal = normals[:, 4].repeat_interleave(9, dim=0)
        normal_compatible = (((all_normals[None, :, :] * reference_normal[:, None, :]).sum(-1) > .5) | ~valid).all(-1).reshape(-1, 9).all(-1)
        # Inflate sampled angular support; no sub-taxel localization claim.
        radius = 1.5 * spread + self.cal["surface_margin_m"]
        return {"points": centers, "normals": normals[:, 4], "radius": radius,
                "valid": (far.reshape(-1, 9) > 0).all(-1) & normal_compatible & (radius <= self.cfg["maximum_support_radius_m"])}

    def prepare(self, frames):
        cfg = self.cfg
        frames = observation_view(frames, self.cal, self.modality, self.device)
        if not 1 <= len(frames) <= cfg["window_frames"]:
            raise ValueError("Invalid sliding window length")
        previous = -1
        for frame in frames:
            validate_frame(frame, previous, tactile_mode="binary" if self.modality == "VB" else "force")
            previous = frame["time_s"]
        times = self.tensor([f["time_s"] for f in frames])
        data = {"times": times, "vision": [], "anchors": [], "contacts": [], "events": [], "force_tracks": {}}
        # Identical visual budget in V/VB/VF; reserve the remaining quarter for
        # tactile rows so adding a modality never silently exceeds 4096 inputs.
        visual_budget = 3 * cfg["maximum_points"] // 4
        points_per_frame = visual_budget // len(frames)
        tactile_per_packet = (cfg["maximum_points"] - visual_budget) // max(1, sum(len(f["tactile"]) for f in frames))
        used_packets, last_health = set(), {}
        for i, frame in enumerate(frames):
            visual = frame["vision"]
            if visual is not None and visual["time_s"] == frame["time_s"]:
                pts, normals = self.tensor(visual["points_world_m"]), self.tensor(visual["normals_world"])
                if pts.numel():
                    if pts.ndim != 2 or pts.shape[1] != 3 or normals.shape != pts.shape:
                        raise ValueError("Invalid visual points/normals")
                    if not torch.allclose(normals.norm(dim=1), torch.ones_like(normals[:, 0]), atol=1e-4):
                        raise ValueError("Visual normals must be unit length")
                    indices = torch.linspace(0, len(pts) - 1, min(points_per_frame, len(pts)), device=self.device).long()
                    data["vision"].append((i, pts[indices], normals[indices], visual["sigma_m"]))
                anchor = visual.get("pose_measurement")
                if anchor:
                    data["anchors"].append((i, self.transform(anchor["T_world_object"]), anchor["translation_sigma_m"], anchor["rotation_sigma_rad"]))
            if self.modality == "V":
                continue
            for packet in frame["tactile"]:
                identity = (packet["sensor_id"], packet["time_s"])
                if identity in used_packets:
                    raise ValueError("Duplicate tactile sample would double-count information")
                used_packets.add(identity)
                event = {"sensor_id": packet["sensor_id"], "time_s": packet["time_s"], "state": "unknown"}
                data["events"].append(event)
                if not packet["valid"] or frame["time_s"] - packet["time_s"] > self.cal["max_age_s"] + 1e-9:
                    event["state"] = "missing_or_stale"
                    last_health.pop(packet["sensor_id"], None)
                    continue
                if packet["time_s"] < frames[0]["time_s"]:
                    event["state"] = "outside_pose_window"
                    continue
                transform = self.transform(packet["T_world_sensor"])
                width, height = self.cal["size"]
                saturated = torch.as_tensor(packet["saturated"], device=self.device, dtype=torch.bool)
                if saturated.shape != (height, width):
                    raise ValueError("Invalid force grid shape")
                saturated = saturated.reshape(-1)
                support = self.support[packet["sensor_id"]]
                if self.modality == "VB":
                    bits = torch.as_tensor(packet["contact_bits"], device=self.device, dtype=torch.bool)
                    if bits.shape != (height, width):
                        raise ValueError("Invalid binary contact grid shape")
                    bits = bits.reshape(-1)
                    compressive = torch.zeros(len(bits), device=self.device, dtype=self.v.dtype)
                    active = bits & support["valid"]
                else:
                    force = self.tensor(packet["force_sensor_n"])
                    if force.shape != (height, width, 3):
                        raise ValueError("Invalid force grid shape")
                    force = force.reshape(-1, 3)
                    bits = force.norm(dim=-1) >= self.cal["threshold_n"]
                    compressive = -(force * support["normals"]).sum(-1)
                    active = bits & support["valid"] & (compressive > 0)
                event["active_taxels"] = int(active.sum())
                event["saturated_taxels"] = int(saturated.sum())
                event["state"] = "contact_candidate" if active.any() else ("no_contact" if not bits.any() else "unlocalized_contact")
                previous_health = last_health.get(packet["sensor_id"])
                event["onset_interval_s"] = ([previous_health[1], packet["time_s"]]
                    if previous_health and previous_health[0] == "no_contact" and event["state"] == "contact_candidate"
                    and packet["time_s"] - previous_health[1] <= self.cal["max_age_s"] else None)
                last_health[packet["sensor_id"]] = (event["state"], packet["time_s"])
                # Saturated force is not an equality observation; retain the event
                # but do not update geometry/compliance from clipped magnitudes.
                active &= ~saturated
                if int(active.sum()) > tactile_per_packet:
                    candidates = torch.nonzero(active).flatten()
                    if self.modality == "VB":
                        selected = candidates[torch.linspace(0, len(candidates)-1, tactile_per_packet, device=self.device).long()]
                    else:
                        selected = candidates[compressive[candidates].topk(tactile_per_packet).indices]
                    active = torch.zeros_like(active)
                    active[selected] = True
                if not active.any():
                    continue
                pts = support["points"][active] @ transform[:3, :3].T + transform[:3, 3]
                normal = support["normals"][active] @ transform[:3, :3].T
                # Acquisition time, not reception time, determines object pose.
                upper = min(int(torch.searchsorted(times, self.tensor(packet["time_s"]), right=True)), len(frames) - 1)
                lower = max(0, upper - 1)
                if upper != lower and float(times[upper]-times[lower]) > .10000001 and not any(abs(packet["time_s"]-float(times[j])) < 1e-8 for j in [lower, upper]):
                    event["state"] = "unbracketed_pose_interval"
                    continue
                alpha = 0.0 if lower == upper else (packet["time_s"] - float(times[lower])) / float(times[upper] - times[lower])
                fn = compressive[active]
                data["contacts"].append((lower, upper, alpha, pts, normal, fn, support["radius"][active]))
                for index in torch.nonzero(active).flatten().tolist() if self.modality == "VF" else []:
                    track = data["force_tracks"].setdefault((packet["sensor_id"], index), [])
                    track.append((packet["time_s"], compressive[index]))
        return data

    def fixed_visual_poses(self, frames, data, budget, deadline):
        """Independent coarse/vision path for the shape-only ablation.

        Do not consume tactile evidence, shape-refined geometry, or a memory
        cache populated by the joint solver. Reused vision yields a conditional
        shape covariance, not a second independent pose measurement likelihood.
        """
        if len(data["anchors"]) == len(frames):
            return torch.stack([entry[1] for entry in data["anchors"]]), {
                "source": "per_frame_independent_measurement", "gradient_steps": 0,
                "translation_sigma_m": [entry[2] for entry in data["anchors"]],
                "rotation_sigma_rad": [entry[3] for entry in data["anchors"]]}
        if budget < 2:
            return None, {"source": "unavailable", "gradient_steps": 0, "reason": "insufficient_shared_step_budget"}
        if self.independent_pose_estimator is None:
            self.independent_pose_estimator = BeliefEstimator(self.coarse_prior, self.cal, self.cfg, self.device, "V", "pose_only")
        visual_frames = [{**frame, "tactile": []} for frame in frames]
        pose_result = self.independent_pose_estimator.fit(visual_frames, steps=budget//2, wall_deadline=deadline)
        metadata = {"source": "visual_only_coarse_registration", "gradient_steps": pose_result.get("steps", 0),
                    "uses_refined_shape": False, "uses_tactile": False,
                    "uncertainty_scope": "conditional shape solve; fixed visual poses retain estimation uncertainty"}
        if not pose_result["state_updated"]:
            metadata["reason"] = "no_independent_visual_pose"
            return None, metadata
        null = self.tensor(pose_result["null_projector"])
        if bool((null.diag()[:6*len(frames)] >= .05).any()):
            metadata["reason"] = "independent_pose_not_observable_at_every_frame"
            return None, metadata
        metadata["pose_variance_diagonal_normalized"] = self.tensor(pose_result["covariance"]).diag()[:6*len(frames)].tolist()
        return self.tensor(pose_result["T_world_object"]), metadata

    def fit(self, frames, steps=None, wall_deadline=None):
        started = time.monotonic()
        cfg, data = self.cfg, self.prepare(frames)
        budget = cfg["steps"] if steps is None else steps
        if not 1 <= budget <= cfg["steps"]:
            raise ValueError("Gradient-step budget exceeded")
        deadline = wall_deadline if wall_deadline is not None else started+cfg["maximum_wall_s"]
        fixed_poses, independent_pose, pose_steps = None, None, 0
        if self.ablation == "shape_only":
            fixed_poses, independent_pose = self.fixed_visual_poses(frames, data, budget, deadline)
            pose_steps = independent_pose["gradient_steps"]
            if fixed_poses is None:
                return {"status": "awaiting_verification", "inference_status": "unobservable",
                    "reason": "independent_pose_unavailable", "time_s": frames[-1]["time_s"],
                    "events": data["events"], "covariance": None, "state_updated": False,
                    "independent_pose": independent_pose, "steps": pose_steps, "wall_s": time.monotonic()-started}
        count, modes = len(frames), self.basis.shape[1]
        size = 6 * count + modes + 1
        base = self.initial.expand(count, 4, 4).clone()
        parameters = torch.zeros(size, dtype=self.v.dtype, device=self.device)
        c0 = max(self.initial_c, 1e-6) / cfg["maximum_compliance_m_per_n"]
        parameters[-1] = math.log(c0 / (1 - c0))
        if self.previous:
            base[:] = self.tensor(self.previous["T_world_object"])
            parameters[6 * count:6 * count + modes] = self.tensor(self.previous["shape_parameters"])
            parameters[-1] = self.previous["compliance_parameter"]
        if fixed_poses is not None:
            base = fixed_poses.detach().clone()
        else:
            for index, frame in enumerate(frames):
                cached = getattr(self, "pose_initializations", {}).get(frame["time_s"])
                if cached is not None:
                    base[index] = self.transform(cached)
        base_vectors = torch.stack([rotation_vector(value[:3, :3]@self.initial[:3, :3].T) for value in base])
        excitation = False
        for track in data["force_tracks"].values():
            if len({entry[0] for entry in track}) >= cfg["minimum_force_samples"]:
                loads = torch.stack([entry[1] for entry in track])
                excitation |= bool(loads.max()-loads.min() >= cfg["minimum_force_span_n"])
        learn_compliance = self.modality == "VF" and self.ablation == "joint" and excitation
        active = torch.ones(size, dtype=self.v.dtype, device=self.device)
        if self.ablation == "shape_only":
            active[:6 * count] = 0
        if self.ablation == "pose_only":
            active[6 * count:-1] = 0
        if not learn_compliance:
            active[-1] = 0
        initial_parameters = parameters.clone()
        parameters.requires_grad_(True)

        def state(x):
            x = initial_parameters + (x - initial_parameters) * active
            twists = x[:6 * count].reshape(count, 6)
            rotations = so3(base_vectors + twists[:, 3:] * cfg["rotation_scale_rad"]) @ self.initial[:3, :3]
            translations = base[:, :3, 3] + twists[:, :3] * cfg["translation_scale_m"]
            offsets = self.basis @ (x[6 * count:-1] * cfg["shape_scale_m"])
            offsets = offsets * (cfg["maximum_displacement_m"] / offsets.abs().max().clamp_min(cfg["maximum_displacement_m"]))
            vertices = self.v + self.n * offsets[:, None]
            triangle = vertices[self.faces]
            face_normals = torch.linalg.cross(triangle[:, 1] - triangle[:, 0], triangle[:, 2] - triangle[:, 0])
            vertex_normals = torch.zeros_like(vertices).index_add(0, self.faces.reshape(-1), face_normals[:, None, :].expand(-1, 3, -1).reshape(-1, 3))
            normals = unit(vertex_normals)
            compliance = cfg["maximum_compliance_m_per_n"] * x[-1].sigmoid()
            if self.ablation == "rigid_contact":
                compliance = compliance * 0
            return rotations, translations, vertices, normals, offsets, compliance

        def surface(points, vertices, normals):
            distances, indices = torch.cdist(points, vertices).topk(min(cfg["neighbors"], len(vertices)), largest=False)
            neighbors = vertices[indices]
            n = normals[indices]
            weights = torch.softmax(-distances.square() / (.5 * cfg["kernel_radius_m"]) ** 2, dim=-1)
            normal = unit((n * weights[:, :, None]).sum(1))
            # Trapezoidal integration of the local normal field along the chord:
            # a one-sided tangent plane has an O(curvature*distance^2) bias that
            # otherwise looks like load-dependent indentation/compliance.
            symmetric_normal = (n+normal[:, None, :])/2
            phi = (((points[:, None, :] - neighbors) * symmetric_normal).sum(-1) * weights).sum(-1)
            return phi, normal, distances[:, 0]

        # Freeze correspondence acceptance from the initial estimate. Optimizing
        # away all observations must not reduce the objective by dropping rows.
        masks = {"vision": [], "contacts": []}
        with torch.no_grad():
            r, t, v, n, _, _ = state(parameters)
            for i, points, normals, sigma in data["vision"]:
                local = (points - t[i]) @ r[i]
                _, estimate_n, distance = surface(local, v, n)
                masks["vision"].append((distance < cfg["correspondence_radius_m"]) & ((estimate_n * (normals @ r[i])).sum(-1) > .2))
            for lo, hi, a, points, normals, force, radius in data["contacts"]:
                # Small inter-keyframe motion approximation; SO3 remains proper.
                rotation_parameters = base_vectors+parameters[:6*count].reshape(count, 6)[:, 3:]*cfg["rotation_scale_rad"]
                rt = so3((1-a)*rotation_parameters[lo]+a*rotation_parameters[hi])@self.initial[:3, :3]
                local = (points - ((1-a)*t[lo] + a*t[hi])) @ rt
                _, object_n, distance = surface(local, v, n)
                masks["contacts"].append((distance < cfg["correspondence_radius_m"] + radius) & ((object_n * (normals @ rt)).sum(-1) < -.2))

        def residual(x, include_prior=False):
            r, t, v, n, offsets, compliance = state(x)
            rows = []
            for index, (i, points, normals, sigma) in enumerate(data["vision"]):
                local = (points - t[i]) @ r[i]
                phi, _, _ = surface(local, v, n)
                rows.append(phi[masks["vision"][index]] / sigma)
            for i, measured, sigma_t, sigma_r in data["anchors"]:
                rows.append((t[i] - measured[:3, 3]) / sigma_t)
                # Chordal SO3 residual, scaled to angular noise near identity.
                rows.append(((r[i] - measured[:3, :3]) / (math.sqrt(2) * sigma_r)).reshape(-1))
            for index, (lo, hi, a, points, normals, force, radius) in enumerate(data["contacts"]):
                twist = x[:6 * count].reshape(count, 6)
                if self.ablation == "shape_only":
                    twist = twist * 0
                rotation_parameters = base_vectors+twist[:, 3:]*cfg["rotation_scale_rad"]
                rt = so3((1-a)*rotation_parameters[lo]+a*rotation_parameters[hi])@self.initial[:3, :3]
                phi, _, _ = surface((points - ((1-a)*t[lo] + a*t[hi])) @ rt, v, n)
                mask = masks["contacts"][index]
                if self.modality == "VB" or (self.modality == "VF" and self.ablation == "joint" and not excitation):
                    # Contact bit constrains an interval, not a fabricated force.
                    allowance = radius + cfg["maximum_compliance_m_per_n"] * self.cal["saturation_n"]
                    rows.append(torch.relu(phi.abs() - allowance)[mask] / cfg["surface_sigma_m"])
                else:
                    sigma = (cfg["surface_sigma_m"]**2 + radius.square()/3 + (compliance*self.cal["noise_std_n"])**2).sqrt()
                    rows.append(((phi + compliance*force) / sigma)[mask])
            if include_prior:
                rows.append(offsets[self.roi] / (cfg["shape_prior_sigma_m"] * math.sqrt(len(self.roi))))
                rows.append((t - base[:, :3, 3]).reshape(-1) / .05)
                rows.append(x[:6*count].reshape(count, 6)[:, 3:].reshape(-1) * cfg["rotation_scale_rad"] / .5)
                rows.append(((compliance - self.initial_c) / cfg["compliance_prior_sigma_m_per_n"]).reshape(1))
            return torch.cat(rows) if rows else x[:0]

        accepted_visual = sum(int(mask.sum()) for mask in masks["vision"])
        accepted_contact = sum(int(mask.sum()) for mask in masks["contacts"])
        if accepted_visual + accepted_contact + len(data["anchors"]) == 0:
            return {"status": "awaiting_verification", "inference_status": "unobservable",
                    "reason": "no usable observations; state not updated", "time_s": frames[-1]["time_s"],
                    "events": data["events"], "covariance": None, "state_updated": False,
                    "independent_pose": independent_pose, "steps": pose_steps}
        optimizer = torch.optim.Adam([parameters], lr=cfg["learning_rate"])
        trace = []
        for iteration in range(budget-pose_steps):
            if time.monotonic() > (wall_deadline if wall_deadline is not None else started + cfg["maximum_wall_s"]):
                raise TimeoutError("Declared wall budget exhausted; partial run is not acceptance")
            optimizer.zero_grad(set_to_none=True)
            error = residual(parameters, True)
            delta = cfg["huber_delta"]
            loss = (delta**2 * (torch.sqrt(1 + (error / delta)**2) - 1)).sum()
            if not torch.isfinite(loss):
                raise RuntimeError("Nonfinite joint objective")
            loss.backward()
            if parameters.grad is None or not torch.isfinite(parameters.grad).all():
                raise RuntimeError("Nonfinite joint gradient")
            parameters.grad *= active
            optimizer.step()
            trace.append(float(loss.detach()))
        # Observability is computed WITHOUT regularization. A prior cannot make
        # an unobservable compliance or occluded shape become a measurement.
        point = parameters.detach().requires_grad_(True)
        # Central differences stay on CUDA and support cdist/top-k on Torch 2.5;
        # forward-mode AD is not implemented for every cdist backend. FP64 and
        # normalized coordinates make epsilon correspond to micrometer scales.
        def information(at):
            with torch.no_grad():
                columns = []
                for j in range(size):
                    if time.monotonic() > (wall_deadline if wall_deadline is not None else started + cfg["maximum_wall_s"]):
                        raise TimeoutError("Information calculation exceeded declared wall budget")
                    direction = torch.zeros_like(at)
                    direction[j] = 1e-3
                    columns.append((residual(at + direction, False) - residual(at - direction, False)) / .002)
                jac = torch.stack(columns, -1)
                err = residual(at, False)
                weighted = jac * (1 + (err / cfg["huber_delta"])**2).pow(-.75)[:, None]
                return weighted.T @ weighted
        raw = residual(point, False).detach()
        fisher = information(point.detach())
        eigenvalues, eigenvectors = torch.linalg.eigh(fisher)
        threshold = max(cfg["information_absolute_threshold"], float(eigenvalues.max()) * cfg["information_relative_threshold"])
        identifiable = eigenvalues > threshold
        identifiable_vectors = eigenvectors[:, identifiable]
        null_vectors = eigenvectors[:, ~identifiable]
        projector = identifiable_vectors @ identifiable_vectors.T
        # Freeze unobservable coupled directions at their incoming estimate.
        projected = initial_parameters + projector @ (point.detach() - initial_parameters)
        projected = initial_parameters + (projected - initial_parameters) * active
        # Report uncertainty at the state actually returned, after null freezing.
        eigenvalues, eigenvectors = torch.linalg.eigh(information(projected))
        threshold = max(cfg["information_absolute_threshold"], float(eigenvalues.max()) * cfg["information_relative_threshold"])
        identifiable = eigenvalues > threshold
        identifiable_vectors = eigenvectors[:, identifiable]
        null_vectors = eigenvectors[:, ~identifiable]
        covariance = (identifiable_vectors / eigenvalues[identifiable].clamp_min(threshold)) @ identifiable_vectors.T
        null_projector = null_vectors @ null_vectors.T
        r, t, vertices, normals, offsets, compliance = state(projected)
        reference_triangles, updated_triangles = self.v[self.faces], vertices[self.faces]
        reference_area = torch.linalg.cross(reference_triangles[:, 1]-reference_triangles[:, 0], reference_triangles[:, 2]-reference_triangles[:, 0])
        updated_area = torch.linalg.cross(updated_triangles[:, 1]-updated_triangles[:, 0], updated_triangles[:, 2]-updated_triangles[:, 0])
        if (updated_area.norm(dim=-1) < 1e-12).any() or ((reference_area*updated_area).sum(-1) <= 0).any():
            raise RuntimeError("Local refinement inverted/degenerates a mesh face; reject the update")
        transforms = torch.eye(4, device=self.device, dtype=self.v.dtype).expand(count, 4, 4).clone()
        transforms[:, :3, :3], transforms[:, :3, 3] = r, t
        compliance_observable = learn_compliance and float(null_projector[-1, -1]) < .05
        self.previous = {"T_world_object": transforms[-1].detach().tolist(),
                         "shape_parameters": projected[6*count:-1].tolist(), "compliance_parameter": float(projected[-1])}
        return {"status": "awaiting_verification", "inference_status": "observable" if int(identifiable.sum()) == int(active.sum()) else "partially_observable",
            "state_updated": bool(identifiable.any()), "time_s": frames[-1]["time_s"], "window_times_s": data["times"].tolist(),
            "T_world_object": transforms.detach().tolist(), "vertices_object_m": vertices.detach().tolist(),
            "normals_object": normals.detach().tolist(), "faces": self.faces.tolist(),
            "shape_offsets_m": offsets.detach().tolist(), "shape_basis": self.basis.tolist(),
            "effective_compliance_m_per_n": float(compliance.detach()), "compliance_observable": compliance_observable,
            "force_excited": excitation, "observed_rank": int(identifiable.sum()), "active_parameters": int(active.sum()),
            "force_update_mode": "continuous_force" if (learn_compliance or self.ablation != "joint") else "interval_only_until_excited",
            "parameter_order": f"{count}*(world_translation_xyz,rotation_vector_xyz),{modes}*shape_coeff,compliance_logit",
            "parameter_scales": {"translation_m": cfg["translation_scale_m"], "rotation_rad": cfg["rotation_scale_rad"],
                                 "shape_m": cfg["shape_scale_m"], "compliance_derivative_m_per_n": float(compliance.detach()*(1-compliance.detach()/cfg["maximum_compliance_m_per_n"]))},
            "covariance": covariance.tolist(), "null_projector": null_projector.tolist(),
            "uncertainty_status": "uncalibrated local data-information approximation; null directions have unbounded uncertainty",
            "information_eigenvalues": eigenvalues.tolist(), "information_threshold": threshold,
            "accepted_visual_points": accepted_visual, "accepted_contact_taxels": accepted_contact,
            "events": data["events"], "friction_interval": None, "slip_probability": None,
            "unknown_state_reason": "Force alone does not certify sticking or identify friction; no slip classifier calibrated",
            "loss_trace": trace, "steps": budget, "shape_or_joint_steps": budget-pose_steps,
            "independent_pose": independent_pose, "wall_s": time.monotonic()-started,
            "data_residual_rms_before_projection": float(raw.square().mean().sqrt()),
            "data_residual_rms_after_projection": float(residual(projected, False).detach().square().mean().sqrt()),
            "maximum_shape_displacement_m": float(offsets.abs().max().detach()),
            "peak_cuda_bytes": torch.cuda.max_memory_allocated(self.device)}
