"""Verify an interrupted R2 run and resume after local GPU headroom returns.

No applications are stopped. Completed/failed physical attempts are retained;
this entry point only resumes extraction and invokes the existing wrapper.
"""

import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from r2_common import PROJECT, STORAGE, sha256, storage_check, write_json


def active_pipeline():
    names = {"extract-r2-video.py", "run-r2-physical.py", "render-r2-demo.py", "run-r2-demo.sh", "g1_deploy_onnx_ref"}
    found = []
    for entry in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            argv = [part.decode() for part in entry.read_bytes().split(b"\0") if part]
        except (OSError, UnicodeError):
            continue
        # Never inspect arbitrary launcher text (e.g. bash -c "...").
        executable = Path(argv[0]).name if argv else ""
        script = Path(argv[1]).name if len(argv) > 1 and executable in {"python", "python3", "python3.12", "python3.10", "bash"} else ""
        if executable in names or script in names:
            found.append({"pid": int(entry.parent.name), "executable": executable, "script": script})
    return found


def verify(run):
    storage_check(run)
    extraction = run / "extraction"
    identity = json.loads((extraction / "input.json").read_text())
    if identity["role"] != "debug":
        raise ValueError("Heldout runs must use their frozen suite entry point")
    if sha256(identity["input"]) != identity["input_sha256"]:
        raise ValueError("Original source changed")
    frozen = json.loads((extraction / "source-snapshot/sha256.json").read_text())
    for relative, digest in frozen.items():
        if sha256(PROJECT / relative) != digest:
            raise ValueError(f"Frozen source/config changed: {relative}")
    for relative, key in [("scripts/extract-r2-video.py", "script_sha256"), ("scripts/r2_common.py", "common_helper_sha256")]:
        if sha256(PROJECT / relative) != identity[key]:
            raise ValueError(f"Extraction identity changed: {relative}")
    if sha256(STORAGE / "runs/asset-download-20261030/download-plan.json") != identity["asset_plan_sha256"]:
        raise ValueError("Asset plan changed")
    revision = subprocess.check_output(["git", "-C", str(PROJECT / "vendor/GEM-X"), "rev-parse", "HEAD"], text=True).strip()
    if revision != identity["gemx_revision"]:
        raise ValueError("GEM-X source revision changed")
    completed = []
    for record_path in sorted(extraction.glob("*-complete.json")):
        record = json.loads(record_path.read_text())
        if record["status"] != "passed":
            raise ValueError(f"Invalid completion record: {record_path.name}")
        for name, digest in record["sha256"].items():
            if sha256(extraction / name) != digest:
                raise ValueError(f"Cached artifact changed: {name}")
        completed.append(record_path.name.removesuffix("-complete.json"))
    if (run / "physical").exists():
        metrics = run / "physical/physical-metrics.json"
        if not metrics.exists() or json.loads(metrics.read_text())["status"] != "passed":
            raise ValueError("Existing incomplete/failed physics requires inspection; it will not be rerun or overwritten")
    live = active_pipeline()
    if live:
        raise RuntimeError(f"A pipeline/controller is already active: {live}")
    return identity, completed


def gpu_free_mib():
    result = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"], text=True)
    lines = result.strip().splitlines()
    if len(lines) != 1:
        raise RuntimeError("Expected exactly one local GPU")
    return float(lines[0])


def main(args):
    run = args.run.resolve()
    identity, completed = verify(run)
    print(json.dumps({"status": "passed", "scope": "recovery guards only", "verified_completed_stages": completed, "gpu_free_mib": gpu_free_mib(), "no_inference_started": True}), flush=True)
    if args.check_only:
        return 0
    with (run / "resume.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        index = 1
        while (run / f"resume-attempt-{index:02d}.json").exists():
            index += 1
        record_path = run / f"resume-attempt-{index:02d}.json"
        record = {"status": "awaiting_verification", "phase": "waiting_for_gpu", "pid": os.getpid(), "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(), "minimum_free_mib": args.min_free_mib, "maximum_wait_seconds": args.max_wait_seconds, "completed_stages_verified": completed, "started_unix": time.time(), "expectation": "Reuse verified completed caches; new attempt for interrupted stage; preserve all failures; no applications stopped", "cloud_cost_usd": 0}
        write_json(record_path, record)
        began, stable_since = time.monotonic(), None
        while True:
            storage_check(run)
            free = gpu_free_mib()
            now = time.monotonic()
            stable_since = (stable_since or now) if free >= args.min_free_mib else None
            record.update({"last_observed_unix": time.time(), "gpu_free_mib": free, "waited_seconds": now - began})
            write_json(record_path, record)
            if stable_since is not None and now - stable_since >= 15:
                break
            if now - began >= args.max_wait_seconds:
                record.update({"phase": "resource_busy", "reason": "GPU headroom has not returned; no inference submitted"})
                write_json(record_path, record)
                return 3
            time.sleep(15)
        identity, completed = verify(run)
        command = ["bash", str(PROJECT / "scripts/run-r2-demo.sh"), identity["input"], run.name]
        if identity.get("source_url"):
            command.append(identity["source_url"])
        record.update({"phase": "running", "command": command, "resumed_unix": time.time()})
        write_json(record_path, record)
        with (run / f"resume-attempt-{index:02d}.log").open("x") as log:
            child = subprocess.Popen(command, cwd=PROJECT, stdout=log, stderr=subprocess.STDOUT)
            record["child_pid"] = child.pid
            write_json(record_path, record)
            code = child.wait()
        record.update({"status": "passed" if code == 0 else "failed", "phase": "finished", "exit_code": code, "ended_unix": time.time()})
        write_json(record_path, record)
        return code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--min-free-mib", type=float, default=6144)
    parser.add_argument("--max-wait-seconds", type=float, default=3600)
    arguments = parser.parse_args()
    if arguments.min_free_mib <= 0 or arguments.max_wait_seconds <= 0:
        parser.error("Resource limits must be positive")
    raise SystemExit(main(arguments))
