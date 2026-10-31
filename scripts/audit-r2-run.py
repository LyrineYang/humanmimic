"""Audit complete R2 artifacts and media; never launch inference or control."""

import argparse
import ast
import json
import math
from pathlib import Path
import subprocess
import time

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
        events = body.get("key_events", {}).get("events", [])
        result.update(source_original_frames=source["source"]["frame_count"], normalized_frames=source["normalized"]["frame_count"], control_frames=conversion["control_frames"], key_events_passed=sum(event["status"] == "passed" for event in events), key_events_total=len(events), artifact_layout={"physical": physical.name, "body": body_dir.name, "demo": demo.name})
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
        actual_count = rendered["frames"]
        if count != len(mapping) or not 0 < actual_count <= count or actual_count != len(rendered["valid_actual_state"]):
            raise ValueError("Media mapping length differs from recorded/complete timelines")
        available = [bool(row["robot_frame_available"]) for row in mapping]
        expected_available = [True] * actual_count + [False] * (count - actual_count)
        if available != expected_available:
            raise ValueError("Demo actual-state availability differs from recorded physics")
        all_actual = actual_count == count and all(available) and all(rendered["valid_actual_state"])
        result["actual_video_frames"] = actual_count
        result["all_robot_frames_available"] = all_actual
        if metrics["status"] == "passed" and not all_actual:
            raise ValueError("Passed physics has missing actual-state video frames")
        for i, row in enumerate(mapping):
            if row["demo_frame"] != i or abs(row["source_time_s"] - i / fps) > 1e-8:
                raise ValueError("Demo source time grid changed")
        result["videos"] = [media(demo / name, count, fps) for name in demo_info["files"]]
        result["videos"].append(media(physical / "actual-execution.mp4", actual_count, fps))
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


def write_report(report, audit_path):
    """Readable result package; preserve prior narrative versions on updates."""
    run = Path(report["run"])
    layout = report.get("artifact_layout", {})
    physical = run / layout.get("physical", "physical")
    body = run / layout.get("body", "body-audit")
    demo = run / layout.get("demo", "demo")
    lines = ["# R2 单视频结果", "", f"状态：**{report['status']}**。此为单片结果，不替代5调试/5保留整批验收。", "",
             f"来源SHA256：{report.get('source_sha256', '尚无完整输入证据')}；角色：{report.get('role', '未确认')}。",
             f"原始帧：{report.get('source_original_frames', '未确认')}；30Hz提取帧：{report.get('normalized_frames', '未完成')}；50Hz控制参考：{report.get('control_frames', '未完成')}。",
             f"物理：{report.get('physical_status', 'awaiting_verification')}；身体/事件：{report.get('body_status', 'awaiting_verification')}；视频：{report.get('media_status', 'awaiting_verification')}；视觉核验：{report.get('visual_status', 'awaiting_verification')}。",
             f"关键事件：{report.get('key_events_passed', 0)}/{report.get('key_events_total', 0)}通过。身体误差相对单目提取参考报告，不是人体三维真值或R1关节跟踪误差。", ""]
    artifacts = [("完整三路对照", demo / "comparison.mp4"), ("完整原片", run / "extraction/source-original.mp4"), ("全部提取/转换缓存", run / "extraction"), ("真实执行状态", physical / "actual-state.npz"), ("物理与原生时钟指标", physical / "physical-metrics.json"), ("身体误差/关键事件", body / "body-evaluation.json"), ("全部身体时间序列", body / "body-descriptors.npz"), ("输入/提取/控制/实际帧映射", demo / "frame-mapping.json"), ("独立审计", audit_path)]
    for label, path in artifacts:
        lines.append(f"- [{label}]({path})" if path.exists() else f"- {label}：尚未生成，见失败/缺失证据。")
    for key in ("audit_error", "missing_evidence"):
        if key in report:
            lines += ["", f"{key}：{report[key]}"]
    lines += ["", "源时间轴保留；失败/中断日志和各次invocation记录均在本目录，不以成功片段替换失败。新增云费用0。"]
    output = run / "REPORT.md"
    if output.exists():
        output.rename(run / f"REPORT-before-{time.time_ns()}.md")
    output.write_text("\n".join(lines) + "\n")


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
    if report["status"] in ("passed", "failed") or report.get("media_status") == "passed":
        write_report(report, args.output.resolve())
    print(json.dumps({key: report[key] for key in ("status", "scope", "run")}, indent=2))
    raise SystemExit({"passed": 0, "failed": 1, "awaiting_verification": 2}[report["status"]])
