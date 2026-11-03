#!/usr/bin/env python3
"""Synthetic CUDA analysis checks; no research result and no CPU fallback."""
import argparse
import copy
import importlib.util
from pathlib import Path
from r4_campaign import ROOT, digest, read, write
from r4_cuda import require_cuda


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT/"scripts"/name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    device, gpu = require_cuda()
    config = read(ROOT/"configs/r4-e3-campaign.json")
    rows = load("run-r4-campaign.py").matrix(config)
    for row in rows:
        row["gpu_uuid"] = "fixture-slot-"+str(row["slot"])
    analyze = load("analyze-r4-campaign-gpu.py").analyze
    outcomes = {r["id"]: {"execution_status": "completed", "task_status": "passed",
                "penalized_position_error_m": .002 if r.get("probe") == "task_risk_reduction" else .004} for r in rows}
    result = analyze(rows, outcomes, config, device)
    checks = {"positive_E3": result["status"] == "passed" and abs(result["primary"]["relative_error_reduction"]-.5) < 1e-10}
    equal = copy.deepcopy(outcomes)
    for v in equal.values(): v["penalized_position_error_m"] = .004
    checks["equal_strategies_fail"] = analyze(rows, equal, config, device)["status"] == "failed"
    for r in rows:
        if r.get("probe") == "task_risk_reduction": equal[r["id"]].update(task_status="failed", penalized_position_error_m=0)
    failed = analyze(rows, equal, config, device)
    checks["all_failures_penalized"] = failed["status"] == "failed" and abs(failed["mean_penalized_position_error_m"][-1]-.1) < 1e-10
    missing = dict(outcomes); missing.pop(next(r["id"] for r in rows if r["stage"] == "E3" and r["variant"] == "core"))
    checks["missing_trial_not_dropped"] = analyze(rows, missing, config, device)["status"] == "awaiting_verification"
    duplicate = rows+[next(r for r in rows if r["stage"] == "E3" and r["variant"] == "core")]
    try:
        analyze(duplicate, outcomes, config, device); checks["duplicate_rejected"] = False
    except ValueError:
        checks["duplicate_rejected"] = True
    mixed = copy.deepcopy(rows); mixed[0]["gpu_uuid"] = "other-fixture-gpu"
    try:
        analyze(mixed, outcomes, config, device); checks["mixed_hardware_rejected"] = False
    except ValueError:
        checks["mixed_hardware_rejected"] = True
    e2 = copy.deepcopy(outcomes)
    for row in rows:
        if row["stage"] == "E2": e2[row["id"]]["penalized_position_error_m"] = .002 if row["group"] == "G1F1" else .004
    checks["reduced_E2_supported"] = analyze(rows, e2, config, device, "E2")["status"] == "passed"
    args.output.mkdir(parents=True, exist_ok=False)
    write(args.output/"result.json", {"status": "passed" if all(checks.values()) else "failed", "checks": checks,
          "gpu": gpu, "scope": "Synthetic tables only; no physical experiments", "positive_fixture": result,
          "source_sha256": digest(ROOT/"scripts/analyze-r4-campaign-gpu.py")})
    if not all(checks.values()): raise SystemExit(1)


if __name__ == "__main__":
    main()
