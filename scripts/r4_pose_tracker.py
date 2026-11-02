"""Cheap CUDA point-to-plane pose tracking between bounded shape updates.

Geometry is frozen. The old covariance is propagated conservatively and NOT
shrunk as if fixed-model ICP had resolved shape uncertainty. This avoids using
four expensive shape updates as the only pose observations in a 12s episode.
"""
import copy
import torch
from r4_belief import so3


def track_pose(belief, frame, device):
    visual = frame["vision"]
    if belief is None or visual is None or len(visual["points_world_m"]) < 32:
        return None
    tensor = lambda x: torch.tensor(x, device=device, dtype=torch.float64)
    pose = tensor(belief["T_world_object"][-1])
    vertices, normals = tensor(belief["vertices_object_m"]), tensor(belief["normals_object"])
    observed, observed_n = tensor(visual["points_world_m"]), tensor(visual["normals_world"])
    measured_rank = 0
    for _ in range(3):
        world = vertices@pose[:3, :3].T+pose[:3, 3]
        world_n = normals@pose[:3, :3].T
        distance, index = torch.cdist(observed, world).min(-1)
        keep = (distance < .015) & ((observed_n*world_n[index]).sum(-1) > .3)
        if int(keep.sum()) < 32:
            return None
        p, target, normal = world[index[keep]], observed[keep], world_n[index[keep]]
        center = pose[:3, 3]
        jac = torch.cat([normal, torch.linalg.cross(p-center, normal)], -1)
        residual = ((target-p)*normal).sum(-1)
        weight = 1/(1+(residual/.002)**2).sqrt()
        weighted = jac*weight[:, None]
        information = weighted.T@jac
        eigen, vectors = torch.linalg.eigh(information)
        valid = eigen > max(float(eigen.max())*1e-7, 1e-8)
        measured_rank = int(valid.sum())
        if measured_rank < 3:
            return None
        delta = (vectors[:, valid]/eigen[valid])@vectors[:, valid].T@(weighted.T@residual)
        if delta[:3].norm() > .005 or delta[3:].norm() > .1:
            return None
        pose[:3, 3] += delta[:3]
        pose[:3, :3] = so3(delta[3:])@pose[:3, :3]
    result = copy.deepcopy(belief)
    result["T_world_object"][-1] = pose.tolist()
    result["window_times_s"][-1] = frame["time_s"]
    result["time_s"] = frame["time_s"]
    result["state_updated"] = True
    result["prediction_age_s"] = 0
    result["pose_tracking_rank"] = measured_rank
    result["geometry_time_s"] = belief.get("geometry_time_s", belief["time_s"]-belief.get("prediction_age_s", 0))
    result["pose_tracking_uncertainty"] = "propagated conservative prior; no covariance shrink from fixed-shape ICP"
    return result
