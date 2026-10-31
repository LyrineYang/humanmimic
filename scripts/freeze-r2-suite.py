"""Validate the reviewed R2 split, then freeze it before any heldout inference."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import time

from r2_common import GEMX, PROJECT, SONIC, STORAGE, sha256, storage_check, write_json

CODE = (
    "activate-r1.sh", "activate-r2.sh", "run-r2-demo.sh", "extract-r2-video.py", "diagnose-r2-extraction.py",
    "r2_common.py", "r2_smpl.py", "r2_timeline.py", "r2_geometry.py", "r2_initialization.py", "r2_detection.py", "r2_cache.py", "run-r2-cached-suite.py", "cache-r2-pose2d.py",
    "run-r2-checkpoint-recovery.py", "run-r2-physical.py", "run-r1-reproduction.py",
    "evaluate-r2-body.py", "render-r2-demo.py", "audit-r2-run.py", "freeze-r2-suite.py", "summarize-r2-suite.py", "run-r2-suite.py", "run-r2-throughput-recovery.py", "run-r2-video.py",
)
CONFIGS = ("r2-resources.json", "r2-execution-policy.json", "r1-evaluation.json", "r1-dds.xml", "constraints-r2.txt",
           "requirements-r2.lock.txt", "conda-r2-linux-64.explicit.txt")


def inspect(draft):
    blockers, event_files, sources = [], [], []
    if draft.get("status") != "draft":
        raise ValueError("Use the reviewed draft; do not refreeze used test results")
    if draft.get("heldout_inference_used") or any(item.get("model_inference_used") for item in draft["heldout"]):
        blockers.append("Draft declares a proposed heldout source already used")
    for role in ("debug", "heldout"):
        items = draft[role]
        if len(items) != 5 or len({item["action_class"] for item in items}) < 3:
            raise ValueError(f"{role} requires exactly five sources and at least three action classes")
        for item in items:
            if item["role"] != role or item["source_content_trimmed"]:
                raise ValueError("Source role/interval differs from the reviewed split")
            source = Path(item["source_path"])
            if sha256(source) != item["source_sha256"]:
                raise ValueError(f"Source changed: {item['id']}")
            duration = float(subprocess.check_output([str(STORAGE / "envs/humanoid-r2/bin/ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(source)], text=True).strip())
            sources.append(item["source_sha256"])
            annotation = PROJECT / item["events_path"]
            if not annotation.exists():
                blockers.append(f"Missing source-only {role} events: {item['id']}")
                continue
            events = json.loads(annotation.read_text())
            if events["source_sha256"] != item["source_sha256"] or events["role"] != role or not events["events"]:
                raise ValueError(f"Event identity/role mismatch: {item['id']}")
            if events["source_content_trimmed"] or events["time_shift_fitted"]:
                raise ValueError("Events must use the complete original timeline")
            event_ids, event_times = [], []
            for event in events["events"]:
                left, right = event["window_seconds"]
                if event["extremum"] not in ("min", "max") or not 0 <= left <= event["source_event_seconds"] <= right or left == right:
                    raise ValueError(f"Invalid event: {event['id']}")
                if right > duration:
                    raise ValueError(f"Event window exceeds original source: {event['id']}")
                allowed = {f"{side}_{feature}" for side in ("left", "right") for feature in ("elbow_flexion_rad", "knee_flexion_rad", "upper_arm_torso_rad", "thigh_torso_rad", "wrist_height_shoulder_units", "ankle_height_hip_units", "wrist_outward_shoulder_units", "ankle_forward_hip_units")} | {"torso_tilt_rad", "torso_forward_lean_rad", "torso_left_lean_rad", "torso_twist_rad"}
                if event["feature"] not in allowed:
                    raise ValueError(f"Unknown event feature: {event['feature']}")
                event_ids.append(event["id"])
                event_times.append(event["source_event_seconds"])
            if len(set(event_ids)) != len(event_ids) or any(b <= a for a, b in zip(event_times, event_times[1:])):
                raise ValueError("Event IDs/times must be unique and ordered")
            event_files.append(item["events_path"])
    if len(set(sources)) != 10:
        raise ValueError("Duplicate source across split")
    if draft.get("same_original_or_choreography_cross_split") is not False:
        blockers.append("Original/choreography grouping has not been reviewed")
    for item in draft["debug"]:
        path = item.get("audit_json")
        if not path or not Path(path).exists():
            blockers.append(f"Debug run not audited: {item['id']}")
            continue
        report = json.loads(Path(path).read_text())
        if report["status"] not in ("passed", "failed"):
            blockers.append(f"Debug run incomplete: {item['id']}")
        if report.get("source_sha256", report.get("extraction", {}).get("source_sha256")) != item["source_sha256"]:
            blockers.append(f"Debug audit lacks matching source identity: {item['id']}")
    heldout = {item["source_sha256"] for item in draft["heldout"]}
    ledger = STORAGE / "runs/heldout-use-ledger.jsonl"
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            if json.loads(line).get("input_sha256") in heldout:
                blockers.append("A proposed heldout source already appears in the use ledger")
                break
    # A video already inferred as debug cannot silently become an unseen test.
    for identity_path in (STORAGE / "runs").glob("*/extraction/input.json"):
        identity = json.loads(identity_path.read_text())
        if identity.get("input_sha256") in heldout:
            blockers.append(f"Proposed heldout already entered extraction: {identity_path}")
    return blockers, event_files


def freeze(draft_path, output, check_only):
    draft = json.loads(draft_path.read_text())
    blockers, event_files = inspect(draft)
    result = {"status": "awaiting_verification" if blockers else "passed", "scope": "Suite freeze readiness; no model/control execution", "blockers": blockers, "heldout_inference_started": False, "cloud_cost_usd": 0}
    if check_only or blockers:
        return result
    if output.exists():
        raise ValueError("Frozen suite already exists; do not replace it")
    paths = ["scripts/" + name for name in CODE] + ["configs/" + name for name in CONFIGS] + event_files
    hashes = {relative: sha256(PROJECT / relative) for relative in paths}
    asset_plan = json.loads((STORAGE / "runs/asset-download-20261030/download-plan.json").read_text())
    assets = {}
    for entry in asset_plan["files"]:
        path = STORAGE / entry["path"]
        digest = sha256(path)
        if entry.get("sha256") and digest != entry["sha256"]:
            raise ValueError(f"Asset differs from pinned download identity: {path}")
        assets[str(path)] = digest
    for name in ("model_encoder.onnx", "model_decoder.onnx", "observation_config.yaml"):
        path = STORAGE / "models/sonic-default/policy/release" / name
        assets[str(path)] = sha256(path)
    binary = SONIC / "gear_sonic_deploy/target/release/g1_deploy_onnx_ref"
    driver = subprocess.check_output(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"], text=True).strip()
    vendor_diff = {str(path.relative_to(PROJECT)): hashlib.sha256(subprocess.check_output(["git", "-C", str(path), "diff", "--no-ext-diff", "--binary", "HEAD", "--"])).hexdigest() for path in (GEMX, SONIC)}
    frozen = frozen_usage_snapshot(draft)
    frozen.update(status="frozen", frozen_unix=time.time(), draft_sha256=sha256(draft_path), source_code_sha256=hashes, asset_sha256=assets, binary_sha256=sha256(binary), gpu_driver=driver, gemx_revision=subprocess.check_output(["git", "-C", str(GEMX), "rev-parse", "HEAD"], text=True).strip(), sonic_revision=subprocess.check_output(["git", "-C", str(SONIC), "rev-parse", "HEAD"], text=True).strip(), vendor_diff_sha256=vendor_diff, heldout_used_at_freeze=False, no_fitted_time_shift=True, source_content_trimmed=False, debug_audit_sha256={item["audit_json"]: sha256(item["audit_json"]) for item in draft["debug"]}, usage_ledger_relative="runs/heldout-use-ledger.jsonl")
    write_json(output, frozen)
    result.update(frozen_suite=str(output), frozen_suite_sha256=sha256(output))
    return result


def frozen_usage_snapshot(draft):
    """Immutable manifest flags describe freeze time, never current test use."""
    result = copy.deepcopy(draft)
    result["heldout_inference_used_at_freeze"] = result.pop("heldout_inference_used", False)
    for item in result["heldout"]:
        item["model_inference_used_at_freeze"] = item.pop("model_inference_used", False)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if not args.check_only and args.output is None:
        parser.error("--output is required when freezing")
    storage_check()
    report = freeze(args.draft, args.output, args.check_only)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["status"] == "passed" else 2)
