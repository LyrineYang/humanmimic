#!/usr/bin/env python3
"""Estimator process: one public JSON payload on stdin, results on stdout.

No simulator objects or filesystem data paths cross this boundary. The Python
audit guard prevents accidental file/label access in cooperating project code;
it is not an OS sandbox against malicious native extensions.
"""
import copy
import json
import os
from pathlib import Path
import sys
import time

import torch
from r4_belief import BeliefEstimator
from r4_cuda import require_cuda
from r4_public import keys, finite, validate_frame
from r4_memory import EvidenceMemory
from r4_modalities import observation_view


def install_read_guard():
    # Torch optimizer imports may allocate an unused distributed-JIT temporary
    # directory. Clean that owned runtime directory before sealing file reads;
    # otherwise its atexit rmtree retries a denied directory open recursively.
    # Distributed JIT is outside this single-GPU, public-JSON worker contract.
    instantiator = sys.modules.get("torch.distributed.nn.jit.instantiator")
    if instantiator is not None:
        instantiator._TEMP_DIR.cleanup()
    runtime = Path(sys.prefix).resolve()
    code = Path(__file__).resolve().parent
    permitted_system = [Path(p) for p in ["/usr/lib", "/lib", "/lib64", "/usr/share/zoneinfo", "/proc/self", "/dev"]]
    reads = set()

    def within(path, root):
        return path == root or root in path.parents

    def audit(event, args):
        if event in {"subprocess.Popen", "os.system", "socket.connect", "socket.bind"}:
            raise PermissionError("Estimator may not spawn processes or access the network")
        if event != "open" or isinstance(args[0], int):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            raise PermissionError("Estimator output uses stdout only")
        allowed = within(path, runtime) or any(within(path, p) for p in permitted_system)
        allowed |= path.parent == code and path.suffix == ".py"
        allowed |= path.name in {"ld.so.cache", "localtime"} and path.parent == Path("/etc")
        if not allowed:
            raise PermissionError("Estimator denied a non-runtime file read")
        reads.add(str(path))
    sys.dont_write_bytecode = True
    sys.addaudithook(audit)
    return reads


def keyframes(frames):
    """10 Hz keyframes, retaining all sensor arrivals between keyframes."""
    result, pending, previous = [], [], -1
    for index, frame in enumerate(frames):
        validate_frame(frame, previous)
        previous = frame["time_s"]
        pending.extend(frame["tactile"])
        if not result or frame["time_s"] - result[-1]["time_s"] >= .1 - 1e-9 or index == len(frames)-1:
            selected = copy.deepcopy(frame)
            selected["tactile"] = pending
            result.append(selected)
            pending = []
    return result


