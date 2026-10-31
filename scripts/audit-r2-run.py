"""Audit complete R2 artifacts and media; never launch inference or control."""

import argparse
import ast
import json
import math
from pathlib import Path
import subprocess

from r2_common import sha256, storage_check, write_json


def media(path, expected_frames, fps):
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
        "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_read_frames,duration",
        "-of", "json", str(path),
    ], text=True))["streams"][0]
    numerator, denominator = map(int, probe["avg_frame_rate"].split("/"))
    if int(probe["nb_read_frames"]) != expected_frames or numerator / denominator != fps:
        raise ValueError(f"Unexpected video frame count/rate: {path}")
    decoded = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-map", "0:v:0", "-f", "null", "-"], capture_output=True, text=True)
    if decoded.returncode or decoded.stderr.strip():
        raise ValueError(f"Video decoding failed: {path}: {decoded.stderr[-1000:]}")
    return {"path": str(path), "status": "passed", "full_decode": True, "stream": probe, "sha256": sha256(path)}


def audit(run):
    layout_path = run / "artifact-layout.json"
    layout = json.loads(layout_path.read_text()) if layout_path.exists() else {}
    for value in layout.values():
        if not isinstance(value, str) or Path(value).name != value or value in (".", ".."):
            raise ValueError("Artifact layout entries must name run subdirectories")
    extraction = run / "extraction"
    physical = run / layout.get("physical", "physical")
    demo = run / layout.get("demo", "demo")
    body_dir = run / layout.get("body", "body-audit")
    result = {"status": "awaiting_verification", "scope": "One complete R2 video; not suite acceptance", "run": str(run), "time_shift_fitted": False, "cloud_cost_usd": 0, "audit_script_sha256": sha256(__file__)}
    try:
        identity = json.loads((extraction / "input.json").read_text())
        if sha256(extraction / "source-original.mp4") != identity["input_sha256"]:
            raise ValueError("Original source identity changed")
        result.update(source_sha256=identity["input_sha256"], role=identity["role"], frozen_suite_sha256=identity.get("frozen_suite_sha256"))
        snapshot = extraction / "source-snapshot"
        snapshot_hashes = json.loads((snapshot / "sha256.json").read_text())
        for relative, digest in snapshot_hashes.items():
            if sha256(snapshot / relative) != digest:
                raise ValueError(f"Execution source snapshot changed: {relative}")
        tree = ast.parse((snapshot / "scripts/extract-r2-video.py").read_text())
        definitions = {target.id: node.value for node in tree.body if isinstance(node, ast.Assign) for target in node.targets if isinstance(target, ast.Name)}
        stages, outputs = (ast.literal_eval(definitions[name]) for name in ("STAGES", "OUTPUTS"))
        checked = []
        for stage in stages:
            complete = json.loads((extraction / f"{stage}-complete.json").read_text())
            if complete["status"] != "passed" or set(complete["sha256"]) != set(outputs[stage]):
                raise ValueError(f"Incomplete stage evidence: {stage}")
            for filename, digest in complete["sha256"].items():
                if sha256(extraction / filename) != digest:
                    raise ValueError(f"Changed {stage} artifact: {filename}")
            checked.append(stage)
        result["extraction"] = {"status": "passed", "verified_stages": checked, "source_sha256": identity["input_sha256"], "role": identity["role"]}
        conversion = json.loads((extraction / "conversion.json").read_text())
        source = json.loads((extraction / "source.json").read_text())
        metrics = json.loads((physical / "physical-metrics.json").read_text())
        body = json.loads((body_dir / "body-evaluation.json").read_text())
        result.update(physical_status=metrics["status"], body_status=body["status"])
        if metrics["status"] == "failed" or body["status"] == "failed":
            result["status"] = "failed"
        if metrics["status"] == "passed":
            clock = metrics["source_clock"]
            if not clock["full_source_consumed"] or clock["verified_source_frames"] != conversion["control_frames"]:
                raise ValueError("Full source was not verified as consumed")
            if metrics["fell"] or not metrics["band_off_during_source"] or not metrics["finite_actual_states"] or metrics["actual_state_overwrites"]:
                raise ValueError("Physical evidence contradicts passed status")
        rendered = json.loads((physical / "actual-render-mapping.json").read_text())
        if rendered["actual_state_sha256"] != sha256(physical / "actual-state.npz"):
            raise ValueError("Rendered actual-state identity changed")
        descriptor_state = body.get("body_error", {}).get("provenance", {}).get("actual_state_sha256")
        if descriptor_state and descriptor_state != rendered["actual_state_sha256"]:
            raise ValueError("Body audit and video use different actual states")
        demo_info = json.loads((demo / "demo.json").read_text())
        mapping = json.loads((demo / "frame-mapping.json").read_text())
        count, fps = demo_info["frames"], demo_info["fps"]
        expected_count = math.ceil(source["normalized"]["duration"] * 25)
        if fps != 25 or count != expected_count or set(demo_info["files"]) != {"source-panel.mp4", "extraction-panel.mp4", "robot-panel.mp4", "comparison.mp4"}:
            raise ValueError("Demo does not contain all complete expected panels/frames")
        if demo_info["source_content_trimmed"] or demo_info["time_shift_fitted"] or rendered["time_shift_fitted"]:
            raise ValueError("Unexpected trimming or fitted time shift")
        if count != len(mapping) or count != rendered["frames"]:
            raise ValueError("Media mapping length differs from complete timeline")
        all_actual = all(row["robot_frame_available"] for row in mapping) and all(rendered["valid_actual_state"])
        result["all_robot_frames_available"] = all_actual
        if metrics["status"] == "passed" and not all_actual:
            raise ValueError("Passed physics has missing actual-state video frames")
        for i, row in enumerate(mapping):
            if row["demo_frame"] != i or abs(row["source_time_s"] - i / fps) > 1e-8:
                raise ValueError("Demo source time grid changed")
        result["videos"] = [media(demo / name, count, fps) for name in demo_info["files"]]
        result["videos"].append(media(physical / "actual-execution.mp4", count, fps))
        result["media_status"] = "passed"
        visual_path = run / "visual-audit.json"
        visual = json.loads(visual_path.read_text()) if visual_path.exists() else {"status": "awaiting_verification", "reason": "Review complete comparison first/middle/last frames"}
        if visual.get("status") == "passed" and visual.get("comparison_sha256") != sha256(demo / "comparison.mp4"):
            raise ValueError("Visual review does not identify the current comparison")
        result["visual_status"] = visual["status"]
        states = [result[key] for key in ("physical_status", "body_status", "media_status", "visual_status")]
        result["status"] = "failed" if "failed" in states else "passed" if all(s == "passed" for s in states) else "awaiting_verification"
    except FileNotFoundError as error:
        result["missing_evidence"] = str(error)
        if any(extraction.glob("extraction-error-*.json")):
            result["status"] = "failed"
    except (ValueError, KeyError, subprocess.CalledProcessError) as error:
        result.update(status="failed", audit_error=str(error))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New JSON audit file; existing reports are preserved")
    args = parser.parse_args()
    storage_check(args.run)
    storage_check(args.output)
    if args.output.exists():
        parser.error("Choose a new audit output path")
    report = audit(args.run.resolve())
    write_json(args.output, report)
    print(json.dumps({key: report[key] for key in ("status", "scope", "run")}, indent=2))
    raise SystemExit({"passed": 0, "failed": 1, "awaiting_verification": 2}[report["status"]])
