"""Execute/resume a frozen local R1 suite without repeating physical trials."""

import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def check_environment(suite):
    manifest = read(suite / "execution-manifest.json")
    gpu = subprocess.check_output(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv"], text=True).strip()
    if gpu != manifest["gpu"]:
        raise RuntimeError("GPU/driver changed; keep this batch separate and prepare a new full suite")
    for package, version in manifest.get("packages", {}).items():
        if importlib.metadata.version(package) != version:
            raise RuntimeError(f"Frozen Python package changed: {package}")
    for name, expected in manifest["source_sha256"].items():
        if digest(ROOT / name) != expected:
            raise RuntimeError(f"Frozen source/config changed: {name}")
    for item in read(ROOT / "configs/r1-suite.json")["runtime_inputs"]:
        if digest(ROOT / item["path"]) != item["sha256"]:
            raise RuntimeError(f"Frozen runtime input changed: {item['path']}")
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            argv = (proc / "cmdline").read_bytes().split(b"\0")
        except (OSError, PermissionError):
            continue
        if not argv or not argv[0]:
            continue
        executable = Path(argv[0].decode(errors="replace")).name
        if executable == "g1_deploy_onnx_ref" or (len(argv) > 1 and Path(argv[1].decode(errors="replace")).name == "run-r1-reproduction.py"):
            raise RuntimeError(f"An existing controller/simulation process is still active (PID {proc.name})")


def append_event(suite, **event):
    event["utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (suite / "resume-events.jsonl").open("a") as stream:
        stream.write(json.dumps(event) + "\n")


def video_complete(run, config):
    video = run / "actual-execution.mp4"
    if not video.exists():
        return False
    process = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,duration",
                              "-select_streams", "v:0", "-of", "json", str(video)], capture_output=True, text=True)
    if process.returncode:
        return False
    try:
        stream = json.loads(process.stdout)["streams"][0]
        return stream["codec_name"] == "h264" and float(stream["duration"]) >= config["reference_frames"] / config["control_hz"] - .08
    except (KeyError, IndexError, ValueError):
        return False


def finish_artifacts(suite, run):
    metrics = read(run / "metrics.json")
    if metrics.get("status") != "passed" or not metrics.get("motion_completed"):
        return
    if (run / "completion-audit.json").exists() and (run / "full-sample-metrics.json").exists():
        append_event(suite, trial=run.name, action="keep_completed_trial")
        return
    if (run / "audit-failed.flag").exists() or (run / "artifact-error.json").exists():
        append_event(suite, trial=run.name, action="keep_artifact_failure_without_retry")
        return
    config = read(run / "run-config.json")
    if not video_complete(run, config):
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        saved = []
        for name in ["actual-execution.mp4", "video-encode.log", "preview.png"]:
            original = run / name
            if original.exists():
                preserved = original.with_name(original.stem + ".interrupted-" + stamp + original.suffix)
                saved.append({"original": name, "preserved": preserved.name, "sha256": digest(original)})
                original.rename(preserved)
        append_event(suite, trial=run.name, action="recover_video_from_actual_states", preserved=saved)
        import numpy as np
        spec = importlib.util.spec_from_file_location("r1_artifact_recovery", ROOT / "scripts/run-r1-reproduction.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with np.load(run / "aligned-tracking.npz") as data:
            window = (float(data["receive_monotonic"][0]), float(data["receive_monotonic"][-1]))
        module.render_actual_video(run, window)
    log = suite / (run.name + ".audit-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".log")
    with log.open("x") as stream:
        code = subprocess.call([sys.executable, str(ROOT / "scripts/summarize-r1.py"), "--run", str(run)], stdout=stream, stderr=subprocess.STDOUT)
    if code:
        (run / "audit-failed.flag").touch()
    append_event(suite, trial=run.name, action="artifact_audit", exit_code=code)


def execute(suite):
    # Check before creating the lock or modifying any trial evidence.
    check_environment(suite)
    with (suite / "orchestrator.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for trial in read(suite / "trials.json"):
            check_environment(suite)
            run = ROOT / trial["run_directory"]
            if run.exists():
                if (run / "metrics.json").exists():
                    finish_artifacts(suite, run)
                    continue
                # An interrupted physical attempt is a retained failure, never a retry.
                (run / "metrics.json").write_text(json.dumps({"status": "failed", "motion_completed": False,
                    "joint_rmse_rad": None, "failure": "Interrupted physical attempt; not repeated"}, indent=2) + "\n")
                (run / "launcher-failed.flag").touch()
                append_event(suite, trial=run.name, action="keep_interrupted_physical_failure")
                continue
            log = suite / (run.name + ".launch.log")
            with log.open("x") as stream:
                append_event(suite, trial=run.name, action="start_physical_trial")
                code = subprocess.call([sys.executable, str(ROOT / "scripts/run-r1-reproduction.py"),
                    "--evaluation", str(suite / (trial["motion"] + ".json")), "--output", str(run)], stdout=stream, stderr=subprocess.STDOUT)
            append_event(suite, trial=run.name, action="physical_and_video_finished", exit_code=code)
            if code:
                run.mkdir(exist_ok=True)
                (run / "launcher-failed.flag").touch()
            if (run / "metrics.json").exists():
                finish_artifacts(suite, run)
        return subprocess.call([sys.executable, str(ROOT / "scripts/audit-r1-suite.py"), "--suite", str(suite)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True, type=Path)
    parser.add_argument("--check-only", action="store_true", help="Read-only source/runtime/driver/active-process checks")
    args = parser.parse_args()
    suite = args.suite.resolve()
    if not suite.is_relative_to(ROOT / "runs"):
        parser.error("--suite must be below the project's runs/ directory")
    if args.check_only:
        check_environment(suite)
        print("Frozen environment and process checks passed; no trial evidence modified")
    else:
        raise SystemExit(execute(suite))
