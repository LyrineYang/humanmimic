#!/usr/bin/env python3
"""CUDA statistical-fixture checks; these invented tables are NOT experiment data."""
import argparse
import copy
import importlib.util
from pathlib import Path
from r4_contract import sha256, write_json
from r4_cuda import require_cuda


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    device, gpu = require_cuda()
    source = Path(__file__).with_name("analyze-r4-control-study-gpu.py")
    spec = importlib.util.spec_from_file_location("r4_analysis", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cases = []
    for family, numbers in [("stepped_prism", range(101, 104)), ("grooved_block", range(104, 107)),
                            ("necked_column", range(107, 110)), ("u_handle", range(110, 113))]:
        for number in numbers:
            for task in ["lift_hold", "precision_place"]:
                for seed in [1101, 1102, 1103]:
                    case_index = len(cases)//4
                    for group in ["G0F0", "G1F0", "G0F1", "G1F1"]:
                        cases.append(dict(case_index=case_index, object_id=f"{family}-{number}", task=task, seed=seed, group=group, probe="no_probe"))
    plan = {"study": "E2", "cases": cases}
    outcomes = [dict(row, execution_status="completed", task_status="passed",
                     penalized_position_error_m=.002 if row["group"] == "G1F1" else .004) for row in cases]
    progress = {"status": "complete", "outcomes": outcomes}
    positive = module.analyze(plan, progress, device)
    checks = {"known_positive_detected": positive["status"] == "passed" and abs(positive["G1F1_vs_G0F1_relative_error_reduction"]-.5) < 1e-10}
    negative_progress = copy.deepcopy(progress)
    for row in negative_progress["outcomes"]:
        row["penalized_position_error_m"] = .004
    negative = module.analyze(plan, negative_progress, device)
    checks["equal_groups_do_not_pass"] = negative["status"] == "failed"
    failed_progress = copy.deepcopy(progress)
    for row in failed_progress["outcomes"]:
        if row["group"] == "G1F1":
            row.update(task_status="failed", penalized_position_error_m=0.)
    failed = module.analyze(plan, failed_progress, device)
    checks["failed_trials_cost_100mm"] = failed["status"] == "failed" and abs(failed["mean_penalized_position_error_m"][3]-.1) < 1e-10
    duplicate = copy.deepcopy(progress)
    duplicate["outcomes"][-1] = copy.deepcopy(duplicate["outcomes"][0])
    try:
        module.analyze(plan, duplicate, device)
        checks["replacement_or_duplicate_rejected"] = False
    except ValueError:
        checks["replacement_or_duplicate_rejected"] = True
    partial_plan = {"study": "E2", "cases": cases[:24]}
    partial_progress = {"status": "complete", "outcomes": outcomes[:24]}
    partial = module.analyze(partial_plan, partial_progress, device)
    checks["partial_matrix_cannot_certify_hypothesis"] = partial["status"] == "awaiting_verification"
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output/"result.json", {"status": "passed" if all(checks.values()) else "failed", "checks": checks,
        "scope": "Invented statistical fixture tables only; no manipulation experiments or real success rates", "gpu": gpu,
        "source_sha256": sha256(source), "fixture_source_sha256": sha256(Path(__file__)),
        "positive_fixture": positive, "equal_fixture": negative, "failed_fixture": failed})
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
