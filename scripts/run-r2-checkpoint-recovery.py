"""Bounded, cooler continuation of the unchanged debug pose checkpoint producer.

Only metadata persistence is replaced with fsync+rename. Native inference and
the original producer source remain unchanged, with both source hashes saved.
"""

import argparse
import errno
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


def main(args):
    storage_check(args.extraction)
    producer = PROJECT / "scripts/cache-r2-pose2d.py"
    spec = importlib.util.spec_from_file_location("r2_checkpoint_producer", producer)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cache = args.extraction / "pose2d-checkpoints"
    cache.mkdir(exist_ok=True)
    record = cache / f"durable-recovery-{time.time_ns()}.json"
    identity = {"status": "awaiting_verification", "scope": "Bounded debug recovery; not full source completion until producer says so", "producer_sha256": sha256(producer), "durable_metadata_wrapper_sha256": sha256(__file__), "metadata_writer_only_override": True, "inference_method_modified": False, "maximum_new_chunks": args.max_new_chunks, "maximum_temperature_before_chunk_c": args.maximum_temperature_c, "precision_model_augmentation_unchanged": True, "expectation": "Verify prior chunk hashes, keep exact inference, save at most three new 32-frame chunks after cool-down; fsync metadata before/after rename", "cloud_cost_usd": 0}
    durable_json(record, identity)
    snapshot = cache / f"durable-wrapper-{identity['durable_metadata_wrapper_sha256']}.py"
    if not snapshot.exists():
        with snapshot.open("xb") as stream:
            stream.write(Path(__file__).read_bytes()); stream.flush(); os.fsync(stream.fileno())
    module.write_json = durable_json
    options = argparse.Namespace(extraction=args.extraction, chunk_frames=32, max_new_chunks=args.max_new_chunks, minimum_start_free_mib=6144, maximum_temperature_c=args.maximum_temperature_c)
    try:
        code = module.run(options)
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
    parser.add_argument("--maximum-temperature-c", type=float, default=60)
    args = parser.parse_args()
    if not 1 <= args.max_new_chunks <= 3 or not 40 <= args.maximum_temperature_c <= 60:
        parser.error("Bounded recovery uses 1..3 chunks and a 40..60 C starting threshold")
    raise SystemExit(main(args))