def replay(payload, device):
    keys(payload, {"calibration", "prior", "frames", "config", "modality", "ablation", "seed", "occlusion"}, {"memory_mode", "object_id", "episode_id"})
    cfg = payload["config"]
    keys(cfg, {"window_frames", "maximum_points", "maximum_vertices", "shape_modes", "steps", "learning_rate",
               "translation_scale_m", "rotation_scale_rad", "shape_scale_m",
               "maximum_displacement_m", "maximum_compliance_m_per_n", "kernel_radius_m", "correspondence_radius_m",
               "neighbors", "surface_sigma_m", "shape_prior_sigma_m",
               "compliance_prior_sigma_m_per_n", "minimum_force_span_n", "minimum_force_samples", "maximum_support_radius_m",
               "huber_delta", "information_relative_threshold", "information_absolute_threshold", "maximum_wall_s", "seed"},
         {"information_batch_size"})
    finite(cfg)
    if any(type(value) not in {int, float} or value <= 0 for key, value in cfg.items() if key != "seed"):
        raise ValueError("Estimator configuration must contain positive finite scalars")
    if cfg["shape_modes"] > 64 or cfg["neighbors"] > 32:
        raise ValueError("Local shape/correspondence budget exceeded")
    if type(cfg.get("information_batch_size", 1)) is not int or not 1 <= cfg.get("information_batch_size", 1) <= 64:
        raise ValueError("Invalid information batch size")
    if not 1 <= cfg["steps"] <= 200 or not 1 <= cfg["maximum_points"] <= 4096 or not 16 <= cfg["maximum_vertices"] <= 2048:
        raise ValueError("R4 geometry budget exceeded")
    if not 1 <= cfg["window_frames"] <= 8 or not 0 < cfg["maximum_wall_s"] <= 300:
        raise ValueError("R4 window/wall budget exceeded")
    torch.manual_seed(payload["seed"])
    torch.cuda.manual_seed_all(payload["seed"])
    torch.use_deterministic_algorithms(True)
    frames = keyframes(payload["frames"])
    frames = [frame for frame in frames if frame["time_s"] >= payload["prior"]["initial_time_s"]]
    if not frames:
        raise ValueError("No observations at or after prior initialization")
    frames = observation_view(frames, payload["calibration"], payload["modality"], device)
    occlusion = payload["occlusion"]
    if occlusion not in {0.0, .5, .8}:
        raise ValueError("Use the preregistered E1 occlusion fractions")
    # A fixed directional crop models occlusion, not iid random point removal.
    # Identical crop/seed across modalities; no evaluation geometry is consulted.
    for frame in frames:
        vision = frame["vision"]
        if vision and len(vision["points_world_m"]) and occlusion:
            points = torch.tensor(vision["points_world_m"], device=device, dtype=torch.float64)
            keep = points[:, 0] >= torch.quantile(points[:, 0], occlusion)
            normals = torch.tensor(vision["normals_world"], device=device, dtype=torch.float64)
            vision["points_world_m"], vision["normals_world"] = points[keep].tolist(), normals[keep].tolist()
    estimator = BeliefEstimator(payload["prior"], payload["calibration"], cfg, device, payload["modality"], payload["ablation"])
    width = cfg["window_frames"]
    ends = list(range(min(width, len(frames)), len(frames)+1, max(1, width//2)))
    if ends[-1] != len(frames):
        ends.append(len(frames))
    if len(ends) > cfg["steps"]:
        raise ValueError("Sequence too long for declared update budget")
    deadline = time.monotonic() + cfg["maximum_wall_s"]
    results = []
    memory = None
    if payload.get("memory_mode"):
        memory = EvidenceMemory(device, payload["object_id"], payload["episode_id"], force_threshold_n=payload["calibration"]["threshold_n"],
                                tactile_mode="binary" if payload["modality"] == "VB" else "force")
    memory_cursor = 0
    for i, end in enumerate(ends):
        budget = cfg["steps"] // len(ends) + int(i < cfg["steps"] % len(ends))
        selected = frames[max(0, end-width):end]
        if memory is not None:
            for frame in frames[memory_cursor:end]:
                memory.append(frame, payload["object_id"], payload["episode_id"])
            memory_cursor = end
            selected = memory.select(payload["memory_mode"])
            estimator.pose_initializations = memory.pose_cache
        belief = estimator.fit(selected, steps=budget, wall_deadline=deadline)
        if memory is not None:
            memory.commit(belief)
            belief["memory"] = memory.summary(selected)
        results.append(belief)
    torch.cuda.synchronize(device)
    return {"status": "awaiting_verification", "execution_status": "completed", "modality": payload["modality"],
            "ablation": payload["ablation"], "occlusion": occlusion, "heldout_used": False,
            "gradient_steps": sum(item.get("steps", 0) for item in results), "beliefs": results,
            "boundary": "Public sensor bundle only; output beliefs are not acceptance evidence without independent evaluation"}


def main():
    device, gpu = require_cuda()
    # Import optimizer dependencies before closing the file boundary; no fitting
    # or CPU numerical probe is performed here.
    torch.optim.Adam([torch.zeros(1, device=device, requires_grad=True)])
    payload = json.load(sys.stdin)
    reads = install_read_guard()
    try:
        with (Path(__file__).resolve().parents[1] / "PLAN.md").open() as forbidden:
            forbidden.read(1)
    except PermissionError:
        guard_denied = True
    else:
        raise RuntimeError("Estimator file boundary did not deny a project data read")
    result = replay(payload, device)
    result["gpu"] = gpu
    result["runtime_file_reads"] = sorted(reads)
    result["read_guard_probe_denied"] = guard_denied
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()
