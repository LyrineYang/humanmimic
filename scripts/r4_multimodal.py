"""CPU research primitives for sensor provenance, identifiability and active touch.

These do not implement WM-CraftNet inference, a full SDF, or a robot controller.
The linear patch model is a declared local diagnostic, not a reconstruction claim.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares


def validate_measurement(packet, now_s, max_age_s=.1):
    """Accept declared sensor output only; missing/stale data is not 'no contact'."""
    required = {"schema_version", "kind", "source", "sensor_id", "time_s",
                "received_time_s", "valid", "T_world_sensor", "units"}
    optional = {"contact", "force_sensor_n", "surface_points_sensor_m", "sigma_m"}
    if set(packet) - required - optional or not required <= set(packet):
        raise ValueError("Unknown/missing fields; simulator truth is not sensor input")
    if packet["schema_version"] != 1 or packet["source"] not in {"simulated_sensor", "measured", "synthetic_fixture"}:
        raise ValueError("Declare sensor provenance")
    if not isinstance(packet["sensor_id"], str) or not packet["sensor_id"]:
        raise ValueError("Sensor identity missing")
    if packet["units"] != {"length": "m", "force": "N", "time": "s"}:
        raise ValueError("Explicit SI units required")
    if packet["kind"] not in {"binary_contact", "force", "tactile_depth"}:
        raise ValueError("Unsupported sensor modality")
    if type(packet["valid"]) is not bool:
        raise ValueError("valid must be boolean")
    times = np.asarray([packet["time_s"], packet["received_time_s"], now_s, max_age_s], float)
    if not np.isfinite(times).all() or times.min() < 0 or not times[0] <= times[1] <= times[2]:
        raise ValueError("Nonfinite, negative or acausal timestamps")
    transform = np.asarray(packet["T_world_sensor"], float)
    if transform.shape != (4, 4) or not np.isfinite(transform).all():
        raise ValueError("Require finite sensor-to-world transform from calibrated kinematics")
    rotation = transform[:3, :3]
    if not np.allclose(transform[3], [0, 0, 0, 1]) or not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-6) or not np.isclose(np.linalg.det(rotation), 1, atol=1e-6):
        raise ValueError("Sensor transform must be rigid and right-handed")
    kind = packet["kind"]
    if kind != "tactile_depth" and {"surface_points_sensor_m", "sigma_m"} & set(packet):
        raise ValueError("A force or contact bit is not a measured surface patch")
    if kind != "force" and "force_sensor_n" in packet:
        raise ValueError("Do not invent force from another modality")
    if "contact" in packet and type(packet["contact"]) is not bool:
        raise ValueError("contact must be boolean")
    if not packet["valid"] or now_s - packet["time_s"] > max_age_s:
        return False
    if kind == "binary_contact" and "contact" not in packet:
        raise ValueError("Missing contact observation")
    if kind == "force":
        force = np.asarray(packet.get("force_sensor_n"), float)
        if force.shape != (3,) or not np.isfinite(force).all():
            raise ValueError("Force must be measured finite xyz in the sensor frame")
    if kind == "tactile_depth":
        points = np.asarray(packet.get("surface_points_sensor_m"), float)
        sigma = np.asarray(packet.get("sigma_m"), float)
        if points.ndim != 2 or points.shape[1] != 3 or not 1 <= len(points) <= 1024 or not np.isfinite(points).all():
            raise ValueError("Invalid measured tactile surface patch")
        if sigma.ndim != 0 or not np.isfinite(sigma) or sigma <= 0:
            raise ValueError("Tactile depth needs positive calibrated uncertainty")
    return True


def fit_contact_patch(displacement_m, normal_force_n, sigma_m, *, pose_observation_m=None,
                      pose_sigma_m=None):
    """Fit y = local_shape_offset + pose_offset + compliance * force.

    Positive displacement follows the probe's inward axis. Compliance is the
    effective sensor/contact compliance (m/N), not an object's Young modulus.
    Independent pose evidence and changing load are needed for identifiability.
    """
    y, force = np.asarray(displacement_m, float), np.asarray(normal_force_n, float)
    sigma = np.broadcast_to(np.asarray(sigma_m, float), y.shape)
    if y.ndim != 1 or len(y) < 3 or force.shape != y.shape:
        raise ValueError("Require at least three synchronized displacement/force samples")
    if not (np.isfinite(y).all() and np.isfinite(force).all() and np.isfinite(sigma).all()) or np.any(force <= 0) or np.any(sigma <= 0):
        raise ValueError("Finite positive contact force and measurement uncertainty required")
    matrix = np.column_stack([np.ones(len(y)), np.ones(len(y)), force])
    if pose_observation_m is not None:
        if pose_sigma_m is None or not np.isfinite([pose_observation_m, pose_sigma_m]).all() or pose_sigma_m <= 0:
            raise ValueError("Pose anchor requires calibrated uncertainty")
        matrix = np.vstack([matrix, [0, 1, 0]])
        y = np.r_[y, pose_observation_m]
        sigma = np.r_[sigma, pose_sigma_m]
    elif pose_sigma_m is not None:
        raise ValueError("Pose uncertainty without an observation is not evidence")
    # Scale columns to comparable physical changes before checking rank.
    scale = np.array([.01, .01, .001])
    design = matrix * scale / sigma[:, None]
    singular = np.linalg.svd(design, compute_uv=False)
    rank = int(np.sum(singular > singular[0] * 1e-8))
    if rank < 3:
        return {"status": "unobservable", "data_rank": rank,
                "reason": "Shape, pose and compliance are confounded; collect independent pose and varying-force evidence",
                "estimate": None, "covariance": None}
    condition = float(singular[0] / singular[-1])
    if condition > 1e6:
        return {"status": "unobservable", "data_rank": rank, "condition": condition,
                "reason": "Insufficient excitation at measurement precision", "estimate": None, "covariance": None}
    fit = least_squares(lambda z: (matrix @ (z * scale) - y) / sigma,
                        [0, 0, 1], bounds=([-np.inf, -np.inf, 0], [np.inf]*3),
                        loss="soft_l1", f_scale=1, max_nfev=100)
    information = fit.jac.T @ fit.jac
    covariance = np.diag(scale) @ np.linalg.inv(information) @ np.diag(scale)
    return {"status": "passed" if fit.success else "failed", "data_rank": rank, "condition": condition,
            "estimate": dict(zip(["shape_offset_m", "pose_offset_m", "effective_compliance_m_per_n"], (fit.x*scale).tolist())),
            "covariance": covariance.tolist(), "evaluations": fit.nfev,
            "scope": "Local linear identifiability diagnostic; covariance assumes independent calibrated residuals"}


def score_touches(covariance, task_jacobian, candidates, *, force_limit_n=2.):
    """Expected reduction of task-output variance from a candidate measurement.

    H and task J must come from the estimated model, not evaluation geometry.
    Candidate rejection is based on supplied force estimates; not a safety proof.
    """
    cov, jac = np.asarray(covariance, float), np.atleast_2d(np.asarray(task_jacobian, float))
    if cov.ndim != 2 or cov.shape[0] != cov.shape[1] or jac.shape[1] != len(cov) or not np.isfinite(cov).all() or not np.isfinite(jac).all():
        raise ValueError("Invalid belief/task Jacobian")
    if not np.allclose(cov, cov.T) or np.linalg.eigvalsh(cov).min() < -1e-12:
        raise ValueError("Covariance must be symmetric positive semidefinite")
    if not np.isfinite(force_limit_n) or force_limit_n <= 0:
        raise ValueError("Force bound must be finite and positive")
    results = []
    for candidate in candidates:
        h = np.asarray(candidate["measurement_jacobian"], float)
        noise, cost, force = (float(candidate[k]) for k in ["noise_variance", "cost_seconds", "predicted_force_n"])
        if h.shape != (len(cov),) or not np.isfinite(h).all() or not np.isfinite([noise, cost, force]).all() or noise <= 0 or cost <= 0 or force < 0:
            raise ValueError("Invalid candidate observation model")
        v = cov @ h
        reduction = np.outer(v, v) / (h @ v + noise)
        gain = max(0., float(np.trace(jac @ reduction @ jac.T)))
        permitted = bool(force <= force_limit_n and candidate.get("reachable") is True)
        results.append({"id": candidate["id"], "permitted": permitted,
                        "task_variance_reduction": gain, "score": gain/cost if permitted else None})
    feasible = [x for x in results if x["permitted"] and x["score"] > 0]
    best = max(feasible, key=lambda x: x["score"])["id"] if feasible else None
    return {"selected": best, "candidates": results}


def static_friction_lower_bound(normal_force_n, shear_force_n, error_bound_n=0.):
    """Sticking supplies a conservative lower bound on mu, never its exact value."""
    fn, ft = np.asarray(normal_force_n, float), np.asarray(shear_force_n, float)
    if fn.shape != ft.shape or not fn.size or not np.isfinite(fn).all() or not np.isfinite(ft).all() or np.any(fn <= 0) or np.any(ft < 0) or not np.isfinite(error_bound_n) or error_bound_n < 0:
        raise ValueError("Require positive normal force, nonnegative shear magnitude and error bound")
    lower = float(np.max(np.maximum(ft-error_bound_n, 0)/(fn+error_bound_n)))
    return {"mu_lower": lower, "mu_upper": None, "identification": "lower_bound_only",
            "assumption": "Sticking contact; normal/shear magnitudes are calibrated sensor measurements"}
