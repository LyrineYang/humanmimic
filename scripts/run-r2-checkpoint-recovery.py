"""Bounded, cooler continuation of the unchanged debug pose checkpoint producer.

Only metadata persistence is replaced with fsync+rename. Native inference and
the original producer source remain unchanged, with both source hashes saved.
"""

import argparse
import errno
import fcntl
import gc
import importlib.util
import json
import os
from pathlib import Path
import time

from r2_common import PROJECT, sha256, storage_check


def durable_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + f".{time.time_ns()}.tmp")
    with temporary.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    with path.open("rb") as stream:
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        try:
            os.fsync(directory)
        except OSError as error:
            if error.errno not in (errno.EINVAL, errno.ENOTSUP, errno.EBADF):
                raise
    finally:
        os.close(directory)


def run_cycles(module, options, args, record, identity):
    """Finite cohorts; release GPU tensors and cool fully between cohorts."""
    import torch
    with (args.extraction / "extraction.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for cycle in range(args.cycles):
            identity.update({"cycle": cycle + 1, "phase": "computing_bounded_cohort"})
            durable_json(record, identity)
            code = module.locked_run(options, args.extraction.resolve())
            gc.collect()
            if torch.cuda.is_initialized():
                torch.cuda.empty_cache()
            if code == 0 or cycle + 1 == args.cycles:
                return code
            if torch.cuda.is_initialized() and torch.cuda.memory_allocated() >= 100 * 1024**2:
                identity.update({"phase": "cuda_allocations_not_released", "framework_allocated_bytes": torch.cuda.memory_allocated()})
                durable_json(record, identity)
                return 3
            # No uninterrupted long GPU run: free weights, rest at least 30s,
            # then require <55C. This only schedules offline extraction.
            began = time.monotonic()
            while True:
                resource = module.resources()
                elapsed = time.monotonic() - began
                identity.update({"phase": "gpu_released_resting_between_cohorts", "rest_seconds": elapsed, "system_resource": resource, "framework_allocated_bytes": torch.cuda.memory_allocated() if torch.cuda.is_initialized() else 0})
                durable_json(record, identity)
                if elapsed >= 30 and resource["temperature_c"] < 55:
                    break
                if elapsed >= 120:
                    return 3
                time.sleep(5)


def main(args):
    storage_check(args.extraction)
    producer = PROJECT / "scripts/cache-r2-pose2d.py"
    spec = importlib.util.spec_from_file_location("r2_checkpoint_producer", producer)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cache = args.extraction / "pose2d-checkpoints"
    cache.mkdir(exist_ok=True)
    record = cache / f"durable-recovery-{time.time_ns()}.json"
    identity = {"status": "awaiting_verification", "scope": "Bounded debug recovery; not full source completion until producer says so", "producer_sha256": sha256(producer), "durable_metadata_wrapper_sha256": sha256(__file__), "metadata_writer_only_override": True, "inference_method_modified": False, "maximum_new_chunks_per_cohort": args.max_new_chunks, "maximum_cohorts": args.cycles, "minimum_rest_between_cohorts_seconds": 30, "maximum_temperature_before_next_cohort_c": 55, "maximum_temperature_before_chunk_c": args.maximum_temperature_c, "precision_model_augmentation_unchanged": True, "expectation": "Verify prior chunk hashes, keep exact inference, save at most three new 32-frame chunks per cohort after cool-down; release GPU weights and rest between at most four cohorts; fsync metadata before/after rename", "cloud_cost_usd": 0}
    durable_json(record, identity)
    snapshot = cache / f"durable-wrapper-{identity['durable_metadata_wrapper_sha256']}.py"
    if not snapshot.exists():
        with snapshot.open("xb") as stream:
            stream.write(Path(__file__).read_bytes()); stream.flush(); os.fsync(stream.fileno())
    module.write_json = durable_json
    options = argparse.Namespace(extraction=args.extraction, chunk_frames=32, max_new_chunks=args.max_new_chunks, minimum_start_free_mib=6144, maximum_temperature_c=args.maximum_temperature_c)
    try:
        code = run_cycles(module, options, args, record, identity)
    except Exception as error:
        identity.update({"status": "failed", "error": str(error)})
        durable_json(record, identity)
        raise
    identity.update({"status": "passed" if code == 0 else "awaiting_verification", "producer_exit_code": code, "whole_pose2d_complete": code == 0})
    durable_json(record, identity)
    print(json.dumps(identity, indent=2), flush=True)
    return code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--max-new-chunks", type=int, default=3)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--maximum-temperature-c", type=float, default=60)
    args = parser.parse_args()
    if not 1 <= args.max_new_chunks <= 3 or not 1 <= args.cycles <= 4 or not 40 <= args.maximum_temperature_c <= 60:
        parser.error("Bounded recovery uses 1..3 chunks/cohort, 1..4 cohorts and a 40..60 C starting threshold")
    raise SystemExit(main(args))
