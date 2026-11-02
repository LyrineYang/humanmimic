#!/usr/bin/env python3
"""Prepare or execute paired E1 GPU replays; immutable recorded trajectories.

Manifest: {"split":"debug", "records":[{"object_id":...,"seed":1101,
"observations":"/absolute/public-observations", "prior":"/absolute/prior.json",
"evaluation_scene":"/absolute/evaluation.json", "actual_state":"/absolute/actual-state.npz",
"collection_manifest":"/absolute/collection/manifest.json"}]}.
36 object/seed records x 3 occlusions x 3 modalities = 324 planned E1 replays.
No collector, controller change, training or heldout execution is invoked here.
"""
import argparse
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys

from r4_contract import sha256, write_json
from r4_public import keys, read_public
from r4_replay import launch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[1]/"configs/r4-p1p2.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="Without this flag, only materialize the immutable execution plan")
    parser.add_argument("--ablations", action="store_true", help="Separate pose_only/shape_only/rigid_contact extension; not part of the 324 core replays")
    args = parser.parse_args()
    manifest = json.loads(args.records.read_text())
    if manifest.get("split") != "debug" or not 1 <= len(manifest["records"]) <= 36:
        raise ValueError("Only up to 36 development object/seed recordings are accepted")
    cfg = json.loads(args.config.read_text())["estimator"]
    identities = set()
    allowed_objects = {f"{family}-{seed}" for family, seeds in
        [("stepped_prism", range(101, 104)), ("grooved_block", range(104, 107)),
         ("necked_column", range(107, 110)), ("u_handle", range(110, 113))] for seed in seeds}
    cases, record_hashes = [], []
    for record in manifest["records"]:
        keys(record, {"object_id", "seed", "observations", "prior", "evaluation_scene", "actual_state", "collection_manifest"})
        identity = (record["object_id"], record["seed"])
        if identity in identities or record["seed"] not in [1101, 1102, 1103]:
            raise ValueError("Duplicate object/seed or undeclared E1 seed")
        if record["object_id"] not in allowed_objects:
            raise ValueError("Only the 12 declared development objects are accepted; heldout is disabled")
        identities.add(identity)
        for field in ["observations", "prior", "evaluation_scene", "actual_state", "collection_manifest"]:
            if not Path(record[field]).is_absolute():
                raise ValueError("Use explicit absolute input paths")
        public = Path(record["observations"])
        # Read/validate only the public bundle here; private labels stay in the
        # separate evaluator subprocess and never join an estimator payload.
        bundle = read_public(public, Path(record["prior"]))
        if any(frame["split"] != "debug" for frame in bundle["frames"]):
            raise ValueError("E1 requires development recordings, not readiness or heldout data")
        hashes = {"observations": sha256(public/"observations.jsonl"), "calibration": sha256(public/"calibration.json"),
                  "prior": sha256(Path(record["prior"])), "evaluation_scene": sha256(Path(record["evaluation_scene"])),
                  "actual_state": sha256(Path(record["actual_state"])), "collection_manifest": sha256(Path(record["collection_manifest"]))}
        collection = json.loads(Path(record["collection_manifest"]).read_text())
        if collection.get("status") != "complete" or collection.get("split") != "debug":
            raise ValueError("Collection is not a completed development run")
        if collection.get("object_id") != record["object_id"] or collection.get("sensor_seed") != record["seed"]:
            raise ValueError("Object/seed labels do not match the original collection")
        if (collection.get("public_artifacts_sha256") != {"observations.jsonl": hashes["observations"], "calibration.json": hashes["calibration"]}
                or collection.get("actual_state_sha256") != hashes["actual_state"]
                or collection.get("evaluation_scene_sha256") != hashes["evaluation_scene"]):
            raise ValueError("Public observations and private evaluation do not match the same recorded run")
        record_hashes.append(hashes)
        variants = [(m, "joint") for m in ["V", "VB", "VF"]]
        if args.ablations:
            variants += [("VF", a) for a in ["pose_only", "shape_only", "rigid_contact"]]
        for occlusion, (modality, ablation) in itertools.product([0, .5, .8], variants):
            cases.append({"record": len(record_hashes)-1, "object_id": identity[0], "seed": identity[1],
                          "occlusion": occlusion, "modality": modality, "ablation": ablation})
    args.output.mkdir(parents=True, exist_ok=False)
    plan = {"status": "awaiting_verification", "records_manifest_sha256": sha256(args.records),
            "config_sha256": sha256(args.config), "record_hashes": record_hashes, "cases": cases, "heldout_used": False,
            "wall_upper_seconds": len(cases)*(cfg["maximum_wall_s"]+120+120), "paid_usd": 0,
            "input_pairs": "same frozen observation/prior/trajectory per object/seed for every modality/ablation",
            "source_sha256": {p.name: sha256(p) for p in Path(__file__).parent.glob("*r4*.py")}}
    write_json(args.output/"plan.json", plan)
    if not args.execute:
        return
    from r4_cuda import require_cuda
    _, gpu = require_cuda()
    outcomes = []
    for index, case in enumerate(cases):
        record = manifest["records"][case["record"]]
        public = Path(record["observations"])
        current_hash = {"observations": sha256(public/"observations.jsonl"), "calibration": sha256(public/"calibration.json"),
                        "prior": sha256(Path(record["prior"])), "evaluation_scene": sha256(Path(record["evaluation_scene"])), "actual_state": sha256(Path(record["actual_state"])),
                        "collection_manifest": sha256(Path(record["collection_manifest"]))}
        if current_hash != record_hashes[case["record"]]:
            raise RuntimeError("Frozen input changed; abort paired study")
        result_dir = args.output/f"case-{index:04d}"
        payload = read_public(public, Path(record["prior"]))
        payload.update(config=cfg, modality=case["modality"], ablation=case["ablation"], seed=case["seed"], occlusion=case["occlusion"])
        try:
            launch(payload, result_dir, cfg["maximum_wall_s"]+120)
            command = [sys.executable, str(Path(__file__).with_name("evaluate-r4-belief-gpu.py")), "--belief", str(result_dir/"belief.json"),
                       "--prior", record["prior"], "--evaluation-scene", record["evaluation_scene"], "--actual-state", record["actual_state"],
                       "--output", str(result_dir/"evaluation")]
            with (result_dir/"evaluation.log").open("w") as log:
                subprocess.run(command, check=True, timeout=120, stdout=log, stderr=subprocess.STDOUT, close_fds=True)
            outcomes.append({**case, "execution_status": "completed", "acceptance_status": "awaiting_verification", "path": str(result_dir)})
        except Exception as exc:
            outcomes.append({**case, "execution_status": "failed", "error": str(exc), "path": str(result_dir)})
        write_json(args.output/"progress.json", {"status": "running", "pid": os.getpid(), "gpu": gpu, "outcomes": outcomes})
    write_json(args.output/"progress.json", {"status": "complete", "gpu": gpu, "outcomes": outcomes,
        "acceptance_status": "awaiting_verification", "heldout_used": False,
        "boundary": "E1 perception metrics only; no physical manipulation precision claim"})
    if any(item["execution_status"] == "failed" for item in outcomes):
        sys.exit(1)


if __name__ == "__main__":
    main()
