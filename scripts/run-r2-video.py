"""One full video to preserved GEM-X caches, actual simulation and comparison."""

import argparse
import importlib.util
import json
from pathlib import Path
import re

from r2_common import PROJECT, STORAGE, sha256, storage_check


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-url", default="")
    parser.add_argument("--events", type=Path, help="Source-only key-event annotation; absent annotations cannot pass acceptance")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]*", args.run_id):
        parser.error("--run-id must be a simple directory name")
    source = args.input.resolve()
    if not source.is_file() or (args.events and not args.events.is_file()):
        parser.error("Input and supplied annotation must exist")
    spec = importlib.util.spec_from_file_location("r2_single_pipeline", PROJECT / "scripts/run-r2-suite.py")
    pipeline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pipeline)
    pipeline.throughput_policy()
    run = STORAGE / "runs" / args.run_id
    storage_check(run)
    item = {"id": source.stem, "role": "debug", "action_class": "user_supplied", "source_path": str(source), "source_sha256": sha256(source), "source_url": args.source_url, "run_id": args.run_id, "events_path": str(args.events.resolve()) if args.events else None, "audit_json": str(run / "run-audit.json")}
    if args.events:
        annotation = json.loads(args.events.read_text())
        if annotation.get("source_sha256") != item["source_sha256"] or annotation.get("role") != "debug":
            parser.error("Single-video debug annotation must match this source and role")
    reserved = set()
    for manifest_path in (PROJECT / "configs").glob("r2-suite*.json"):
        document = json.loads(manifest_path.read_text())
        reserved.update(entry["source_sha256"] for entry in document.get("heldout", []))
    is_reserved = item["source_sha256"] in reserved
    active = pipeline.active_tasks()
    cached = json.loads(Path(item["audit_json"]).read_text()) if Path(item["audit_json"]).exists() else None
    terminal = cached and cached["status"] in ("passed", "failed") and cached.get("source_sha256", cached.get("extraction", {}).get("source_sha256")) == item["source_sha256"]
    if args.check_only:
        print(json.dumps({"status": "passed", "scope": "Input/scheduling inspection only; no model/control", "input_sha256": item["source_sha256"], "output": str(run), "active_task_pids": active, "cached_terminal_result_available": bool(terminal), "event_annotation_provided": args.events is not None, "reserved_heldout_source": is_reserved}, indent=2))
        raise SystemExit(0)
    if is_reserved:
        parser.error("This source is reserved for heldout; use its frozen suite entry point")
    if active and not terminal:
        parser.error(f"A pipeline is already active; inspect these PIDs before submitting another: {active}")
    if terminal:
        result = {"id": item["id"], "status": cached["status"], "previous_terminal_run_preserved": True}
    else:
        result = pipeline.run_video(item, "debug", {"status": "draft"}, Path(__file__))
    layout_path = run / "artifact-layout.json"
    layout = json.loads(layout_path.read_text()) if layout_path.exists() else {}
    print(json.dumps({**result, "run": str(run), "cached_result_only": bool(terminal), "demo": str(run / layout.get("demo", "demo") / "comparison.mp4"), "acceptance_requires_events_and_full_audit": True}, indent=2))
    raise SystemExit({"passed": 0, "failed": 1, "awaiting_verification": 2}[result["status"]])
