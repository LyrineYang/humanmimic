"""Strict data-only boundary used by collector, replay and the isolated estimator.

No simulator imports. No object truth, asset paths or arbitrary NPZ/pickle keys.
Semantic tensor checks (SE3, sizes, finite values) run on CUDA in the estimator.
"""
import json
import math


def keys(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or not set(required) <= set(value):
        raise ValueError("Unexpected/missing public fields; truth labels and paths are forbidden")


def finite(value):
    if isinstance(value, dict):
        for item in value.values():
            finite(item)
    elif isinstance(value, list):
        for item in value:
            finite(item)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Nonfinite JSON input")


def validate_frame(frame, previous_time=-1, tactile_mode="force"):
    if tactile_mode not in {"force", "binary"}:
        raise ValueError("Unknown tactile input mode")
    keys(frame, {"schema_version", "role", "split", "source", "time_s", "joint_position_rad", "joint_target_rad", "tactile", "vision"}, {"T_world_wrist"})
    if frame["schema_version"] != 2 or frame["role"] != "observation" or frame["split"] not in {"readiness", "debug"}:
        raise ValueError("Only public development observations are accepted")
    if frame["source"] not in {"simulated_sensor", "measured", "synthetic_fixture"}:
        raise ValueError("Undeclared sensor source")
    now = frame["time_s"]
    if not isinstance(now, (float, int)) or not now >= 0 or not now > previous_time:
        raise ValueError("Observation times must strictly increase")
    if len(frame["joint_position_rad"]) != 16 or len(frame["joint_target_rad"]) != 16:
        raise ValueError("LEAP requires 16 named-order joints")
    for packet in frame["tactile"]:
        measurement_key = "force_sensor_n" if tactile_mode == "force" else "contact_bits"
        keys(packet, {"sensor_id", "time_s", "received_time_s", "valid", "reason", "T_world_sensor", measurement_key, "saturated"})
        if packet["sensor_id"] not in {"if", "mf", "rf", "th"} or type(packet["valid"]) is not bool:
            raise ValueError("Invalid sensor identity/health")
        if not 0 <= packet["time_s"] <= packet["received_time_s"] <= now + 1e-9:
            raise ValueError("Acausal sensor data")
        if not packet["valid"] and (packet[measurement_key] is not None or packet["saturated"] is not None):
            raise ValueError("Missing data must be null, not zero force")
        if tactile_mode == "binary" and packet["valid"] and any(type(bit) is not bool for row in packet["contact_bits"] for bit in row):
            raise ValueError("Binary tactile inputs contain only boolean contacts and health")
    vision = frame["vision"]
    if vision is not None:
        keys(vision, {"time_s", "source", "points_world_m", "normals_world", "sigma_m"}, {"pose_measurement"})
        if vision["source"] not in {"simulated_rgbd_with_instance_mask", "measured_rgbd", "synthetic_fixture"}:
            raise ValueError("Undeclared visual provenance")
        if not 0 <= vision["time_s"] <= now or vision["sigma_m"] <= 0:
            raise ValueError("Invalid visual time/noise")
        if "pose_measurement" in vision:
            anchor = vision["pose_measurement"]
            keys(anchor, {"T_world_object", "translation_sigma_m", "rotation_sigma_rad", "source"})
            if anchor["source"] not in {"independent_fiducial", "synthetic_fixture"}:
                raise ValueError("Pose anchor must be independent; do not double-count point registration")
            if anchor["translation_sigma_m"] <= 0 or anchor["rotation_sigma_rad"] <= 0:
                raise ValueError("Pose measurement uncertainty must be positive")
    finite(frame)
    return frame


def validate_calibration(calibration):
    keys(calibration, {"schema_version", "role", "hand", "size", "fov_deg", "gamma", "surface_margin_m", "pads",
                       "threshold_n", "max_age_s", "noise_std_n", "saturation_n", "force_convention", "calibration_status"})
    if calibration["role"] != "hand_sensor_calibration" or calibration["schema_version"] != 2 or calibration["hand"] != "leap_right":
        raise ValueError("Require hand-only calibration")
    if calibration["force_convention"] != "force_on_hand_in_sensor_xyz" or set(calibration["pads"]) != {"if", "mf", "rf", "th"}:
        raise ValueError("Invalid force calibration")
    width, height = calibration["size"]
    if any(type(n) is not int for n in [width, height]) or not 1 <= width * height <= 512:
        raise ValueError("Invalid taxel layout")
    if not 0 < calibration["fov_deg"][0] <= 180 or not 0 < calibration["fov_deg"][1] <= 90 or calibration["gamma"] != 0:
        raise ValueError("Only calibrated linear angular bins are supported")
    if not 0 < calibration["threshold_n"] < calibration["saturation_n"] or calibration["max_age_s"] <= 0:
        raise ValueError("Invalid sensor bounds")
    if calibration["noise_std_n"] < 0 or calibration["surface_margin_m"] <= 0:
        raise ValueError("Invalid sensor uncertainty")
    for pad in calibration["pads"].values():
        keys(pad, {"triangles_sensor_m"})
        if not 1 <= len(pad["triangles_sensor_m"]) <= 4096:
            raise ValueError("Invalid hand surface budget")
    finite(calibration)
    return calibration


def validate_prior(prior):
    keys(prior, {"schema_version", "role", "source", "vertices_object_m", "normals_object", "faces",
                 "roi_vertex_indices", "T_world_object_initial", "initial_time_s", "compliance_initial_m_per_n"})
    if prior["schema_version"] != 2 or prior["role"] != "coarse_estimate" or prior["source"] not in {"observed_rgbd", "declared_generic_prior", "synthetic_fixture"}:
        raise ValueError("A true object mesh/pose cannot be used as a prior")
    if prior["initial_time_s"] < 0:
        raise ValueError("Invalid prior acquisition time")
    finite(prior)
    return prior


def read_public(directory, prior_path):
    calibration = validate_calibration(json.loads((directory / "calibration.json").read_text()))
    prior = validate_prior(json.loads(prior_path.read_text()))
    frames, previous = [], -1
    with (directory / "observations.jsonl").open() as handle:
        for line in handle:
            frame = validate_frame(json.loads(line), previous)
            previous = frame["time_s"]
            frames.append(frame)
    if not frames:
        raise ValueError("Empty observation stream")
    return {"calibration": calibration, "prior": prior, "frames": frames}
