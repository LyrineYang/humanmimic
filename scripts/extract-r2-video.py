"""Full-source video -> cached GEM-X stages -> SOMA/SMPL references, on local R2."""

import argparse
from dataclasses import asdict
import fcntl
from fractions import Fraction
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

from r2_common import GEMX, PROJECT, SONIC, STORAGE, run_profiled, sha256, storage_check, write_json

STAGES = ("prepare", "detect", "features", "pose2d", "camera", "motion", "postprocess", "convert")
OUTPUTS = {"prepare": ["source.json", "source-pts.json", "frame-time-mapping.json", "normalized.mp4", "source-framehash.csv", "selected-framehash.csv", "selected-frame-mapping.json", "normalization-command.json"], "detect": ["tracks.pt"], "features": ["features.pt"], "pose2d": ["keypoints2d.pt"], "camera": ["camera.pt"], "motion": ["motion-raw.pt"], "postprocess": ["motion-processed.pt"], "convert": ["soma-joints.npz", "smpl-source.npz", "sonic-reference.npz", "conversion.json"]}


def tensor_load(path):
    import torch
    return torch.load(path, map_location="cpu", weights_only=False)


def save_tensor(path, value):
    import torch
    from gem.inference.serialization import tensor_tree
    temporary = path.with_suffix(".tmp.pt")
    torch.save(tensor_tree(value), temporary)
    os.replace(temporary, path)


def configuration():
    # Same path resolution as the pinned official loader, without importing
    # every perception model in CPU-only workers.
    from gem.inference.inputs import load_mapping
    path = (GEMX / "docs/configs/body_video_native77.yaml").resolve()
    config = load_mapping(path)
    for section, keys in (("pose", ("checkpoint",)), ("observations", ("checkpoint",)), ("detector", ("checkpoint",)), ("motion", ("checkpoint", "stats")), ("camera", ("rotations",))):
        for key in keys:
            value = config.get(section, {}).get(key)
            if value is not None:
                config[section][key] = str((path.parent / value).resolve())
    for section, filename in [("pose", "body_s240000.ckpt"), ("observations", "vitpose.pth"), ("detector", "yolox_humanart.onnx"), ("motion", "motion_native77_e774_s292175.ckpt")]:
        config[section]["checkpoint"] = str(STORAGE / "models/gem-x" / filename)
    config["motion"]["stats"] = str(STORAGE / "models/gem-x/motion_stats_raw.npz")
    config["pose"]["batch_size"] = 1
    config["observations"]["batch_size"] = 1
    config["detector"]["device"] = "cpu"
    from r2_detection import INTRA_THREADS, INTER_THREADS
    config["detector"]["intra_op_num_threads"] = INTRA_THREADS
    config["detector"]["inter_op_num_threads"] = INTER_THREADS
    config["camera"]["mode"] = "static"
    return config


