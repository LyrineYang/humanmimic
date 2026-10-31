"""Describe cached detection/2D observations, without inference or new gates."""

import argparse
import json
from pathlib import Path

from r2_common import sha256, storage_check, write_json


def diagnose(extraction):
    import numpy as np
    import torch

    identity = json.loads((extraction / "input.json").read_text())
    source = json.loads((extraction / "source.json").read_text())
    hashes = {}

    def verified(stage, filename):
        marker = json.loads((extraction / f"{stage}-complete.json").read_text())
        digest = sha256(extraction / filename)
        if marker["status"] != "passed" or digest != marker["sha256"][filename]:
            raise ValueError(f"Cached {stage} evidence differs: {filename}")
        hashes[filename] = digest
        return torch.load(extraction / filename, map_location="cpu", weights_only=False)

    tracks = verified("detect", "tracks.pt")
    observed = np.asarray(tracks["observed_primary"], dtype=bool)
    count = len(observed)
    if count != source["normalized"]["frame_count"] or not np.array_equal(tracks["frame_ids"], np.arange(count)):
        raise ValueError("Tracking does not cover the complete normalized timeline")
    if len(tracks["raw_boxes"]) != count or len(tracks["raw_scores"]) != count or not np.isfinite(tracks["boxes_xys"]).all():
        raise ValueError("Invalid complete detection/crop cache")
    raw = np.array([len(boxes) > 0 for boxes in tracks["raw_boxes"]])
    changes = np.diff(np.r_[False, ~observed, False].astype(int))
    fps = source["normalized"]["fps"]
    gaps = [{"start_normalized_frame": int(start), "stop_frame_exclusive": int(stop), "seconds": float((stop - start) / fps)} for start, stop in zip(np.flatnonzero(changes == 1), np.flatnonzero(changes == -1))]
    report = {"status": "passed", "scope": "Descriptive cached observation computation only; not extraction accuracy, physical acceptance or an additional gate", "source_sha256": identity["input_sha256"], "role": identity["role"], "frames": count, "raw_detection_frames": int(raw.sum()), "raw_detection_fraction": float(raw.mean()), "dominant_track_observed_frames": int(observed.sum()), "dominant_track_observed_fraction": float(observed.mean()), "filled_primary_frames": int((~observed).sum()), "dominant_track_valid_span": list(tracks["valid_span"]), "dominant_track_missing_runs": gaps, "cache_sha256": hashes, "pose_confidence_status": "awaiting_verification", "no_model_or_control_launched": True, "cloud_cost_usd": 0}
    if (extraction / "pose2d-complete.json").exists():
        points = verified("pose2d", "keypoints2d.pt")
        points = np.asarray(points)
        if points.shape != (count, 77, 3) or not np.isfinite(points).all():
            raise ValueError("Invalid complete SOMA77 observations")
        confidence = points[..., 2]
        report.update(pose_confidence_status="passed", keypoints_per_frame=77, all77_confidence_mean=float(confidence.mean()), all77_confidence_median=float(np.median(confidence)), all77_fraction_confidence_above_025=float((confidence > .25).mean()), confidence_semantics="Native raw heatmap maximum; not a calibrated probability or 3D accuracy")
        conversion_path = extraction / "conversion.json"
        if conversion_path.exists():
            mapping = json.loads(conversion_path.read_text())["smpl_indices"]
            if len(mapping) != 24 or not all(0 <= value < 77 for value in mapping):
                raise ValueError("Unexpected SMPL24 mapping")
            mapped = confidence[:, mapping]
            report.update(mapped_smpl24_fraction_confidence_above_025=float((mapped > .25).mean()), mapped_smpl24_per_frame_confident_fraction_percentiles=np.percentile((mapped > .25).mean(axis=1), [0, 5, 50, 95, 100]).tolist())
    report["interpretation"] = "Raw detections and the selected dominant track can have different coverage. Filled boxes do not imply absent raw detections or wrong poses; assess source events and actual physics separately. No per-video tuning or confidence acceptance threshold was applied."
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    storage_check(args.output)
    if args.output.exists():
        parser.error("Preserve previous diagnostics; choose a new output file")
    result = diagnose(args.extraction.resolve())
    write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
