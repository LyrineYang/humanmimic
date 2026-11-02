"""Private analytic CUDA fixture metrics; never import into the estimator."""
import torch


def evaluate(result, truth, device):
    belief = result["beliefs"][-1]
    if not belief["state_updated"]:
        return {"state_updated": False}
    tensor = lambda x: torch.tensor(x, device=device, dtype=torch.float64)
    pose, target = tensor(belief["T_world_object"]), tensor(truth["poses"])
    translation_error = pose[:, :3, 3] - target[:, :3, 3]
    vertices, radii = tensor(belief["vertices_object_m"]), tensor(truth["radii_m"])
    # Independent ellipsoid implicit-distance approximation, not the fitter's RBF loss.
    implicit = (vertices/radii).square().sum(-1) - 1
    gradient = 2 * vertices/radii.square()
    shape_error = implicit / gradient.norm(dim=-1).clamp_min(1e-12)
    covariance, null = tensor(belief["covariance"]), tensor(belief["null_projector"])
    offset = 6*(len(pose)-1)
    variance = covariance.diag()[offset:offset+3] * belief["parameter_scales"]["translation_m"]**2
    observable_pose = bool((null.diag()[offset:offset+3] < .05).all())
    # Bonferroni 95% simultaneous coverage of x/y/z translation and compliance.
    pose_covered = bool((translation_error[-1].abs() <= 2.498*variance.clamp_min(0).sqrt()).all())
    compliance_error = belief["effective_compliance_m_per_n"] - truth["compliance_m_per_n"]
    compliance_std = float(covariance[-1, -1].clamp_min(0).sqrt()) * belief["parameter_scales"]["compliance_derivative_m_per_n"]
    return {"state_updated": True, "position_rmse_m": float(translation_error.square().sum(-1).mean().sqrt()),
            "shape_surface_rmse_m": float(shape_error.square().mean().sqrt()), "compliance_error_m_per_n": abs(compliance_error),
            "pose_observable": observable_pose, "pose_covered": pose_covered,
            "compliance_observable": belief["compliance_observable"],
            "compliance_covered": belief["compliance_observable"] and abs(compliance_error) <= 2.498*compliance_std}
