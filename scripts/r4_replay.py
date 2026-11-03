#!/usr/bin/env python3
"""Launch isolated CUDA estimation from a public observation bundle."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from r4_contract import sha256, write_json
from r4_public import read_public


def launch(payload, output, timeout):
    output.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).resolve().parent
    wire = json.dumps(payload, allow_nan=False, sort_keys=True).encode()
    manifest = {"status": "running", "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "launcher_pid": os.getpid(), "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                "public_payload_sha256": hashlib.sha256(wire).hexdigest(), "heldout_used": False,
                "source_sha256": {name: sha256(source/name) for name in ["r4_belief.py", "r4_public.py", "r4_modalities.py", "r4_cuda.py", "r4_memory.py", "r4_estimator_worker.py", "r4_replay.py", "run-r4-belief-gpu.py"]},
                "config": payload["config"], "modality": payload["modality"], "ablation": payload["ablation"],
                "seed": payload["seed"], "occlusion": payload["occlusion"],
                "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES")}
    write_json(output / "manifest.json", manifest)
    # No truth path, object asset root, inherited open log fd or user PYTHONPATH.
    environment = {k: os.environ[k] for k in ["PATH", "LD_LIBRARY_PATH", "CUDA_VISIBLE_DEVICES", "CONDA_PREFIX", "R4_ENV_PREFIX", "PYTORCH_KERNEL_CACHE_PATH", "CUDA_CACHE_PATH"] if k in os.environ}
    environment.update({"OMP_NUM_THREADS": "8", "MKL_NUM_THREADS": "8", "OPENBLAS_NUM_THREADS": "8",
                        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1", "CUBLAS_WORKSPACE_CONFIG": ":4096:8"})
    with (output / "worker.stderr.log").open("wb") as error, (output / "belief.json").open("wb") as result:
        process = subprocess.Popen([sys.executable, "-B", str(source / "r4_estimator_worker.py")], stdin=subprocess.PIPE,
                                    stdout=result, stderr=error, env=environment, cwd=source, close_fds=True,
                                    start_new_session=os.environ.get("R4_CAMPAIGN_PROCESS_GROUP") != "1")
        manifest["worker_pid"] = process.pid
        write_json(output / "manifest.json", manifest)
        try:
            process.communicate(wire, timeout=timeout)
            if process.returncode:
                raise RuntimeError(f"Estimator exited {process.returncode}; see worker.stderr.log")
            result.flush()
            parsed = json.loads((output / "belief.json").read_text())
            if parsed["execution_status"] != "completed":
                raise RuntimeError("Incomplete estimator response")
            manifest["status"] = "complete"
            manifest["acceptance_status"] = "awaiting_verification"
            manifest["result_sha256"] = sha256(output / "belief.json")
        except BaseException as exc:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            manifest["status"] = "failed"
            manifest["error"] = str(exc)
            raise
        finally:
            write_json(output / "manifest.json", manifest)
    return parsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--prior", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[1]/"configs/r4-p1p2.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--modality", choices=["V", "VB", "VF"], default="VF")
    parser.add_argument("--ablation", choices=["joint", "pose_only", "shape_only", "rigid_contact"], default="joint")
    parser.add_argument("--occlusion", type=float, choices=[0, .5, .8], default=0)
    parser.add_argument("--seed", type=int, default=1101)
    parser.add_argument("--memory", choices=["single", "recent", "diverse"])
    parser.add_argument("--object-id")
    parser.add_argument("--episode-id")
    args = parser.parse_args()
    if args.observations.resolve() == args.output.resolve() or args.observations.resolve() in args.output.resolve().parents:
        raise ValueError("Output must be separate from the immutable public observations")
    payload = read_public(args.observations, args.prior)
    config = json.loads(args.config.read_text())["estimator"]
    payload.update(config=config, modality=args.modality, ablation=args.ablation, seed=args.seed, occlusion=args.occlusion)
    if args.memory:
        if not args.object_id or not args.episode_id:
            raise ValueError("Memory requires explicit object and episode identities")
        payload.update(memory_mode=args.memory, object_id=args.object_id, episode_id=args.episode_id)
    launch(payload, args.output, config["maximum_wall_s"] + 120)


if __name__ == "__main__":
    main()
