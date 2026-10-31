"""Re-run all five debug controls on verified video caches in fresh run IDs.

No new motion inference. Previous canonical results stay intact. The derived
draft is adopted only after review; heldout inputs/annotations stay unchanged.
"""

import argparse
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import time

from r2_common import PROJECT, STORAGE, sha256, storage_check, write_json
from r2_cache import verify_cached_extraction

CODE = ("run-r2-physical.py", "evaluate-r2-body.py", "r2_initialization.py", "render-r2-demo.py", "r2_geometry.py", "r2_cache.py", "run-r2-suite.py", "audit-r2-run.py", "run-r2-cached-suite.py")


def runtime_identity():
    sonic = PROJECT / "vendor/GR00T-WholeBodyControl"
    policy = PROJECT / "models/sonic-default/policy/release"
    return {"gpu_driver": subprocess.check_output(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"], text=True).strip(),
            "binary_sha256": sha256(sonic / "gear_sonic_deploy/target/release/g1_deploy_onnx_ref"),
            "r1_simulator_sha256": sha256(PROJECT / "scripts/run-r1-reproduction.py"),
            "evaluation_sha256": sha256(PROJECT / "configs/r1-evaluation.json"), "dds_sha256": sha256(PROJECT / "configs/r1-dds.xml"),
            "policy_sha256": {name: sha256(policy / name) for name in ("model_encoder.onnx", "model_decoder.onnx", "observation_config.yaml")}}


def main(args):
    storage_check(args.output)
    spec = importlib.util.spec_from_file_location("r2_cached_pipeline", PROJECT / "scripts/run-r2-suite.py")
    pipeline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pipeline)
    pipeline.throughput_policy()
    if pipeline.active_tasks():
        raise RuntimeError("Another model/control queue is active")
    manifest = json.loads(args.manifest.read_text())
    if manifest["status"] != "draft" or len(manifest["debug"]) != 5:
        raise ValueError("Use the unchanged reviewed five-debug draft before heldout freeze")
    args.output.mkdir(parents=True, exist_ok=True)
    if not (args.output / "expectation.json").exists():
        raise ValueError("Record the regression expectation before execution")
    versions = {name: sha256(PROJECT / "scripts" / name) for name in CODE}
    runtime = runtime_identity()
    runtime_path = args.output / "runtime-identity.json"
    if runtime_path.exists():
        if json.loads(runtime_path.read_text()) != runtime:
            raise ValueError("Regression hardware/policy/evaluation changed")
    else:
        write_json(runtime_path, runtime)
    version_path = args.output / "code-identity.json"
    if version_path.exists():
        if json.loads(version_path.read_text()) != versions:
            raise ValueError("Regression code changed; preserve prior runs and use a new batch")
    else:
        write_json(version_path, versions)
        snapshot = args.output / "source"
        snapshot.mkdir()
        for name in CODE:
            shutil.copy2(PROJECT / "scripts" / name, snapshot / name)
    derived = copy.deepcopy(manifest)
    for item in derived["debug"]:
        old_run_id, old_audit = item["run_id"], Path(item["audit_json"])
        old_run = STORAGE / "runs" / old_run_id
        origin = (old_run / "extraction").resolve()
        verified = verify_cached_extraction(origin)
        if verified["summary"]["source_sha256"] != item["source_sha256"] or verified["summary"]["role"] != "debug":
            raise ValueError("Cache belongs to another source or role")
        new_id = f"r2-debug-init-{item['id']}-20261101-01"
        run = STORAGE / "runs" / new_id
        run.mkdir(exist_ok=True)
        if not (run / "extraction").exists():
            (run / "extraction").symlink_to(origin, target_is_directory=True)
        elif (run / "extraction").resolve() != origin:
            raise ValueError("Existing replay run points to another extraction")
        reuse = {"scope": "Verified cached video extraction reused; actual physics/evaluation are new", "origin_extraction": str(origin), "fingerprint": verified["fingerprint"], "new_ml_inference": False, "original_source_sha256": item["source_sha256"]}
        cache_path = run / "cached-extraction-reuse.json"
        if cache_path.exists():
            if json.loads(cache_path.read_text()) != reuse:
                raise ValueError("Recorded cache reuse changed")
        else:
            write_json(cache_path, reuse)
        diagnostic = max(old_run.glob("extraction-diagnostics*.json"), key=lambda path: path.stat().st_mtime_ns, default=None)
        if diagnostic and not (run / "extraction-diagnostics.json").exists():
            record = json.loads(diagnostic.read_text())
            if record["source_sha256"] != item["source_sha256"]:
                raise ValueError("Existing extraction diagnostic belongs to another source")
            record.update(reused_from=str(diagnostic), new_inference=False)
            write_json(run / "extraction-diagnostics.json", record)
        previous = {"run_id": old_run_id, "audit_json": str(old_audit), "audit_sha256": sha256(old_audit), "status": json.loads(old_audit.read_text())["status"], "reason": "Uniform initialization regression; all original attempts retained"}
        item.setdefault("previous_attempts", []).append(previous)
        item.update(run_id=new_id, audit_json=str(run / "run-audit.json"), extraction_reused_from=str(origin))
        link = PROJECT / "runs" / new_id
        if not link.exists():
            link.symlink_to(run, target_is_directory=True)
    derived_path = args.output / "replay-manifest.json"
    if derived_path.exists():
        if json.loads(derived_path.read_text()) != derived:
            raise ValueError("Prepared replay draft changed")
    else:
        write_json(derived_path, derived)
    if args.prepare_only:
        print(json.dumps({"status": "passed", "scope": "Five debug cache-replay preparation only; no new control/inference", "derived_draft": str(derived_path)}, indent=2))
        return 0
    rows = []
    for item in derived["debug"]:
        pipeline.throughput_policy()
        if any(sha256(PROJECT / "scripts" / name) != digest for name, digest in versions.items()):
            raise ValueError("Frozen debug regression implementation changed")
        if runtime_identity() != runtime:
            raise ValueError("Regression hardware/policy/evaluation changed")
        write_json(args.output / "progress.json", {"status": "awaiting_verification", "active_source": item["id"], "sources": rows, "mode": "cached video extraction, new actual control", "heldout_used": False, "cloud_cost_usd": 0})
        result = pipeline.run_video(item, "debug", derived, derived_path)
        rows.append(result)
        print(json.dumps(result), flush=True)
    status = "failed" if any(row["status"] == "failed" for row in rows) else "awaiting_verification" if any(row["status"] == "awaiting_verification" for row in rows) else "passed"
    write_json(args.output / "progress.json", {"status": status, "scope": "Five-debug uniform initialization regression only; heldout/suite acceptance separate", "sources": rows, "derived_draft": str(derived_path), "heldout_used": False, "cloud_cost_usd": 0, "finished_unix": time.time()})
    return {"passed": 0, "failed": 1, "awaiting_verification": 2}[status]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    raise SystemExit(main(args))
