"""Audit consumed SMPL samples, fixed timing and measured robot limb geometry.

Run with humanoid-r1 after physics stops. MuJoCo forward kinematics only replays
recorded actual qpos; it does not execute a controller or change a simulation.
Human 3D is the extracted estimate, never ground truth. No time-shift fitting.
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from r2_common import PROJECT, SONIC, sha256, storage_check, write_json
from r2_geometry import body_frame_descriptors, descriptor_difference

POINTS = ("left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle", "left_shoulder", "right_shoulder", "left_elbow", "right_elbow", "left_wrist", "right_wrist")
SMPL_INDICES = (1, 2, 4, 5, 7, 8, 16, 17, 18, 19, 20, 21)
JOINT_SUFFIX = {"hip": "hip_pitch_joint", "knee": "knee_joint", "ankle": "ankle_pitch_joint", "shoulder": "shoulder_pitch_joint", "elbow": "elbow_joint", "wrist": "wrist_roll_joint"}


def angle(a, b):
    denominator = np.linalg.norm(a, axis=-1) * np.linalg.norm(b, axis=-1)
    cosine = np.divide(np.sum(a * b, axis=-1), denominator, out=np.full(denominator.shape, np.nan), where=denominator > 1e-8)
    return np.arccos(np.clip(cosine, -1, 1))


def descriptors(points, up_axis=2):
    """Length/rotation invariant limb angles and signed vertical/outward ratios."""
    p = {name: points[:, i] for i, name in enumerate(POINTS)}
    hips = (p["left_hip"] + p["right_hip"]) / 2
    shoulders = (p["left_shoulder"] + p["right_shoulder"]) / 2
    torso = shoulders - hips
    lateral = p["left_shoulder"] - p["right_shoulder"]
    lateral = lateral / np.maximum(np.linalg.norm(lateral, axis=-1, keepdims=True), 1e-8)
    values = {}
    for side, sign in (("left", 1), ("right", -1)):
        hip, knee, ankle, shoulder, elbow, wrist = [p[f"{side}_{part}"] for part in ("hip", "knee", "ankle", "shoulder", "elbow", "wrist")]
        arm = np.linalg.norm(shoulder - elbow, axis=-1) + np.linalg.norm(elbow - wrist, axis=-1)
        leg = np.linalg.norm(hip - knee, axis=-1) + np.linalg.norm(knee - ankle, axis=-1)
        values[f"{side}_elbow_flexion_rad"] = np.pi - angle(shoulder - elbow, wrist - elbow)
        values[f"{side}_knee_flexion_rad"] = np.pi - angle(hip - knee, ankle - knee)
        values[f"{side}_upper_arm_torso_rad"] = angle(elbow - shoulder, torso)
        values[f"{side}_thigh_torso_rad"] = angle(knee - hip, torso)
        values[f"{side}_wrist_height_shoulder_units"] = (wrist[:, up_axis] - shoulder[:, up_axis]) / np.maximum(arm, 1e-8)
        values[f"{side}_ankle_height_hip_units"] = (ankle[:, up_axis] - hip[:, up_axis]) / np.maximum(leg, 1e-8)
        values[f"{side}_wrist_outward_shoulder_units"] = sign * np.sum((wrist - shoulder) * lateral, axis=-1) / np.maximum(arm, 1e-8)
    values.update(body_frame_descriptors(points, up_axis))
    return values


def csv_rows(path):
    with Path(path).open() as stream:
        return list(csv.DictReader(stream))


def timing_audit(extraction, physical):
    """Pair native playing ticks with exact ordered recorded SMPL data.

    A missing row, skipped prefix, pause or changed reference is rejected, never
    repaired by searching a best alignment. Frame zero is the recorded prefix,
    including the explicit warmup; sample identities prove the correspondence.
    """
    manifest = json.loads((physical / "execution-manifest.json").read_text())
    reference = np.load(extraction / "sonic-reference.npz")
    if sha256(extraction / "sonic-reference.npz") != manifest["reference_sha256"]:
        raise ValueError("Consumed reference identity changed")
    recordings = list((physical / "reference/recorded_motion").glob("*/streamed_*/smpl_joint.csv"))
    if len(recordings) != 1:
        raise ValueError(f"Expected one native SMPL recording, found {len(recordings)}")
    recorded = np.loadtxt(recordings[0], delimiter=",", skiprows=1, ndmin=2).reshape(-1, 24, 3)
    recorded_q = np.loadtxt(recordings[0].with_name("body_quat.csv"), delimiter=",", skiprows=1, ndmin=2)
    mode = csv_rows(physical / "controller-csv/encoder_mode.csv")
    plays = csv_rows(physical / "controller-csv/motion_playing.csv")
    motion_names = csv_rows(physical / "controller-csv/motion_name.csv")
    by_index = lambda rows: {int(row["index"]): row for row in rows}
    play_index, name_index = by_index(plays), by_index(motion_names)
    ticks = []
    for row in mode:
        key = int(row["index"])
        play, name = play_index.get(key), name_index.get(key)
        if play is None or name is None:
            raise ValueError("Native mode/play/name logger indices differ")
        if float(list(row.values())[-1]) == 2 and float(list(play.values())[-1]) == 1 and name["motion_name"] == "streamed":
            ticks.append(row)
    if not len(recorded) or len(ticks) != len(recorded) or len(recorded_q) != len(recorded):
        raise ValueError(f"Native playing ticks/SMPL/quaternion counts differ: {len(ticks)}/{len(recorded)}/{len(recorded_q)}")
    warmup, future = manifest["warmup_frames"], manifest["future_context_padding_frames"]
    source = reference["smpl_joints"]
    quats = reference["body_quat"]
    padded = np.concatenate((np.repeat(source[:1], warmup, axis=0), source, np.repeat(source[-1:], future, axis=0)))
    padded_q = np.concatenate((np.repeat(quats[:1], warmup, axis=0), quats, np.repeat(quats[-1:], future, axis=0)))
    if len(recorded) > len(padded):
        raise ValueError("Recorded sequence exceeds the full transmitted cache")
    error = float(np.max(np.abs(recorded - padded[:len(recorded)])))
    quat_error = float(np.max(np.abs(recorded_q - padded_q[:len(recorded)])))
    if error > 2e-6 or quat_error > 2e-6:
        raise ValueError(f"Recorded sequence does not match the transmitted prefix: joints={error}, quaternion={quat_error}")
    times = np.array([float(row["time_monotonic_ms"]) / 1000 for row in ticks])
    indices = np.array([int(row["index"]) for row in ticks])
    if not np.all(np.diff(times) > 0) or not np.all(np.diff(indices) == 1):
        raise ValueError("Native active tick clock/index is discontinuous")
    if len(times) <= warmup:
        raise ValueError("No source samples reached after warmup")
    available = min(len(source), len(times) - warmup)
    source_times = times[warmup:warmup + available]
    expected = reference["timestamps"][:available]
    offsets = source_times - source_times[0] - expected
    report = {"status": "passed", "scope": "Ordered reference identity and native controller clock; no fitted alignment", "recorded_frames": len(recorded), "verified_source_frames": available, "expected_source_frames": len(source), "full_source_consumed": available == len(source), "maximum_recorded_joint_error_m": error, "maximum_recorded_quaternion_error": quat_error, "source_zero_monotonic": float(source_times[0]), "clock_offset_median_seconds": float(np.median(offsets)), "clock_offset_p95_abs_seconds": float(np.percentile(np.abs(offsets), 95)), "clock_offset_max_abs_seconds": float(np.max(np.abs(offsets))), "time_shift_fitted": False, "recording": str(recordings[0])}
    return report, source_times, expected, source[:available]


def actual_points(physical, query_times):
    import mujoco
    config = json.loads((physical / "simulation-config.json").read_text())
    scene = SONIC / config["wbc_config"]["ROBOT_SCENE"]
    model = mujoco.MjModel.from_xml_path(str(scene))
    data = mujoco.MjData(model)
    anchors = [model.joint(f"{name.split('_')[0]}_{JOINT_SUFFIX[name.split('_')[1]]}").id for name in POINTS]
    with np.load(physical / "actual-state.npz") as states:
        stamps, qpos = states["monotonic"], states["qpos"]
        if qpos.shape[1] != model.nq or not np.all(np.diff(stamps) > 0):
            raise ValueError("Recorded actual state shape/clock differs from scene")
        right = np.clip(np.searchsorted(stamps, query_times), 0, len(stamps) - 1)
        left = np.maximum(right - 1, 0)
        selected = np.where(abs(stamps[left] - query_times) <= abs(stamps[right] - query_times), left, right)
        gap = abs(stamps[selected] - query_times)
        valid = (query_times >= stamps[0]) & (query_times <= stamps[-1]) & (gap <= .015)
        positions = np.full((len(query_times), len(POINTS), 3), np.nan)
        for i in np.flatnonzero(valid):
            data.qpos[:] = qpos[selected[i]]  # Offline actual-state FK only.
            mujoco.mj_forward(model, data)
            positions[i] = data.xanchor[anchors]
    return positions, valid, {"scene": str(scene), "scene_sha256": sha256(scene), "actual_state_sha256": sha256(physical / "actual-state.npz"), "maximum_nearest_sample_gap_seconds": float(np.max(gap)), "maximum_allowed_gap_seconds": .015, "recorded_state_fk_only": True}


def evaluate_events(annotation, source_times, human, robot, valid):
    """Independently find extrema in predefined source windows; do not shift video."""
    if annotation is None:
        return {"status": "awaiting_verification", "reason": "Source key events have not been annotated/frozen"}
    events = annotation["events"]
    if len({event["id"] for event in events}) != len(events) or any(a["source_event_seconds"] >= b["source_event_seconds"] for a, b in zip(events, events[1:])):
        raise ValueError("Key events must have unique IDs and increasing source times")
    results = []
    for event in events:
        name = event["feature"]
        start, end = event["window_seconds"]
        if name not in human or start < 0 or end <= start or not start <= event["source_event_seconds"] <= end or event["extremum"] not in ("max", "min"):
            raise ValueError(f"Invalid key-event annotation: {event['id']}")
        window = (source_times >= start) & (source_times <= end)
        ids = np.flatnonzero(window)
        row = {"id": event["id"], "description": event["description"], "feature": name, "window_seconds": [start, end]}
        step = float(np.median(np.diff(source_times))) if len(source_times) > 1 else 0
        if len(ids) < 2 or source_times[0] > start + step or source_times[-1] < end - step or not valid[ids].all():
            results.append({**row, "status": "failed", "reason": "Event window lacks complete actual state coverage"})
            continue
        sign = 1 if event["extremum"] == "max" else -1
        human_index = ids[np.argmax(sign * human[name][ids])]
        robot_index = ids[np.argmax(sign * robot[name][ids])]
        source_value, actual_value = float(human[name][human_index]), float(robot[name][robot_index])
        threshold = event["threshold"]
        source_correct = sign * source_value >= sign * threshold
        robot_correct = sign * actual_value >= sign * threshold
        row.update({"status": "passed" if source_correct and robot_correct else "failed", "extracted_direction_correct": bool(source_correct), "robot_direction_correct": bool(robot_correct), "extracted_peak_value": source_value, "robot_peak_value": actual_value, "extracted_event_seconds": float(source_times[human_index]), "robot_event_seconds": float(source_times[robot_index]), "robot_minus_extracted_event_seconds": float(source_times[robot_index] - source_times[human_index]), "source_annotation_event_seconds": event["source_event_seconds"], "extracted_minus_annotation_seconds": float(source_times[human_index] - event["source_event_seconds"]), "robot_minus_annotation_seconds": float(source_times[robot_index] - event["source_event_seconds"])})
        results.append(row)
    ordered = all(a.get("robot_event_seconds", np.inf) < b.get("robot_event_seconds", -np.inf) for a, b in zip(results, results[1:]))
    return {"status": "passed" if results and ordered and all(row["status"] == "passed" for row in results) else "failed", "robot_event_order_correct": bool(ordered), "events": results, "time_shift_fitted": False}


def run(args):
    storage_check(args.output)
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"status": "awaiting_verification", "scope": "R2 body geometry/timing/key-event audit; extracted human is not 3D ground truth", "body_error_acceptance_threshold": None, "body_error_is_reporting_only": True, "joint_pos_zero_field_used_as_target": False, "time_shift_fitted": False, "evaluator_sha256": sha256(__file__), "geometry_helper_sha256": sha256(Path(__file__).with_name("r2_geometry.py")), "twist_error_wrap": "[-pi,pi)"}
    try:
        physical = json.loads((args.physical / "physical-metrics.json").read_text())
        report["physical_status"] = physical["status"]
        if physical["status"] == "failed":
            report["status"] = "failed"
        timing, monotonic, source_times, joints = timing_audit(args.extraction, args.physical)
        report["timing"] = timing
        points, valid, provenance = actual_points(args.physical, monotonic)
        # SMPL root-local coordinates cannot supply world-up heights; use only
        # invariant angles here, then rotate by the streamed root quaternion.
        from scipy.spatial.transform import Rotation
        with np.load(args.extraction / "sonic-reference.npz") as reference:
            q = reference["body_quat"][:len(joints)]
            human_world = np.einsum("tij,tkj->tki", Rotation.from_quat(q[:, [1, 2, 3, 0]]).as_matrix(), joints)
        human = descriptors(human_world[:, SMPL_INDICES])
        robot = descriptors(points)
        errors = {}
        for name in human:
            mask = valid & np.isfinite(human[name]) & np.isfinite(robot[name])
            difference = descriptor_difference(name, robot[name][mask], human[name][mask])
            errors[name] = {"samples": int(mask.sum()), "rmse": float(np.sqrt(np.mean(difference**2))) if len(difference) else None, "mae": float(np.mean(abs(difference))) if len(difference) else None, "units": "rad" if name.endswith("_rad") else "limb_length_ratio"}
        finite = valid.any() and all(np.isfinite(human[name][valid]).all() and np.isfinite(robot[name][valid]).all() for name in human)
        report["body_error"] = {"status": "passed" if finite else "failed", "scope": "Measured robot/extracted human descriptors on verified consumed ticks; morphology differs", "per_feature": errors, "all_covered_descriptors_finite": bool(finite), "actual_state_coverage_fraction": float(valid.mean()), "provenance": provenance}
        annotation = json.loads(args.events.read_text()) if args.events else None
        if annotation and annotation["source_sha256"] != sha256(args.extraction / "source-original.mp4"):
            raise ValueError("Event annotation belongs to a different source")
        report["key_events"] = evaluate_events(annotation, source_times, human, robot, valid)
        report["event_annotation_sha256"] = sha256(args.events) if args.events else None
        if physical["status"] == "failed" or report["key_events"]["status"] == "failed" or report["body_error"]["status"] == "failed":
            report["status"] = "failed"
        elif physical["status"] == "passed" and timing["full_source_consumed"] and valid.all() and report["key_events"]["status"] == "passed":
            report["status"] = "passed"
        np.savez_compressed(args.output / "body-descriptors.npz", source_seconds=source_times, controller_monotonic=monotonic, actual_valid=valid, feature_names=np.array(list(human)), extracted=np.stack(list(human.values()), axis=-1), actual=np.stack(list(robot.values()), axis=-1))
    except FileNotFoundError as error:
        report["reason"] = str(error)
        report["verification_incomplete"] = True
    except (ValueError, KeyError, IndexError) as error:
        report.update({"status": "failed", "reason": str(error), "verification_incomplete": True})
    write_json(args.output / "body-evaluation.json", report)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--physical", type=Path, required=True)
    parser.add_argument("--events", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(run(parser.parse_args()))