def worker(stage, output):
    import numpy as np
    from gem.inference.video import VideoFrames
    config = configuration()
    if stage in ("postprocess", "convert"):
        import warp as wp
        wp.config.kernel_cache_dir = str(STORAGE / "cache/warp")
    source = output / "source-original.mp4"
    normalized = output / "normalized.mp4"
    if stage == "prepare":
        info = json.loads((output / "input.json").read_text())
        original = Path(info["input"]).resolve()
        if not source.exists():
            try:
                os.link(original, source)
            except OSError:
                shutil.copy2(original, source)
        probe = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames", "-show_streams", "-show_entries", "stream=time_base:frame=best_effort_timestamp,best_effort_timestamp_time,pkt_duration_time,duration_time", "-of", "json", str(source)], text=True)
        source_frames = json.loads(probe)
        write_json(output / "source-pts.json", source_frames)
        source_pts = np.array([float(frame["best_effort_timestamp_time"]) for frame in source_frames["frames"]])
        if len(source_pts) < 2 or not np.all(np.diff(source_pts) > 0):
            raise ValueError("Source requires at least two frames with increasing timestamps")
        if source_pts[-1] - source_pts[0] >= 60:
            raise ValueError("Source exceeds the current <=60s workflow; do not silently trim it")
        with VideoFrames(source) as frames:
            original_meta = {"path": str(source), "frame_count": len(frames), "fps": frames.fps, "width": frames.width, "height": frames.height, "duration": len(frames) / frames.fps, "first_pts": float(source_pts[0]), "last_pts": float(source_pts[-1]), "selected_interval": "entire source; no -ss/-t"}
        # Keep the full VFR source; duration estimated as frame_count/fps must
        # never become an ffmpeg -t cutoff. Retain original PTS separately.
        from r2_timeline import normalize
        exact_mapping = normalize(source, output)
        source_integer_pts = [int(frame["best_effort_timestamp"]) for frame in source_frames["frames"]]
        source_tb = Fraction(source_frames["streams"][0]["time_base"])
        filter_tb = Fraction(exact_mapping["source_time_base"])
        if len(source_integer_pts) != exact_mapping["source_frames"] or any((pts - source_integer_pts[0]) * source_tb != raw * filter_tb for pts, raw in zip(source_integer_pts, exact_mapping["source_pts_after_startpts"])):
            raise ValueError("Raw filter PTS do not correspond to original source integer timestamps")
        with VideoFrames(normalized) as frames:
            normalized_meta = {"path": str(normalized), "frame_count": len(frames), "fps": frames.fps, "width": frames.width, "height": frames.height, "duration": len(frames) / frames.fps}
            times = np.arange(len(frames), dtype=np.float64) / 30
        if normalized_meta["duration"] + 1 / 30 < source_pts[-1] - source_pts[0]:
            raise ValueError("Normalized video failed to cover the original final timestamp")
        if normalized_meta["frame_count"] != exact_mapping["normalized_frames"]:
            raise ValueError("Encoded normalized video frame count differs from selected-frame proof")
        mapped = np.clip(np.searchsorted(source_pts - source_pts[0], times, side="right") - 1, 0, len(source_pts) - 1)
        write_json(output / "frame-time-mapping.json", {"normalized_fps": 30, "original_pts_origin": float(source_pts[0]), "original_integer_pts": source_integer_pts, "original_time_base": str(source_tb), "normalized_times": times.tolist(), "selected_source_frame_indices": exact_mapping["selected_source_frame_indices"], "selection_proof": "selected-frame-mapping.json and input/output raw-frame hashes", "preceding_source_frame_indices": mapped.tolist(), "source_pts": source_pts.tolist(), "content_trimmed": False, "time_shift_fitted": False})
        metadata = {"source": original_meta, "normalized": normalized_meta}
        write_json(output / "source.json", {**metadata, "url": info.get("source_url"), "sha256": sha256(source), "role": info["role"], "content_trimmed": False})
        write_json(output / "resolved-model-config.json", config)
        return
    if stage == "pose2d":
        # The master owns extraction.lock for the lifetime of this worker.
        # Preserve the producer's model/crops/precision; only schedule cohorts.
        import importlib.util
        spec = importlib.util.spec_from_file_location("r2_cooled_producer", PROJECT / "scripts/run-r2-checkpoint-recovery.py")
        recovery = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(recovery)
        with VideoFrames(normalized) as frames:
            cohorts = (len(frames) + 95) // 96 + 1
        options = argparse.Namespace(extraction=output, max_new_chunks=3, cycles=cohorts, maximum_temperature_c=60)
        code = recovery.main(options, lock_held=True)
        if code:
            raise RuntimeError("Cooled pose cohort stopped before full completion; checkpoints retained")
        return
    import torch
    torch.set_num_threads(8)
    if stage == "detect":
        from gem.common.detectors import detect_track
        from r2_detection import load_cpu_detector
        with VideoFrames(normalized) as frames:
            detector = load_cpu_detector(config["detector"]["checkpoint"])
            tracks = detect_track(frames, detector)
        save_tensor(output / "tracks.pt", asdict(tracks))
    elif stage == "features":
        from gem.inference.body_video import body_release, extract_body_features, motion_intrinsics
        from gem.pose.api import load_pose_checkpoint
        tracks = tensor_load(output / "tracks.pt")
        model = load_pose_checkpoint(config["pose"]["checkpoint"], body_release(config), device="cuda")
        with VideoFrames(normalized) as frames:
            intrinsics = motion_intrinsics(frames.width, frames.height)
            values, release = extract_body_features(frames, tracks["boxes_xys"], intrinsics, model, batch_size=1, device="cuda")
        save_tensor(output / "features.pt", {"values": values, "feature_version": release})
    elif stage == "camera":
        from gem.inference.camera_motion import camera_motion
        tracks = tensor_load(output / "tracks.pt")
        keypoints = tensor_load(output / "keypoints2d.pt")
        with VideoFrames(normalized) as frames:
            # Identical diagonal-focal construction to official motion_intrinsics.
            focal = float(np.hypot(frames.width, frames.height))
            intrinsics = torch.tensor([[focal, 0, frames.width / 2], [0, focal, frames.height / 2], [0, 0, 1]])
            camera = camera_motion(frames, intrinsics.numpy(), tracks["boxes_xyxy"], mode="static", keypoints=keypoints.numpy())
        save_tensor(output / "camera.pt", {**camera, "K_fullimg": intrinsics})
    elif stage == "motion":
        from gem.inference.motion import load_predictor, run_motion
        tracks = tensor_load(output / "tracks.pt")
        keypoints = tensor_load(output / "keypoints2d.pt")
        features = tensor_load(output / "features.pt")
        camera = tensor_load(output / "camera.pt")
        length = len(keypoints)
        sequence = {"condition_spec": config["motion"]["condition_spec"], "length": torch.tensor([length]), "f_imgseq": features["values"].unsqueeze(0), "kp2d_native77": keypoints.unsqueeze(0), "bbx_xys": torch.as_tensor(tracks["boxes_xys"]).unsqueeze(0), "K_fullimg": camera["K_fullimg"].expand(1, length, 3, 3).clone(), "cam_angvel": camera["cam_angvel"].unsqueeze(0), "frame_times": (torch.arange(length, dtype=torch.float64) / 30).unsqueeze(0), "sampling_fps": 30.0}
        if features["feature_version"] != sequence["condition_spec"]["pose_release_id"]:
            raise ValueError("Body Pose features differ from the matched Motion release")
        predictor = load_predictor(config["motion"]["checkpoint"], config["motion"], stats_path=config["motion"]["stats"], device="cuda")
        with torch.inference_mode():
            result = run_motion(predictor, sequence, device="cuda")
        save_tensor(output / "motion-raw.pt", {**result, "tracking": tracks, "video": json.loads((output / "source.json").read_text()), "release": config})
    elif stage == "postprocess":
        from gem.inference.postprocess import postprocess_motion_result
        raw = tensor_load(output / "motion-raw.pt")
        result = postprocess_motion_result(raw, soma_assets=STORAGE / "models/soma-v0.3.3", device="cpu")
        save_tensor(output / "motion-processed.pt", result)
    elif stage == "convert":
        from r2_smpl import convert_motion
        convert_motion(output, tensor_load(output / "motion-processed.pt"))
    else:
        raise ValueError(stage)
    if torch.cuda.is_initialized():
        torch.cuda.synchronize()
        write_json(output / (stage + "-cuda.json"), {"peak_allocated_bytes": torch.cuda.max_memory_allocated(), "peak_reserved_bytes": torch.cuda.max_memory_reserved(), "device": torch.cuda.get_device_name()})


