"""Checkpoint the official independent-frame native77 detector without trimming.

Used by debug and explicitly frozen heldout extraction. Completion records
name this producer and its exact provenance; the master verifies every cached
output before continuing. Only the schedule partitions independent images.
"""

import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from r2_common import GEMX, PROJECT, STORAGE, sha256, storage_check, write_json


def resources():
    result = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used,memory.free,temperature.gpu,power.draw", "--format=csv,noheader,nounits"], text=True)
    rows = result.strip().splitlines()
    if len(rows) != 1:
        raise ValueError("Expected exactly one local GPU")
    values = rows[0].split(",")
    return dict(zip(("system_gpu_used_mib", "gpu_free_mib", "temperature_c", "power_w"), map(float, values)))


def save_tensor(torch, path, value):
    temporary = path.with_name(path.name + f".{time.time_ns()}.tmp")
    torch.save(value, temporary)
    with temporary.open("rb") as stream:
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def run(args):
    output = args.extraction.resolve()
    storage_check(output)
    with (output / "extraction.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return locked_run(args, output)


def locked_run(args, output):
    original = json.loads((output / "input.json").read_text())
    if original["role"] == "heldout":
        frozen_path = Path(original["frozen_suite_path"])
        frozen = json.loads(frozen_path.read_text())
        if sha256(frozen_path) != original["frozen_suite_sha256"] or frozen["status"] != "frozen":
            raise ValueError("Heldout suite identity changed")
        if original["input_sha256"] not in [item["source_sha256"] for item in frozen["heldout"]]:
            raise ValueError("Input is not in the frozen heldout suite")
        for relative, digest in frozen["source_code_sha256"].items():
            if sha256(PROJECT / relative) != digest:
                raise ValueError(f"Frozen source changed: {relative}")
        ledger = STORAGE / "runs/heldout-use-ledger.jsonl"
        if not ledger.is_file() or not any(row.get("input_sha256") == original["input_sha256"] and row.get("suite_sha256") == original["frozen_suite_sha256"] and row.get("run") == str(output) and row.get("used") is True for row in (json.loads(line) for line in ledger.read_text().splitlines())):
            raise ValueError("Heldout inference requires a durable prior-use ledger record")
    elif original["role"] != "debug":
        raise ValueError("Unknown extraction role")
    config = json.loads((output / "resolved-model-config.json").read_text())
    if config["observations"]["batch_size"] != 1:
        raise ValueError("The verified checkpoint method requires original batch size 1")
    if (output / "pose2d-complete.json").exists():
        record = json.loads((output / "pose2d-complete.json").read_text())
        if sha256(output / "keypoints2d.pt") != record["sha256"]["keypoints2d.pt"]:
            raise ValueError("Completed keypoints were changed")
        print("Verified completed pose2d cache; no inference", flush=True)
        return 0
    cache = output / "pose2d-checkpoints"
    cache.mkdir(exist_ok=True)
    identity = {"source_input_sha256": original["input_sha256"], "normalized_sha256": sha256(output / "normalized.mp4"), "tracks_sha256": sha256(output / "tracks.pt"), "resolved_config_sha256": sha256(output / "resolved-model-config.json"), "checkpoint_sha256": sha256(config["observations"]["checkpoint"]), "producer_sha256": sha256(__file__), "native_detector_sha256": sha256(GEMX / "gem/common/pose2d/native77.py"), "gemx_revision": original["gemx_revision"], "release_id": config["observations"]["release_id"], "batch_size": 1, "precision": "official FP32 including flipped augmentation and released BF16 rotary roundtrip", "chunk_frames": args.chunk_frames, "source_content_trimmed": False}
    manifest = cache / "identity.json"
    if manifest.exists():
        if json.loads(manifest.read_text()) != identity:
            raise ValueError("Checkpoint producer/input/weights/config identity changed")
    else:
        write_json(manifest, identity)
        shutil.copy2(__file__, cache / "producer-source.py")
    before = resources()
    if before["gpu_free_mib"] < args.minimum_start_free_mib:
        raise RuntimeError(f"Insufficient GPU headroom before loading the model: {before}")
    import torch
    torch.set_num_threads(8)
    from gem.common.pose2d import load_native77_detector
    from gem.inference.video import VideoFrames
    tracks = torch.load(output / "tracks.pt", map_location="cpu", weights_only=False)
    boxes = torch.as_tensor(tracks["boxes_xys"], dtype=torch.float32)
    count = len(boxes)
    completed, pending = {}, []
    for start in range(0, count, args.chunk_frames):
        stop = min(start + args.chunk_frames, count)
        matches = sorted(cache.glob(f"chunk-{start:06d}-{stop:06d}-attempt-*.json"))
        for path in matches:
            record = json.loads(path.read_text())
            if record["status"] != "passed" or record["identity_sha256"] != sha256(manifest):
                raise ValueError("Invalid chunk completion identity")
            tensor_path = cache / record["tensor_file"]
            if sha256(tensor_path) != record["sha256"]:
                raise ValueError(f"Changed checkpoint tensor: {tensor_path.name}")
            points = torch.load(tensor_path, map_location="cpu", weights_only=True)
            if points.shape != (stop - start, 77, 3) or not torch.isfinite(points).all():
                raise ValueError("Invalid cached detector output")
            if start in completed:
                raise ValueError("Duplicate completed chunks require inspection")
            completed[start] = points
        if start not in completed:
            pending.append((start, stop))
    started = time.monotonic()
    model = None
    equivalent = cache / "equivalence.json"
    with VideoFrames(output / "normalized.mp4") as frames:
        if len(frames) != count:
            raise ValueError("Tracking and video frame counts differ")
        if pending:
            model = load_native77_detector(config["observations"]["checkpoint"], release_id=config["observations"]["release_id"], device="cuda", batch_size=1)
            # A real two-frame call vs two one-frame calls: identical official
            # per-frame batches, model.eval(), crops, confidence and augmentation.
            if not equivalent.exists():
                indices = sorted({count // 4, count // 2})
                rgb = [frames[i] for i in indices]
                baseline = model.predict(rgb, boxes[indices])
                partitioned = torch.cat([model.predict([image], boxes[index:index + 1]) for image, index in zip(rgb, indices)])
                if not torch.equal(baseline, partitioned):
                    write_json(equivalent, {"status": "failed", "maximum_abs_difference": float((baseline - partitioned).abs().max())})
                    raise ValueError("Partitioning changed actual predictions")
                save_tensor(torch, cache / "equivalence-predictions.pt", baseline)
                write_json(equivalent, {"status": "passed", "scope": "Real released model on two source frames, exact official batch1 whole/partitioned equality", "frame_indices": indices, "exact_tensor_equality": True, "maximum_abs_difference": 0.0, "identity_sha256": sha256(manifest), "predictions_sha256": sha256(cache / "equivalence-predictions.pt")})
            probe = json.loads(equivalent.read_text())
            if probe["status"] != "passed" or probe["identity_sha256"] != sha256(manifest) or sha256(cache / "equivalence-predictions.pt") != probe["predictions_sha256"]:
                raise ValueError("Missing/changed equivalence evidence")
            proof = torch.load(cache / "equivalence-predictions.pt", map_location="cpu", weights_only=True)
            for chunk_index, (start, stop) in enumerate(pending):
                gate_started = time.monotonic()
                while True:
                    observation = resources()
                    if observation["gpu_free_mib"] >= 768 and observation["temperature_c"] < args.maximum_temperature_c:
                        break
                    write_json(cache / "progress.json", {"status": "awaiting_verification", "phase": "cooling_or_resource_wait", "completed_frames": sum(len(v) for v in completed.values()), "expected_frames": count, "resource": observation})
                    if time.monotonic() - gate_started >= 120:
                        return 3
                    time.sleep(5)
                points = model.predict(frames[start:stop], boxes[start:stop])
                if points.shape != (stop - start, 77, 3) or not torch.isfinite(points).all():
                    raise ValueError("Nonfinite or missing predicted source frames")
                for index, expected in zip(probe["frame_indices"], proof):
                    if start <= index < stop and not torch.equal(points[index - start], expected):
                        raise ValueError("Sequential decode/inference differs from verified frame predictions")
                attempt = 1
                prefix = f"chunk-{start:06d}-{stop:06d}-attempt-"
                while any(cache.glob(f"{prefix}{attempt:02d}.*")):
                    attempt += 1
                tensor = cache / f"{prefix}{attempt:02d}.pt"
                save_tensor(torch, tensor, points)
                stats = {"peak_allocated_bytes": torch.cuda.max_memory_allocated(), "peak_reserved_bytes": torch.cuda.max_memory_reserved(), "allocated_bytes_after_chunk": torch.cuda.memory_allocated(), "reserved_bytes_after_chunk": torch.cuda.memory_reserved()}
                write_json(tensor.with_suffix(".json"), {"status": "passed", "scope": "Independent original-frame subset only", "start": start, "stop": stop, "tensor_file": tensor.name, "sha256": sha256(tensor), "identity_sha256": sha256(manifest), "framework": stats, "system_resource": resources()})
                completed[start] = points
                torch.cuda.empty_cache()
                write_json(cache / "progress.json", {"status": "awaiting_verification", "phase": "checkpoint_saved", "completed_frames": sum(len(v) for v in completed.values()), "expected_frames": count, "last_range": [start, stop], "framework": stats, "system_resource": resources(), "wall_seconds_this_invocation": time.monotonic() - started})
                print(f"Saved exact native77 frames {start}:{stop}; {sum(len(v) for v in completed.values())}/{count}", flush=True)
                if args.max_new_chunks and chunk_index + 1 >= args.max_new_chunks:
                    return 3
    points = torch.cat([completed[start] for start in sorted(completed)])
    if points.shape != (count, 77, 3):
        raise ValueError("Cannot complete until every original normalized frame is present")
    proof_record = json.loads(equivalent.read_text())
    if proof_record["status"] != "passed" or proof_record["identity_sha256"] != sha256(manifest) or sha256(cache / "equivalence-predictions.pt") != proof_record["predictions_sha256"]:
        raise ValueError("Equivalence evidence must remain intact before completion")
    target = output / "keypoints2d.pt"
    if target.exists():
        raise ValueError("Unmarked prior full tensor requires inspection; it will not be overwritten")
    save_tensor(torch, target, points)
    write_json(output / "pose2d-complete.json", {"status": "passed", "scope": "pose2d", "helper_sha256": None, "sha256": {target.name: sha256(target)}, "auxiliary_producer": str(Path(__file__).resolve()), "producer_sha256": sha256(__file__), "checkpoint_identity_sha256": sha256(manifest), "original_extractor_unchanged": True, "all_original_normalized_frames": count, "equivalence_evidence": str(equivalent)})
    if torch.cuda.is_initialized():
        write_json(cache / f"cuda-complete-{time.time_ns()}.json", {"status": "passed", "peak_allocated_bytes": torch.cuda.max_memory_allocated(), "peak_reserved_bytes": torch.cuda.max_memory_reserved(), "device": torch.cuda.get_device_name()})
    write_json(cache / "progress.json", {"status": "passed", "scope": "All original pose2d observations only, no 3D motion or physical execution", "completed_frames": count, "expected_frames": count})
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--chunk-frames", type=int, default=32)
    parser.add_argument("--max-new-chunks", type=int, default=0)
    parser.add_argument("--minimum-start-free-mib", type=float, default=6144)
    parser.add_argument("--maximum-temperature-c", type=float, default=82)
    arguments = parser.parse_args()
    if arguments.chunk_frames < 1 or arguments.max_new_chunks < 0:
        parser.error("Invalid chunk bounds")
    raise SystemExit(run(arguments))
