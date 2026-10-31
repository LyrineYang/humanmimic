"""CPU-only full-decode source screening, provenance and aspect-preserving previews.

This does not run person detection or motion inference and never declares a
source eligible automatically. Visual review precedes any suite freeze.
"""

import argparse
import json
from pathlib import Path
import subprocess

import cv2
import numpy as np

from r2_common import sha256, storage_check, write_json


def inspect(video, output, samples):
    video = video.resolve()
    metadata = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)], text=True))
    streams = [stream for stream in metadata["streams"] if stream["codec_type"] == "video"]
    if len(streams) != 1:
        raise ValueError("Source must have exactly one video stream")
    stream = streams[0]
    duration = float(stream.get("duration", metadata["format"]["duration"]))
    expected = int(stream.get("nb_frames", 0))
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise ValueError("Could not open source")
    if not expected:
        expected = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if expected <= 0:
        raise ValueError("Source frame count is unavailable")
    requested = set(map(int, np.linspace(0, expected - 1, min(samples, expected), dtype=int)))
    thumbnails, dark_frames, changes = [], [], []
    previous, decoded = None, 0
    maximum_change = 0.0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        small = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (96, 54)).astype(np.float32)
        if small.mean() < 4:
            dark_frames.append(decoded)
        if previous is not None:
            delta = abs(small - previous)
            maximum_change = max(maximum_change, float(delta.mean()))
            if delta.mean() > 30 and (delta > 40).mean() > .5:
                changes.append({"frame": decoded, "mean_gray_difference": float(delta.mean()), "fraction_changed_over_40": float((delta > 40).mean())})
        previous = small
        if decoded in requested:
            canvas = np.full((240, 320, 3), 25, np.uint8)
            height, width = frame.shape[:2]
            scale = min(320 / width, 212 / height)
            w, h = max(1, round(width * scale)), max(1, round(height * scale))
            x, y = (320 - w) // 2, 28 + (212 - h) // 2
            canvas[y:y + h, x:x + w] = cv2.resize(frame, (w, h))
            # Approximate times are for source screening only. Extraction saves
            # exact original PTS and the source->normalized frame map separately.
            cv2.putText(canvas, f"frame {decoded} ~{decoded * duration / expected:.2f}s", (5, 18), cv2.FONT_HERSHEY_SIMPLEX, .45, (255, 255, 255), 1)
            thumbnails.append(canvas)
        decoded += 1
    capture.release()
    if decoded != expected:
        raise ValueError(f"Full decode frame count differs: {decoded} != {expected}")
    while len(thumbnails) % 4:
        thumbnails.append(np.full((240, 320, 3), 25, np.uint8))
    preview = np.concatenate([np.concatenate(thumbnails[i:i + 4], axis=1) for i in range(0, len(thumbnails), 4)], axis=0)
    target = output / (video.stem + ".jpg")
    if not cv2.imwrite(str(target), preview):
        raise RuntimeError("Could not save preview")
    sidecar = video.with_suffix(".info.json")
    source_info = json.loads(sidecar.read_text()) if sidecar.exists() else {}
    return {"status": "passed", "scope": "Full decode and visual screening artifacts only; not model acceptance", "path": str(video), "source_url": source_info.get("webpage_url"), "title": source_info.get("title"), "channel": source_info.get("channel"), "sha256": sha256(video), "duration_seconds": duration, "decoded_frames": decoded, "reported_frames": expected, "dimensions": [stream["width"], stream["height"]], "preview": str(target), "sampled_frame_indices": sorted(requested), "preview_times_are_approximate": True, "source_content_trimmed": False, "very_dark_frame_indices": dark_frames, "large_global_change_candidates": changes, "global_change_detector_is_heuristic": True, "maximum_mean_gray_frame_change": maximum_change, "basic_gate_eligibility": "awaiting_visual_review", "model_inference_used": False, "heldout_inference_used": False}


def main(args):
    storage_check(args.output)
    if len({video.stem for video in args.videos}) != len(args.videos):
        raise ValueError("Input filenames must have distinct stems to preserve each report")
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output / "expectation.json", {"status": "awaiting_verification", "expectation": "Decode every source frame, preserve source/SHA/timeline, preview first/last and uniform intermediate frames without distortion; screen cuts/dark frames heuristically, leave human eligibility to visual review", "videos": [str(path.resolve()) for path in args.videos], "source_sha256": sha256(__file__), "model_inference_used": False})
    records = []
    for video in args.videos:
        try:
            record = inspect(video, args.output, args.samples)
        except (ValueError, OSError, subprocess.CalledProcessError) as error:
            record = {"status": "failed", "path": str(video), "error": str(error), "model_inference_used": False}
        write_json(args.output / (video.stem + ".json"), record)
        records.append(record)
    result = {"status": "passed" if all(record["status"] == "passed" for record in records) else "failed", "scope": "Source decoding/provenance/previews; eligibility requires visual review", "sources": records, "model_inference_used": False, "heldout_inference_used": False, "cloud_cost_usd": 0}
    write_json(args.output / "results.json", result)
    print(json.dumps({"status": result["status"], "source_count": len(records), "output": str(args.output)}))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("videos", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=16)
    arguments = parser.parse_args()
    if arguments.samples < 4:
        parser.error("Use at least four preview samples")
    raise SystemExit(main(arguments))
