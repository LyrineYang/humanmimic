"""Debug-only startup ablation; preserve the original reference after a fixed prefix.

This is not the R2 suite entry point. It adds two seconds of initialization to
an existing debug extraction and optionally tests it after recorded tasks end.
No model inference, source video editing or acceptance-rule changes occur.
"""

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess

import numpy as np
from scipy.spatial.transform import Rotation

from r2_common import PROJECT, sha256, storage_check, write_json

PREFIX = 100
CHAINS = ((1, 4, 7, 10), (2, 5, 8, 11))


def direction_path(start, end, fraction):
    """Shortest unit-vector arc, including parallel and antipodal cases."""
    dot = np.clip(start @ end, -1., 1.)
    angle = np.arccos(dot)
    tangent = end - dot * start
    norm = np.linalg.norm(tangent)
    if norm < 1e-10:
        basis = np.eye(3)[np.argmin(abs(start))]
        tangent = basis - (basis @ start) * start
        norm = np.linalg.norm(tangent)
    tangent /= norm
    result = np.cos(fraction[:, None] * angle) * start + np.sin(fraction[:, None] * angle) * tangent
    result[0], result[-1] = start, end
    return result


def neutral_leg_prefix(first, quaternion):
    first = np.asarray(first, dtype=np.float64)
    if first.shape != (24, 3) or not np.isfinite(first).all():
        raise ValueError("Expected finite SMPL24 positions")
    quaternion = np.asarray(quaternion, dtype=np.float64)
    if quaternion.shape != (4,) or not np.isfinite(quaternion).all() or abs(np.linalg.norm(quaternion) - 1) > 1e-5:
        raise ValueError("Expected unit wxyz orientation")
    rotation = Rotation.from_quat(quaternion[[1, 2, 3, 0]])
    left = rotation.apply(first[1] - first[2])
    left[2] = 0
    if np.linalg.norm(left) < 1e-8:
        raise ValueError("Cannot infer horizontal hip axis")
    left /= np.linalg.norm(left)
    down = rotation.inv().apply([0., 0., -1.])
    forward = rotation.inv().apply(np.cross(left, [0., 0., 1.]))
    u = np.linspace(0., 1., PREFIX)
    fraction = u * u * (3 - 2 * u)
    result = np.repeat(first[None], PREFIX, axis=0)
    for chain in CHAINS:
        for segment, (parent, child) in enumerate(zip(chain, chain[1:])):
            vector = first[child] - first[parent]
            length = np.linalg.norm(vector)
            if length < 1e-8:
                raise ValueError("Degenerate lower-limb segment")
            neutral = forward if segment == 2 else down
            result[:, child] = result[:, parent] + length * direction_path(neutral, vector / length, fraction)
    result[-1] = first
    return result


