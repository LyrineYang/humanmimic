"""Serial R2 extraction/physics/demo runs, preserving completed and failed trials."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from r2_common import GEMX, PROJECT, SONIC, STORAGE, sha256, storage_check, write_json


def active_tasks():
    found = []
    scripts = {b"extract-r2-video.py", b"run-r2-physical.py", b"cache-r2-pose2d.py", b"cache-r2-paced-pose2d.py", b"run-r2-throughput-recovery.py", b"run-r2-checkpoint-recovery.py", b"render-r2-demo.py", b"run-r2-demo.sh", b"run-r2-suite.py", b"run-r2-video.py", b"prepare-r2-startup-diagnostic.py"}
    for path in Path("/proc").glob("[0-9]*/cmdline"):
        if int(path.parent.name) == os.getpid():
            continue
        try:
            args = path.read_bytes().split(b"\0")
        except OSError:
            continue
        if args and (Path(os.fsdecode(args[0])).name == "g1_deploy_onnx_ref" or any(Path(os.fsdecode(arg)).name.encode() in scripts for arg in args[1:3])):
            found.append(int(path.parent.name))
    return found


def throughput_policy():
    path = PROJECT / "configs/r2-execution-policy.json"
    if not path.exists():
        return False
    policy = json.loads(path.read_text())
    if Path("/proc/sys/kernel/random/boot_id").read_text().strip() != policy["local_boot_id_authorized"]:
        raise RuntimeError("Local machine rebooted: user requested server handoff, not more local retries")
    return policy["execution_priority"] == "throughput"


def wait_for_recorded_task(path, *, pose_required=True):
    task = json.loads(path.read_text())
    pid = task["pid"]
    while True:
        throughput_policy()
        stat = Path(f"/proc/{pid}/stat")
        try:
            fields = stat.read_text().split(") ", 1)[1].split()
        except FileNotFoundError:
            break
        if int(fields[19]) != task["process_start_ticks"] or fields[0] == "Z":
            break
        time.sleep(2)
    if pose_required and not (path.parent / "extraction/pose2d-complete.json").is_file():
        raise RuntimeError("Recorded recovery stopped without a complete pose cache; inspect its log")


def step(run, name, environment, script, arguments):
    attempt = 1
    while (run / f"{name}-invocation-{attempt:02d}.json").exists():
        attempt += 1
    base = run / f"{name}-invocation-{attempt:02d}"
    command = ["bash", "-c", 'set -e; source "$1"; shift; exec python "$@"', "r2-stage", str(PROJECT / f"scripts/activate-{environment}.sh"), str(PROJECT / "scripts" / script), *map(str, arguments)]
    record = {"status": "awaiting_verification", "command": command, "started_unix": time.time(), "script_sha256": sha256(PROJECT / "scripts" / script)}
    write_json(base.with_suffix(".json"), record)
    with base.with_suffix(".log").open("x") as log:
        process = subprocess.Popen(command, cwd=PROJECT, stdout=log, stderr=subprocess.STDOUT)
        record.update(pid=process.pid, boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip())
        try:
            record["process_start_ticks"] = int(Path(f"/proc/{process.pid}/stat").read_text().split(") ", 1)[1].split()[19])
        except FileNotFoundError:
            record["exited_before_process_sample"] = True
        write_json(base.with_suffix(".json"), record)
        code = process.wait()
    record.update(status="passed" if code == 0 else "awaiting_verification" if code == 2 else "failed", exit_code=code, ended_unix=time.time())
    write_json(base.with_suffix(".json"), record)
    return code


def check_frozen(manifest, manifest_path):
    if manifest["status"] != "frozen":
        raise ValueError("Heldout execution requires the frozen manifest")
    current = json.loads(manifest_path.read_text())
    if current != manifest:
        raise ValueError("Frozen manifest changed while the suite was active")
    for relative, digest in manifest["source_code_sha256"].items():
        if sha256(PROJECT / relative) != digest:
            raise ValueError(f"Frozen code/configuration changed: {relative}")
    gpu = subprocess.check_output(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"], text=True).strip()
    if gpu != manifest["gpu_driver"]:
        raise ValueError("GPU or driver differs from the frozen environment")
    binary = SONIC / "gear_sonic_deploy/target/release/g1_deploy_onnx_ref"
    if sha256(binary) != manifest["binary_sha256"]:
        raise ValueError("Native controller binary differs from the frozen suite")
    for path, field in ((GEMX, "gemx_revision"), (SONIC, "sonic_revision")):
        revision = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
        if revision != manifest[field]:
            raise ValueError(f"Upstream revision differs from the frozen suite: {field}")
    for relative, digest in manifest["vendor_diff_sha256"].items():
        diff = subprocess.check_output(["git", "-C", str(PROJECT / relative), "diff", "--no-ext-diff", "--binary", "HEAD", "--"])
        if hashlib.sha256(diff).hexdigest() != digest:
            raise ValueError(f"Pinned vendor worktree changed: {relative}")


def run_video(item, role, manifest, manifest_path):
    run = STORAGE / "runs" / item["run_id"]
    storage_check(run)
    if sha256(item["source_path"]) != item["source_sha256"]:
        raise ValueError(f"Reviewed source changed: {item['id']}")
    fast = throughput_policy()
    if Path(item["audit_json"]).exists():
        prior = json.loads(Path(item["audit_json"]).read_text())
        if prior["status"] in ("passed", "failed") and prior.get("source_sha256", prior.get("extraction", {}).get("source_sha256")) == item["source_sha256"]:
            resource_only = fast and prior["status"] == "failed" and not (run / "physical").exists() and any("Cooled pose cohort stopped" in path.read_text() for path in (run / "extraction").glob("pose2d-attempt-*.log"))
            if resource_only:
                original = Path(item["audit_json"])
                archived = original.with_name(f"run-audit-resource-wait-{time.time_ns()}.json")
                digest = sha256(original)
                original.rename(archived)
                write_json(run / "resource-recovery-authorization.json", {"reason": "User requested throughput priority and removal of artificial cooling waits; original numerical/physical acceptance unchanged", "preserved_audit": str(archived), "preserved_audit_sha256": digest, "cloud_cost_usd": 0})
            else:
                return {"id": item["id"], "status": prior["status"], "previous_terminal_run_preserved": True}
    run.mkdir(exist_ok=True)
    extraction, physical, body, demo = (run / name for name in ("extraction", "physical", "body-audit", "demo"))
    extraction_args = ["--input", item["source_path"], "--source-url", item["source_url"], "--role", role, "--output", extraction]
    if role == "heldout":
        extraction_args += ["--frozen-suite", manifest_path]
    if role == "heldout":
        check_frozen(manifest, manifest_path)
    if fast and not (extraction / "pose2d-complete.json").exists():
        prepare_code = step(run, "conditions", "r2", "extract-r2-video.py", [*extraction_args, "--until", "features"])
        if prepare_code:
            return {"id": item["id"], "status": "failed", "reason": "Pre-pose stages failed; original outputs retained"}
        pose_code = step(run, "native-pose", "r2", "run-r2-throughput-recovery.py", ["--extraction", extraction])
        if pose_code:
            return {"id": item["id"], "status": "awaiting_verification", "reason": "Native pose recovery incomplete; inspect logs/checkpoints"}
    # Re-enter the master even for a completed extraction: it verifies every
    # cached hash and source snapshot before any reference is sent to control.
    extraction_code = step(run, "extraction", "r2", "extract-r2-video.py", extraction_args)
    if extraction_code:
        failed_audit = run / f"run-audit-extraction-{time.time_ns()}.json"
        step(run, "audit-incomplete", "r2", "audit-r2-run.py", ["--run", run, "--output", failed_audit])
        outcome = json.loads(failed_audit.read_text())
        if outcome["status"] == "failed" and not Path(item["audit_json"]).exists():
            write_json(item["audit_json"], outcome)
        return {"id": item["id"], "status": outcome["status"], "reason": "Extraction invocation failed; original stage evidence preserved"}
    if not physical.exists():
        if role == "heldout":
            check_frozen(manifest, manifest_path)
        step(run, "physical", "r1", "run-r2-physical.py", ["--reference", extraction / "sonic-reference.npz", "--output", physical, "--video"])
    if not (physical / "physical-metrics.json").exists():
        return {"id": item["id"], "status": "awaiting_verification", "reason": "Existing partial physical run requires interruption review; no replacement trial launched"}
    if not body.exists():
        if role == "heldout":
            check_frozen(manifest, manifest_path)
        body_args = ["--extraction", extraction, "--physical", physical, "--output", body]
        if item.get("events_path"):
            body_args += ["--events", PROJECT / item["events_path"]]
        step(run, "body", "r1", "evaluate-r2-body.py", body_args)
    if not demo.exists():
        if role == "heldout":
            check_frozen(manifest, manifest_path)
        step(run, "demo", "r2", "render-r2-demo.py", ["--extraction", extraction, "--physical", physical, "--output", demo])
    audit_path = Path(item["audit_json"])
    initial = run / f"run-audit-initial-{time.time_ns()}.json"
    step(run, "audit", "r2", "audit-r2-run.py", ["--run", run, "--output", initial])
    outcome = json.loads(initial.read_text())
    if outcome["status"] in ("passed", "failed") and not audit_path.exists():
        write_json(audit_path, outcome)
    if (demo / "comparison.mp4").exists() and not (run / "visual-preview.jpg").exists():
        info = json.loads((demo / "demo.json").read_text())
        last = info["frames"] - 1
        indices = sorted({min(25, last), last // 2, max(0, last - 12)})
        expression = "+".join(f"eq(n\\,{i})" for i in indices)
        command = [str(STORAGE / "envs/humanoid-r2/bin/ffmpeg"), "-v", "error", "-nostdin", "-n", "-i", str(demo / "comparison.mp4"), "-vf", f"select={expression},scale=1280:-1,tile=1x{len(indices)}", "-frames:v", "1", str(run / "visual-preview.jpg")]
        subprocess.run(command, check=True)
        write_json(run / "visual-preview.json", {"comparison_sha256": sha256(demo / "comparison.mp4"), "demo_frame_indices": indices, "manual_review_required": True})
    return {"id": item["id"], "status": outcome["status"], "initial_audit": str(initial), "visual_review_required": outcome.get("visual_status") == "awaiting_verification"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--role", choices=("debug", "heldout"), required=True)
    parser.add_argument("--output", type=Path, required=True, help="Orchestration logs; resumable and separately locked")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--wait-for-task", type=Path, help="Adopt one already-running pose recovery; never submit it twice")
    parser.add_argument("--wait-for-queue", type=Path, help="Wait for a recorded orchestration to finish before a serial follow-up")
    parser.add_argument("--source-id", help="Execute only this manifest source; full-suite acceptance still uses all ten")
    args = parser.parse_args()
    storage_check(args.output)
    manifest = json.loads(args.manifest.read_text())
    selected = [item for item in manifest[args.role] if not args.source_id or item["id"] == args.source_id]
    if not selected or (args.wait_for_task and args.wait_for_queue):
        parser.error("Choose a valid source and at most one recorded task to wait for")
    throughput_policy()
    if args.role == "heldout":
        check_frozen(manifest, args.manifest)
    if args.check_only:
        print(json.dumps({"status": "passed", "scope": "Scheduling preview only; no inference/control", "role": args.role, "sources": [item["id"] for item in manifest[args.role]], "active_task_pids": active_tasks()}, indent=2))
        raise SystemExit(0)
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "suite.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.wait_for_task:
            wait_for_recorded_task(args.wait_for_task)
        if args.wait_for_queue:
            wait_for_recorded_task(args.wait_for_queue, pose_required=False)
        if active_tasks():
            raise ValueError("A model/control task is already running; inspect it before submitting a suite")
        rows = []
        for item in selected:
            write_json(args.output / "progress.json", {"status": "awaiting_verification", "active_source": item["id"], "role": args.role, "sources": rows, "execution_priority": "throughput" if throughput_policy() else "cooled", "cloud_cost_usd": 0})
            rows.append(run_video(item, args.role, manifest, args.manifest.resolve()))
            write_json(args.output / "progress.json", {"status": "awaiting_verification", "role": args.role, "sources": rows, "heldout_started": args.role == "heldout", "cloud_cost_usd": 0})
            print(json.dumps(rows[-1]), flush=True)
        status = "failed" if any(row["status"] == "failed" for row in rows) else "awaiting_verification" if any(row["status"] == "awaiting_verification" for row in rows) else "passed"
        write_json(args.output / "progress.json", {"status": status, "scope": "Execution/artifact readiness only; summarize-r2-suite applies the4/5 acceptance rule", "role": args.role, "sources": rows, "heldout_started": args.role == "heldout", "cloud_cost_usd": 0})
        raise SystemExit({"passed": 0, "failed": 1, "awaiting_verification": 2}[status])
