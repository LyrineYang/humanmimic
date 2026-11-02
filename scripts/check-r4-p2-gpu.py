#!/usr/bin/env python3
"""CUDA acceptance: joint inference, degeneracy, truth isolation and coverage.

All numeric fixtures and inference/evaluation run on the selected GPU. No CPU
fallback. Synthetic inference checks are reported separately from real LEAP.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import torch

from r4_contract import sha256, write_json
from r4_cuda import require_cuda
from r4_gpu_fixtures import fixture
from r4_replay import launch

ACTIVE_OUTPUT = None


from r4_fixture_evaluation import evaluate


def fingerprint(result):
    # Runtime timing/allocation vary; compare ALL estimated states, covariances,
    # events and objective traces, not only a cherry-picked final scalar.
    beliefs = copy.deepcopy(result["beliefs"])
    for belief in beliefs:
        belief.pop("wall_s", None)
        belief.pop("peak_cuda_bytes", None)
    return hashlib.sha256(json.dumps(beliefs, sort_keys=True, allow_nan=False).encode()).hexdigest()


def main():
    global ACTIVE_OUTPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[1]/"configs/r4-p1p2.json")
    parser.add_argument("--coverage", action="store_true", help="Additional preregistered 20-seed coverage experiment")
    parser.add_argument("--joint-only", action="store_true", help="Focused joint numerical regression; not the full P2 suite")
    args = parser.parse_args()
    device, gpu = require_cuda()
    config = json.loads(args.config.read_text())
    cfg, bounds = config["estimator"], config["acceptance"]
    args.output.mkdir(parents=True, exist_ok=False)
    ACTIVE_OUTPUT = args.output
    write_json(args.output/"manifest.json", {"status": "running", "gpu": gpu, "config_sha256": sha256(args.config),
        "source_sha256": {p.name: sha256(p) for p in Path(__file__).parent.glob("*r4*.py")}, "heldout_used": False})
    checks, metrics = {}, {}
    payload, truth = fixture(device, cfg)
    private = args.output/"private-evaluation"
    private.mkdir(mode=0o700)
    write_json(private/"truth.json", truth)
    write_json(private/"truth-original.json", truth)
    result = launch(payload, args.output/"joint", cfg["maximum_wall_s"]+120)
    metrics["joint"] = evaluate(result, truth, device)
    checks["read_guard_denied_project_data"] = result["read_guard_probe_denied"]
    m = metrics["joint"]
    checks["joint_estimate"] = m.get("state_updated", False) and m["position_rmse_m"] <= bounds["pose_translation_tolerance_m"] and m["shape_surface_rmse_m"] <= bounds["shape_rmse_tolerance_m"] and m["compliance_error_m_per_n"] <= bounds["compliance_tolerance_m_per_n"] and m["compliance_observable"]
    if args.joint_only:
        write_json(args.output/"result.json", {"status": "passed" if all(checks.values()) else "failed", "checks": checks,
            "metrics": metrics, "scope": "focused joint GPU regression only", "gpu": gpu, "heldout_used": False})
        manifest = json.loads((args.output/"manifest.json").read_text())
        manifest.update(status="complete", result_sha256=sha256(args.output/"result.json"))
        write_json(args.output/"manifest.json", manifest)
        if not all(checks.values()):
            sys.exit(1)
        return
    # Changing private labels after acquisition must not change the estimator.
    write_json(private/"truth-mutated.json", {"role": "evaluation_only", "poses": [999], "friction": 999})
    write_json(private/"truth.json", {"role": "evaluation_only", "poses": [999], "stiffness": -999})
    repeated = launch(payload, args.output/"truth-mutation", cfg["maximum_wall_s"]+120)
    checks["private_truth_mutation_invariance"] = fingerprint(result) == fingerprint(repeated)
    for name, kwargs in {"constant_load": {"constant_force": True}, "fully_missing": {"missing_vision": True, "dropout": True},
                         "saturated": {"saturated": True}, "unanchored_constant": {"missing_vision": True, "constant_force": True}}.items():
        candidate, labels = fixture(device, cfg, **kwargs)
        actual = launch(candidate, args.output/name, cfg["maximum_wall_s"]+120)
        belief = actual["beliefs"][-1]
        if name == "fully_missing":
            checks[name] = not belief["state_updated"] and belief["inference_status"] == "unobservable"
        elif name == "saturated":
            checks[name] = belief.get("accepted_contact_taxels", 0) == 0 and not belief.get("compliance_observable", False)
        else:
            checks[name] = not belief.get("compliance_observable", False) and not belief.get("force_excited", False)
    for modality, ablation in [("V", "joint"), ("VB", "joint"), ("VF", "pose_only"), ("VF", "shape_only"), ("VF", "rigid_contact")]:
        candidate = copy.deepcopy(payload)
        candidate.update(modality=modality, ablation=ablation)
        name = f"{modality}-{ablation}"
        actual = launch(candidate, args.output/name, cfg["maximum_wall_s"]+120)
        metrics[name] = evaluate(actual, truth, device)
        checks[name+"_finite"] = metrics[name]["state_updated"]
    stale = copy.deepcopy(payload)
    for frame in stale["frames"]:
        if frame["time_s"] < .2:
            frame["tactile"] = []
        else:
            frame["tactile"][0]["time_s"] = frame["time_s"] - .2
    stale_result = launch(stale, args.output/"stale", cfg["maximum_wall_s"]+120)
    stale_belief = stale_result["beliefs"][-1]
    checks["stale_not_no_contact"] = stale_belief["accepted_contact_taxels"] == 0 and all(e["state"] == "missing_or_stale" for e in stale_belief["events"])
    # Strict input/schema failure checks execute inside an already admitted GPU run.
    from r4_public import validate_frame
    for name in ["truth_field", "future_packet"]:
        frame = copy.deepcopy(payload["frames"][0])
        if name == "truth_field":
            frame["ground_truth_object_pose"] = truth["poses"][0]
        else:
            frame["tactile"][0]["time_s"] = 1
        try:
            validate_frame(frame)
            checks[name+"_rejected"] = False
        except ValueError:
            checks[name+"_rejected"] = True
    coverage = {"status": "awaiting_verification", "reason": "Run --coverage; calibration is not inferred from a fit"}
    if args.coverage:
        observations = []
        for seed in range(2101, 2101+bounds["coverage_trials"]):
            candidate, labels = fixture(device, cfg, seed=seed)
            actual = launch(candidate, args.output/f"coverage-{seed}", cfg["maximum_wall_s"]+120)
            observations.append(evaluate(actual, labels, device))
        # Missing/unobservable trials remain in the denominator.
        covered = sum(item.get("pose_observable", False) and item.get("pose_covered", False) and item.get("compliance_covered", False) for item in observations)
        fraction = covered / len(observations)
        checks["coverage"] = fraction >= bounds["coverage_minimum"]
        coverage = {"status": "passed" if checks["coverage"] else "failed", "fraction": fraction, "trials": observations,
                    "scope": "Analytic independent ellipsoid fixture only; not calibrated LEAP uncertainty"}
    write_json(args.output/"result.json", {"status": "passed" if all(checks.values()) else "failed", "checks": checks,
        "metrics": metrics, "coverage": coverage, "gpu": gpu, "heldout_used": False,
        "scope": "P2 GPU implementation checks; not manipulation success or full P1/P2 acceptance"})
    manifest = json.loads((args.output/"manifest.json").read_text())
    manifest.update(status="complete", result_sha256=sha256(args.output/"result.json"))
    write_json(args.output/"manifest.json", manifest)
    if not all(checks.values()):
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        if ACTIVE_OUTPUT is not None:
            path = ACTIVE_OUTPUT/"manifest.json"
            manifest = json.loads(path.read_text()) if path.exists() else {}
            manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
            write_json(path, manifest)
        raise
