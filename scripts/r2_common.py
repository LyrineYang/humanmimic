"""Shared R2 artifact, resource and subprocess helpers (no model imports)."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

PROJECT = Path(__file__).resolve().parents[1]
GEMX = PROJECT / "vendor/GEM-X"
SONIC = PROJECT / "vendor/GR00T-WholeBodyControl"
STORAGE = Path(os.environ.get("R2_STORAGE_ROOT", "/mnt/d/humanoid-demo-r2"))


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    os.replace(temporary, path)


def sha256(path):
    with Path(path).open("rb") as stream:
        digest = hashlib.sha256()
        while block := stream.read(4 * 1024 * 1024):
            digest.update(block)
        return digest.hexdigest()


def storage_check(output=None):
    config = json.loads((PROJECT / "configs/r2-resources.json").read_text())
    if not (STORAGE / ".humanoid-demo-r2-owner.json").is_file():
        raise ValueError("Unrecognized R2 storage root")
    if output is not None and not Path(output).resolve().is_relative_to(STORAGE.resolve()):
        raise ValueError("Large R2 outputs must be inside the dedicated D storage root")
    free = {drive: shutil.disk_usage(drive).free / 1024**3 for drive in ("/mnt/c", "/mnt/d")}
    if free["/mnt/c"] < config["min_c_free_gib"] or free["/mnt/d"] < config["min_d_free_gib"]:
        raise ValueError(f"Host disk reserve below configured floor: {free}")
    return free


def gpu_observation():
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"observation_error": str(error)}
    if result.returncode:
        return {"observation_error": result.stderr.strip()}
    values = result.stdout.strip().split(",")
    measured = {}
    for key, raw in zip(("gpu_total_used_mib", "gpu_utilization_percent"), values):
        try:
            measured[key] = float(raw)
        except ValueError:
            measured[key + "_unavailable"] = raw.strip()
    return measured


def run_profiled(command, directory, label):
    """One live child; keep each failed attempt's log and resource samples."""
    import psutil

    directory = Path(directory)
    index = 1
    while (directory / f"{label}-attempt-{index:02d}.json").exists():
        index += 1
    prefix = directory / f"{label}-attempt-{index:02d}"
    started = time.monotonic()
    before = storage_check(directory)
    write_json(prefix.with_suffix(".json"), {"status": "awaiting_verification", "command": command, "started_monotonic": started})
    peak_rss, peak_gpu = 0, 0
    with prefix.with_suffix(".log").open("w") as log, prefix.with_suffix(".jsonl").open("w") as samples:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        tracked = psutil.Process(process.pid)
        write_json(prefix.with_suffix(".json"), {"status": "awaiting_verification", "command": command, "pid": process.pid, "process_create_time": tracked.create_time(), "started_monotonic": started})
        while process.poll() is None:
            sample = {"elapsed_seconds": time.monotonic() - started, **gpu_observation()}
            try:
                rss = tracked.memory_info().rss + sum(p.memory_info().rss for p in tracked.children(recursive=True) if p.is_running())
                sample["process_tree_rss_bytes"] = rss
                peak_rss = max(peak_rss, rss)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            sample["available_ram_bytes"] = psutil.virtual_memory().available
            peak_gpu = max(peak_gpu, sample.get("gpu_total_used_mib", 0))
            samples.write(json.dumps(sample) + "\n")
            samples.flush()
            time.sleep(1)
        code = process.wait()
    result = {"status": "passed" if code == 0 else "failed", "command": command, "pid": process.pid, "exit_code": code, "wall_seconds": time.monotonic() - started, "peak_process_tree_rss_bytes": peak_rss, "peak_system_gpu_used_mib": peak_gpu, "host_free_gib_before": before, "host_free_gib_after": storage_check(directory), "sampling_seconds": 1, "gpu_peak_is_system_total_including_desktop": True}
    write_json(prefix.with_suffix(".json"), result)
    if code:
        raise RuntimeError(f"{label} failed with exit {code}; retained {prefix}.log")
    return result
