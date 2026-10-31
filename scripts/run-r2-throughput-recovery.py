"""Native-speed checkpoint recovery under the user's throughput policy."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import time

from r2_common import PROJECT, sha256, storage_check


def module_from(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(args):
    began = time.monotonic()
    storage_check(args.extraction)
    policy_path = PROJECT / "configs/r2-execution-policy.json"
    policy = json.loads(policy_path.read_text())
    boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    if boot != policy["local_boot_id_authorized"]:
        raise RuntimeError("Local boot changed: user requested server handoff instead of more local retries")
    if policy["execution_priority"] != "throughput" or policy["software_temperature_gates"]:
        raise ValueError("Explicit throughput policy is required")
    producer = module_from(PROJECT / "scripts/cache-r2-pose2d.py", "r2_native_checkpoint_producer")
    durable = module_from(PROJECT / "scripts/run-r2-checkpoint-recovery.py", "r2_durable_checkpoint_metadata").durable_json
    producer.write_json = durable
    cache = args.extraction / "pose2d-checkpoints"
    cache.mkdir(exist_ok=True)
    stamp = time.time_ns()
    record = cache / f"throughput-attempt-{stamp}.json"
    identity = {"status": "awaiting_verification", "scope": "Native-speed official numerical producer with durable32-frame checkpoints", "wrapper_sha256": sha256(__file__), "native_producer_sha256": sha256(PROJECT / "scripts/cache-r2-pose2d.py"), "execution_policy_sha256": sha256(policy_path), "boot_id": boot, "started_unix": time.time(), "temperature_observation_only": True, "artificial_frame_idle_seconds": 0, "inference_method_modified": False, "precision_crop_augmentation_timestamps_unchanged": True, "cloud_cost_usd": 0}
    durable(record, identity)
    source = cache / ("throughput-source-" + identity["wrapper_sha256"] + ".py")
    if not source.exists():
        with source.open("xb") as stream:
            stream.write(Path(__file__).read_bytes()); stream.flush(); os.fsync(stream.fileno())
    elif sha256(source) != identity["wrapper_sha256"]:
        raise ValueError("Preserve damaged recovery source before resuming")
    # Infinity explicitly disables only the producer's software temperature
    # wait. Recorded temperatures are real; GPU hardware limits are untouched.
    options = argparse.Namespace(extraction=args.extraction, chunk_frames=32, max_new_chunks=0, minimum_start_free_mib=6144, maximum_temperature_c=float("inf"))
    try:
        code = producer.run(options)
        identity.update(status="passed" if code == 0 else "awaiting_verification", producer_exit_code=code, whole_pose2d_complete=code == 0)
        if code == 0:
            marker = json.loads((args.extraction / "pose2d-complete.json").read_text())
            marker.update(throughput_wrapper_sha256=identity["wrapper_sha256"], execution_policy_sha256=identity["execution_policy_sha256"], temperature_observation_only=True)
            durable(args.extraction / "pose2d-complete.json", marker)
    except Exception as error:
        identity.update(status="failed", reason=str(error), whole_pose2d_complete=False)
        raise
    finally:
        identity["wall_seconds"] = time.monotonic() - began
        durable(record, identity)
    print(json.dumps(identity, indent=2), flush=True)
    return code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extraction", type=Path, required=True)
    raise SystemExit(run(parser.parse_args()))
