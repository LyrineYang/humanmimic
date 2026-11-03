"""Standard-library accounting/admission for local R4 CUDA campaigns.

This module never computes research tensors. A single locked coordinator owns
the ledger; every launched process group is private to one reserved GPU slot.
"""
import csv
import fcntl
import hashlib
import io
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def exclusive(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a")
    try:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        stream.close()
        raise RuntimeError("Another campaign owns lock: " + str(path))
    return stream


def inventory():
    def query(fields, kind="gpu"):
        raw = subprocess.check_output(["nvidia-smi", "--query-"+kind+"="+fields,
                                       "--format=csv,noheader,nounits"], timeout=15).decode()
        return [[cell.strip() for cell in row] for row in csv.reader(io.StringIO(raw)) if row]
    devices = {row[1]: {"index": int(row[0]), "uuid": row[1], "name": row[2],
                       "driver": row[3], "free_mib": int(row[4]), "compute_pids": []}
               for row in query("index,uuid,name,driver_version,memory.free")}
    for uuid, pid in query("gpu_uuid,pid", "compute-apps"):
        if uuid in devices:
            devices[uuid]["compute_pids"].append(int(pid))
    return devices


def idle_device(devices, uuid):
    if uuid not in devices:
        raise ValueError("Use a full GPU UUID from the current nvidia-smi inventory")
    gpu = devices[uuid]
    if "V100" not in gpu["name"] or gpu["free_mib"] < 4096 or gpu["compute_pids"]:
        raise RuntimeError("GPU unavailable; never preempt/share another compute job: " + uuid)
    return gpu


def validate_limits(limits):
    # This version is specifically the user's local 144 GPUh / 36h authorization.
    for name, maximum in [("gpu_hours_max", 144), ("wall_hours_max", 36), ("concurrent_gpus_max", 4)]:
        value = limits[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= maximum:
            raise ValueError("Invalid authorized limit: " + name)
    if limits["training"] or limits["heldout"] or limits["paid_usd"]:
        raise ValueError("Only non-training, development, local simulation is authorized")
    stages = limits["stage_gpu_hours"]
    if set(stages) != {"prerequisites", "E1", "E2", "E3"} or any(not math.isfinite(v) or v <= 0 for v in stages.values()):
        raise ValueError("Invalid stage allocations")
    if sum(stages.values()) + limits["unallocated_gpu_hours"] > limits["gpu_hours_max"] or limits["unallocated_gpu_hours"] < 0:
        raise ValueError("Stage allocations exceed total authorization")


class Ledger:
    """Single writer, persistent occupancy accounting. Caller must hold lock."""
    def __init__(self, path, limits, now=time.time, monotonic=time.monotonic, boot=None):
        validate_limits(limits)
        self.path, self.limits, self.now, self.monotonic = Path(path), limits, now, monotonic
        self.boot = boot or Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        self.state = read(path) if self.path.exists() else {
            "campaign_id": limits["campaign_id"], "start_epoch": None,
            "start_monotonic": None, "boot_id": self.boot, "jobs": {}}
        if self.state["campaign_id"] != limits["campaign_id"]:
            raise ValueError("Campaign identity cannot reset an existing ledger")

    def save(self):
        write(self.path, self.state)

    def elapsed(self):
        if self.state["start_epoch"] is None:
            return 0
        elapsed = self.now()-self.state["start_epoch"]
        if self.state["boot_id"] == self.boot:
            elapsed = max(elapsed, self.monotonic()-self.state["start_monotonic"])
        elif elapsed < 0:
            raise RuntimeError("Clock moved backwards across reboot; manual accounting required")
        return elapsed

    def committed(self, stage=None):
        return sum(j.get("charged_s", j["reserved_s"]) for j in self.state["jobs"].values()
                   if stage is None or j["stage"] == stage)

    def reserve(self, key, stage, uuid, seconds, plan_sha):
        if key in self.state["jobs"]:
            raise RuntimeError("Job already attempted; preserve its result/denominator: " + key)
        if stage not in self.limits["stage_gpu_hours"] or not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("Invalid reservation")
        running = [j for j in self.state["jobs"].values() if j["status"] == "running"]
        if len(running) >= self.limits["concurrent_gpus_max"] or any(j["gpu_uuid"] == uuid for j in running):
            raise RuntimeError("GPU concurrency/ownership conflict")
        if self.committed()+seconds > self.limits["gpu_hours_max"]*3600:
            raise RuntimeError("Total GPU-hour limit exhausted")
        if self.committed(stage)+seconds > self.limits["stage_gpu_hours"][stage]*3600:
            raise RuntimeError("Stage GPU-hour limit exhausted; reserve is not automatically spendable")
        if self.elapsed()+seconds > self.limits["wall_hours_max"]*3600:
            raise RuntimeError("Continuous wall-clock deadline cannot accommodate this trial")
        now, mono = self.now(), self.monotonic()
        if self.state["start_epoch"] is None:
            self.state.update(start_epoch=now, start_monotonic=mono, boot_id=self.boot)
        self.state["jobs"][key] = {"stage": stage, "gpu_uuid": uuid, "reserved_s": seconds,
            "start_epoch": now, "start_monotonic": mono, "status": "running", "plan_sha256": plan_sha}
        self.save()

    def finish(self, key, outcome):
        job = self.state["jobs"][key]
        if job["status"] != "running":
            raise RuntimeError("Cannot charge an already finalized job")
        # Never clip a scheduler/OS overrun out of the resource account.
        job.update(status="finished", charged_s=max(0, self.monotonic()-job["start_monotonic"]), outcome=outcome)
        self.save()


def stop_group(process):
    # Always kill the private group, even if its leader exited with a live worker.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)


def assert_frozen(plan, cache=None):
    for path, value in plan["frozen_sha256"].items():
        stat = Path(path).stat()
        signature = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        # Full hashes on admission, then rehash any metadata change. Re-reading
        # every frozen video/trajectory for each trial would waste the window.
        if cache is not None and cache.get(path) == (value, signature):
            continue
        if digest(path) != value:
            raise RuntimeError("Frozen input/source changed: " + path)
        if cache is not None:
            cache[path] = (value, signature)


def output_bytes(path):
    return sum(p.stat().st_size for p in Path(path).rglob("*") if p.is_file() and not p.is_symlink())