def run(args):
    output = args.output.resolve()
    storage_check(output)
    output.mkdir(parents=True, exist_ok=True)
    with (output / "extraction.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        input_path = args.input.resolve()
        identity = {"input": str(input_path), "input_sha256": sha256(input_path), "source_url": args.source_url, "script_sha256": sha256(__file__), "common_helper_sha256": sha256(PROJECT / "scripts/r2_common.py"), "asset_plan_sha256": sha256(STORAGE / "runs/asset-download-20261030/download-plan.json"), "gemx_revision": subprocess.check_output(["git", "-C", str(GEMX), "rev-parse", "HEAD"], text=True).strip(), "role": args.role, "camera_assumption": "fixed; source eligibility reviewed separately", "control_fps": 50, "source_content_trimmed": False}
        expected_revision = json.loads((PROJECT / "configs/r2-resources.json").read_text())["source_gemx_revision"]
        if identity["gemx_revision"] != expected_revision:
            raise ValueError("GEM-X differs from its configured source revision")
        if args.role == "heldout":
            if args.frozen_suite is None:
                raise ValueError("Heldout inference requires the frozen suite manifest")
            frozen = json.loads(args.frozen_suite.read_text())
            if frozen["status"] != "frozen" or identity["input_sha256"] not in [item["source_sha256"] for item in frozen["heldout"]]:
                raise ValueError("Input is not in the frozen heldout manifest")
            for relative, digest in frozen["source_code_sha256"].items():
                if sha256(PROJECT / relative) != digest:
                    raise ValueError(f"Frozen source changed: {relative}")
            for asset, digest in frozen["asset_sha256"].items():
                if sha256(asset) != digest:
                    raise ValueError(f"Frozen model/asset changed: {asset}")
            gpu = subprocess.check_output(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"], text=True).strip()
            if gpu != frozen["gpu_driver"]:
                raise ValueError("GPU/driver differs from the frozen suite")
            identity["frozen_suite_sha256"] = sha256(args.frozen_suite)
            identity["frozen_suite_path"] = str(args.frozen_suite.resolve())
            with (STORAGE / "runs/heldout-use-ledger.jsonl").open("a") as ledger:
                ledger.write(json.dumps({"role": "heldout", "used": True, "run": str(output), "input_sha256": identity["input_sha256"], "suite_sha256": identity["frozen_suite_sha256"], "time_unix": time.time()}) + "\n")
                ledger.flush(); os.fsync(ledger.fileno())
        identity_path = output / "input.json"
        if identity_path.exists():
            if json.loads(identity_path.read_text()) != identity:
                raise ValueError("Cache input/source identity changed; use a fresh output directory")
        else:
            write_json(identity_path, identity)
            snapshot = output / "source-snapshot"
            snapshot.mkdir()
            relative_files = [Path("scripts") / name for name in ("activate-r2.sh", "activate-r1.sh", "run-r2-demo.sh", "extract-r2-video.py", "r2_common.py", "r2_smpl.py", "r2_timeline.py", "r2_geometry.py", "r2_initialization.py", "r2_detection.py", "run-r2-physical.py", "render-r2-demo.py", "run-r1-reproduction.py", "cache-r2-pose2d.py", "run-r2-checkpoint-recovery.py", "evaluate-r2-body.py")]
            relative_files += [Path("configs") / name for name in ("r2-resources.json", "constraints-r2.txt", "r1-evaluation.json", "r1-dds.xml")]
            for relative in relative_files:
                destination = snapshot / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(PROJECT / relative, destination)
            write_json(snapshot / "sha256.json", {str(relative): sha256(PROJECT / relative) for relative in relative_files})
        for relative, digest in json.loads((output / "source-snapshot/sha256.json").read_text()).items():
            if sha256(PROJECT / relative) != digest:
                raise ValueError(f"Cached extraction source changed: {relative}; use a new run")
        profiles = []
        try:
            for stage in STAGES:
                completed = output / (stage + "-complete.json")
                if completed.exists():
                    record = json.loads(completed.read_text())
                    if stage == "convert" and record.get("helper_sha256") != sha256(PROJECT / "scripts/r2_smpl.py"):
                        raise ValueError("Completed conversion uses another helper version; preserve it and use a new run")
                    if not all((output / name).is_file() and sha256(output / name) == digest for name, digest in record["sha256"].items()):
                        raise ValueError(f"Cached {stage} output changed")
                    print(f"Verified cached stage: {stage}", flush=True)
                else:
                    profile = run_profiled([sys.executable, str(Path(__file__).resolve()), "--output", str(output), "--worker", stage], output, stage)
                    profiles.append({"stage": stage, **profile})
                    if not completed.exists():
                        write_json(completed, {"status": "passed", "scope": stage, "helper_sha256": sha256(PROJECT / "scripts/r2_smpl.py") if stage == "convert" else None, "sha256": {name: sha256(output / name) for name in OUTPUTS[stage]}})
                if args.until == stage:
                    break
            write_json(output / "extraction-summary.json", {"status": "passed" if args.until == "convert" else "awaiting_verification", "scope": "Video extraction/conversion only; no robot execution yet", "last_stage": args.until, "profiles_this_invocation": profiles, "heldout_used": args.role == "heldout", "cloud_cost_usd": 0})
        except Exception:
            write_json(output / f"extraction-error-{time.time_ns()}.json", {"status": "failed", "error": traceback.format_exc(), "completed_stages_preserved": True})
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--source-url")
    parser.add_argument("--role", choices=("debug", "heldout"), default="debug")
    parser.add_argument("--frozen-suite", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--until", choices=STAGES, default="convert")
    parser.add_argument("--worker", choices=STAGES, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        succeeded = False
        try:
            worker(args.worker, args.output.resolve())
            succeeded = True
        finally:
            torch = sys.modules.get("torch")
            if torch is not None and torch.cuda.is_initialized():
                write_json(args.output.resolve() / (args.worker + "-cuda.json"), {"status": "passed" if succeeded else "failed", "peak_allocated_bytes": torch.cuda.max_memory_allocated(), "peak_reserved_bytes": torch.cuda.max_memory_reserved(), "device": torch.cuda.get_device_name(), "scope": "Framework peak; system/desktop footprint is sampled separately"})
    elif args.input:
        run(args)
    else:
        parser.error("--input is required")
