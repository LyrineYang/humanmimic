"""Compare one complete debug detection cache with fixed CPU thread scheduling.

Writes candidate artifacts separately. Never enables a pipeline setting or
touches the original extraction; any changed output fails the comparison.
"""

import argparse
from dataclasses import asdict
import importlib.util
import json
import os
from pathlib import Path
import resource
import time
from unittest.mock import patch

from r2_common import PROJECT, sha256, storage_check, write_json


def run(args):
    storage_check(args.output)
    spec = importlib.util.spec_from_file_location("r2_cpu_comparison_queue", PROJECT / "scripts/run-r2-suite.py")
    pipeline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pipeline)
    pipeline.throughput_policy()
    if args.wait_for_task:
        pipeline.wait_for_recorded_task(args.wait_for_task, pose_required=False)
    if pipeline.active_tasks():
        raise RuntimeError("Another pipeline is active; comparison must remain serial")
    identity = json.loads((args.extraction / "input.json").read_text())
    if identity["role"] != "debug":
        raise ValueError("Performance development must use debug data")
    before = {name: sha256(args.extraction / name) for name in ("tracks.pt", "normalized.mp4", "input.json")}
    for stage in ("prepare", "detect"):
        saved = json.loads((args.extraction / f"{stage}-complete.json").read_text())
        for name in set(before) & saved["sha256"].keys():
            if before[name] != saved["sha256"][name]:
                raise ValueError("Original detection/video cache changed")
    config = json.loads((args.extraction / "resolved-model-config.json").read_text())
    model = Path(config["detector"]["checkpoint"])
    if (args.output / "candidate-tracks.pt").exists():
        raise ValueError("Preserve prior candidate; use a new output directory")
    began = time.monotonic()
    import numpy as np
    import onnxruntime as ort
    import torch
    from gem.common.detectors import YOLOXONNX, detect_track
    from gem.inference.video import VideoFrames

    torch.set_num_threads(8)
    original_options = ort.SessionOptions

    def fixed_options():
        options = original_options()
        options.intra_op_num_threads = 8
        options.inter_op_num_threads = 1
        return options

    loading = time.monotonic()
    with patch.object(ort, "SessionOptions", fixed_options):
        detector = YOLOXONNX(model, device="cpu")
    model_load_seconds = time.monotonic() - loading
    frame_count = 0
    inference_began = time.monotonic()

    class MeasuredDetector:
        def detect(self, frame):
            nonlocal frame_count
            value = detector.detect(frame)
            frame_count += 1
            if frame_count % 32 == 0:
                write_json(args.output / "progress.json", {"status": "awaiting_verification", "frames": frame_count, "detect_seconds": time.monotonic() - inference_began, "pid": os.getpid(), "model_device": "cpu"})
            return value

    with VideoFrames(args.extraction / "normalized.mp4") as frames:
        candidate = asdict(detect_track(frames, MeasuredDetector()))
        expected_frames = len(frames)
    detect_seconds = time.monotonic() - inference_began
    torch.save(candidate, args.output / "candidate-tracks.pt")
    baseline = torch.load(args.extraction / "tracks.pt", map_location="cpu", weights_only=False)
    mismatches, checked_arrays = [], 0

    def equal(a, b, path):
        nonlocal checked_arrays
        if isinstance(a, torch.Tensor):
            a = a.numpy()
        if isinstance(b, torch.Tensor):
            b = b.numpy()
        if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
            checked_arrays += 1
            ok = isinstance(a, np.ndarray) and isinstance(b, np.ndarray) and a.dtype == b.dtype and np.array_equal(a, b)
        elif isinstance(a, dict) and isinstance(b, dict):
            ok = a.keys() == b.keys()
            for key in a.keys() & b.keys():
                equal(a[key], b[key], f"{path}/{key}")
        elif isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
            ok = type(a) is type(b) and len(a) == len(b)
            for index, (left, right) in enumerate(zip(a, b)):
                equal(left, right, f"{path}/{index}")
        else:
            ok = type(a) is type(b) and a == b
        if not ok:
            mismatches.append(path)

    equal(baseline, candidate, "tracks")
    after = {name: sha256(args.extraction / name) for name in before}
    if before != after or frame_count != expected_frames:
        raise ValueError("Source/cache identity or full-frame coverage changed")
    profiles = [json.loads(path.read_text()) for path in args.extraction.glob("detect-attempt-*.json")]
    baseline_seconds = next(value["wall_seconds"] for value in reversed(profiles) if value["status"] == "passed")
    wall_seconds = time.monotonic() - began
    report = {"status": "failed" if mismatches else "passed", "scope": "Full-debug-clip CPU detection/tracking equality and scheduling measurement only; no R2 physical acceptance", "script_sha256": sha256(__file__), "source_video_sha256": identity["input_sha256"], "original_cache_sha256": before, "original_cache_unchanged": before == after, "model_sha256": sha256(model), "provider": detector.execution_providers, "intra_op_num_threads": 8, "inter_op_num_threads": 1, "frames_verified": frame_count, "all_output_fields_exact": not mismatches, "leaf_arrays_compared": checked_arrays, "mismatch_count": len(mismatches), "first_mismatch_paths": mismatches[:20], "model_load_seconds": model_load_seconds, "decode_detection_tracking_seconds": detect_seconds, "candidate_wall_seconds": wall_seconds, "baseline_worker_wall_seconds": baseline_seconds, "candidate_faster_than_baseline_worker": wall_seconds < baseline_seconds, "timing_comparison_includes_different_import_cache_states": True, "maximum_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024, "pipeline_setting_enabled": False, "heldout_used": False, "cloud_cost_usd": 0}
    write_json(args.output / "comparison.json", report)
    print(json.dumps(report, indent=2), flush=True)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wait-for-task", type=Path)
    args = parser.parse_args()
    if not (args.output / "expectation.json").exists():
        parser.error("Record the expected comparison before execution")
    raise SystemExit(run(args))