def prepare(extraction, output):
    identity = json.loads((extraction / "input.json").read_text())
    if identity["role"] != "debug":
        raise ValueError("Startup development is limited to debug inputs")
    source_path = extraction / "sonic-reference.npz"
    conversion = json.loads((extraction / "conversion.json").read_text())
    if conversion["control_fps"] != 50:
        raise ValueError("Diagnostic requires the existing 50Hz reference")
    with np.load(source_path) as loaded:
        source = {key: loaded[key] for key in loaded.files}
    count = len(source["timestamps"])
    if any(value.ndim == 0 or len(value) != count for value in source.values()):
        raise ValueError("Unexpected reference field layout")
    prefix = neutral_leg_prefix(source["smpl_joints"][0], source["body_quat"][0])
    combined = {name: np.concatenate((np.repeat(value[:1], PREFIX, axis=0), value)) for name, value in source.items()}
    combined["smpl_joints"][:PREFIX] = prefix.astype(source["smpl_joints"].dtype)
    combined["timestamps"] = np.arange(count + PREFIX, dtype=np.float64) / 50
    combined["frame_index"] = np.arange(count + PREFIX, dtype=np.int64)
    preserved = {name: np.array_equal(value, combined[name][PREFIX:]) for name, value in source.items() if name not in ("timestamps", "frame_index")}
    if not all(preserved.values()):
        raise ValueError("An original motion sample changed")
    max_bone_error = 0.
    for chain in CHAINS:
        for parent, child in zip(chain, chain[1:]):
            expected = np.linalg.norm(source["smpl_joints"][0, child] - source["smpl_joints"][0, parent])
            observed = np.linalg.norm(combined["smpl_joints"][:PREFIX, child] - combined["smpl_joints"][:PREFIX, parent], axis=-1)
            max_bone_error = max(max_bone_error, float(np.max(abs(observed - expected))))
    if max_bone_error > 1e-6:
        raise ValueError("Reference transition changed lower-limb bone lengths")
    destination = output / "reference"
    destination.mkdir(exist_ok=False)
    np.savez_compressed(destination / "sonic-reference.npz", **combined)
    write_json(destination / "conversion.json", {**conversion, "scope": "Diagnostic reference includes initialization; not canonical video extraction", "control_frames": count + PREFIX, "source_duration_seconds": (count + PREFIX) / 50, "diagnostic_prefix_frames": PREFIX, "original_reference": str(source_path), "original_reference_sha256": sha256(source_path), "original_source_frames": count, "original_source_time_offset_seconds": PREFIX / 50})
    result = {"status": "passed", "scope": "Reference preparation only; not physical acceptance", "source_video_sha256": identity["input_sha256"], "original_reference_sha256": sha256(source_path), "derived_reference_sha256": sha256(destination / "sonic-reference.npz"), "script_sha256": sha256(__file__), "original_motion_fields_exact_after_prefix": preserved, "source_samples_unchanged": count, "fixed_prefix_frames": PREFIX, "fixed_prefix_seconds": PREFIX / 50, "maximum_lower_limb_bone_length_error_m": max_bone_error, "upper_body": "unchanged first pose throughout prefix", "orientation": "unchanged first quaternion throughout prefix", "interpolation": "smoothstep progress on shortest bone-direction arcs; no source retiming", "cloud_cost_usd": 0}
    write_json(output / "preparation.json", result)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute-after-task", type=Path, nargs="+", help="Run one diagnostic physics trial only after these recorded queues exit")
    args = parser.parse_args()
    storage_check(args.output)
    args.output.mkdir(parents=True, exist_ok=True)
    if not (args.output / "expectation.json").is_file():
        parser.error("Record the expected diagnostic before preparation/execution")
    destination = prepare(args.extraction.resolve(), args.output.resolve())
    if not args.execute_after_task:
        print((args.output / "preparation.json").read_text())
        raise SystemExit(0)
    spec = importlib.util.spec_from_file_location("r2_diagnostic_queue", PROJECT / "scripts/run-r2-suite.py")
    pipeline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pipeline)
    execution_script = sha256(PROJECT / "scripts/run-r2-physical.py")
    for task in args.execute_after_task:
        pipeline.wait_for_recorded_task(task, pose_required=False)
    pipeline.throughput_policy()
    if pipeline.active_tasks():
        raise RuntimeError("Another pipeline is still active")
    original_execution = json.loads((args.extraction.parent / "physical/execution-manifest.json").read_text())
    if execution_script != sha256(PROJECT / "scripts/run-r2-physical.py") or execution_script != original_execution["r2_script_sha256"]:
        raise RuntimeError("Physical runner changed since the original debug failure")
    binary = pipeline.SONIC / "gear_sonic_deploy/target/release/g1_deploy_onnx_ref"
    gpu = subprocess.check_output(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"], text=True).strip()
    if sha256(binary) != original_execution["binary_sha256"] or gpu != original_execution["gpu"]:
        raise RuntimeError("Controller or hardware differs from the original debug failure")
    if sha256(PROJECT / "scripts/run-r1-reproduction.py") != original_execution["r1_simulator_sha256"]:
        raise RuntimeError("Simulator differs from the original debug failure")
    for name, digest in original_execution["immutable_model_hashes_equal_r1"].items():
        if sha256(Path(original_execution["model_root"]) / name) != digest:
            raise RuntimeError("Policy weights differ from the original debug failure")
    physical = args.output / "physical"
    code = pipeline.step(args.output, "physical", "r1", "run-r2-physical.py", ["--reference", destination / "sonic-reference.npz", "--output", physical])
    metrics = json.loads((physical / "physical-metrics.json").read_text())
    consumed = metrics.get("source_clock", {}).get("verified_source_frames", 0)
    result = {"status": metrics["status"], "scope": "Debug startup ablation only; not a new suite acceptance result", "physical_exit_code": code, "original_failure_preserved": True, "initialization_prefix_frames": PREFIX, "original_source_frames_consumed": max(0, consumed - PREFIX), "fell": metrics.get("fell"), "minimum_root_height_m": metrics.get("minimum_root_height_m"), "actual_state_sha256": sha256(physical / "actual-state.npz"), "preparation": str(args.output / "preparation.json"), "cloud_cost_usd": 0}
    write_json(args.output / "diagnostic-result.json", result)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "passed" else 1)
