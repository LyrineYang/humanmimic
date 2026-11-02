#!/usr/bin/env python3
"""CUDA object-level paired bootstrap for E2; failures stay in the denominator."""
import argparse
import json
from pathlib import Path
import torch
from r4_contract import sha256, write_json
from r4_cuda import require_cuda


def validate_pairing(plan, progress):
    fields = ["case_index", "object_id", "seed", "task", "group", "probe"]
    identity = lambda row: tuple(row[name] for name in fields)
    expected = [identity(row) for row in plan["cases"]]
    actual = [identity(row) for row in progress["outcomes"]]
    if len(set(expected)) != len(expected) or len(set(actual)) != len(actual) or set(expected) != set(actual):
        raise ValueError("Outcomes must match every frozen case exactly once")


def analyze(plan, progress, device):
    if plan["study"] != "E2" or progress["status"] != "complete" or len(progress["outcomes"]) != len(plan["cases"]):
        raise ValueError("Only complete E2 plans may be analyzed; incomplete/failed trials cannot be silently excluded")
    validate_pairing(plan, progress)
    groups = ["G0F0", "G1F0", "G0F1", "G1F1"]
    objects = sorted({row["object_id"] for row in plan["cases"]})
    errors, success = [], []
    for obj in objects:
        row_errors, row_success, pairs = [], [], []
        for group in groups:
            rows = [r for r in progress["outcomes"] if r["object_id"] == obj and r["group"] == group]
            pairs.append({(r["task"], r["seed"]) for r in rows})
            if not rows:
                raise ValueError("Missing matched group")
            # Fixed 100mm cost for every failure, including malformed low scores.
            values = [r["penalized_position_error_m"] if r["task_status"] == "passed" and r.get("execution_status") == "completed" else .1 for r in rows]
            tensor = torch.tensor(values, device=device, dtype=torch.float64)
            if not bool(torch.isfinite(tensor).all()) or bool((tensor < 0).any()):
                raise ValueError("Invalid reported task error")
            row_errors.append(tensor.mean())
            row_success.append(torch.tensor([r["task_status"] == "passed" and r.get("execution_status") == "completed" for r in rows], device=device, dtype=torch.float64).mean())
        if any(value != pairs[0] for value in pairs):
            raise ValueError("Groups do not contain the same task/seed pairs")
        errors.append(torch.stack(row_errors))
        success.append(torch.stack(row_success))
    errors, success = torch.stack(errors), torch.stack(success)
    generator = torch.Generator(device=device).manual_seed(41101)
    index = torch.randint(len(objects), (10000, len(objects)), device=device, generator=generator)
    gains = errors[:, 2]-errors[:, 3]
    success_delta = success[:, 3]-success[:, 2]
    quantiles = torch.tensor([.025, .975], device=device, dtype=torch.float64)
    gain_interval = torch.quantile(gains[index].mean(-1), quantiles)
    success_interval = torch.quantile(success_delta[index].mean(-1), quantiles)
    baseline = float(errors[:, 2].mean())
    reduction = float(gains.mean())/baseline if baseline > 0 else None
    allowed = {f"{family}-{n}" for family, numbers in [("stepped_prism", range(101, 104)), ("grooved_block", range(104, 107)), ("necked_column", range(107, 110)), ("u_handle", range(110, 113))] for n in numbers}
    complete_matrix = set(objects) == allowed and len(plan["cases"]) == 288 and all(
        {(r["task"], r["seed"]) for r in plan["cases"] if r["object_id"] == obj and r["group"] == group}
        == {(task, seed) for task in ["lift_hold", "precision_place"] for seed in [1101, 1102, 1103]}
        for obj in objects for group in groups)
    supported = complete_matrix and reduction is not None and reduction >= .2 and float(gain_interval[0]) > 0 and float(success_interval[0]) >= -.05
    contrasts = {}
    for before, after in [(0, 1), (0, 2), (1, 3), (2, 3)]:
        delta = errors[:, before]-errors[:, after]
        contrasts[groups[after]+"_vs_"+groups[before]] = {"mean_gain_m": float(delta.mean()),
            "paired_gain_95ci_m": torch.quantile(delta[index].mean(-1), quantiles).tolist()}
    return {"status": "passed" if supported else ("failed" if complete_matrix else "awaiting_verification"),
        "unit": "object; paired tasks/seeds averaged within object", "objects": objects, "trials": len(plan["cases"]),
        "group_order": groups, "mean_penalized_position_error_m": errors.mean(0).tolist(), "success_rate": success.mean(0).tolist(),
        "G1F1_vs_G0F1_relative_error_reduction": reduction, "paired_gain_95ci_m": gain_interval.tolist(),
        "success_delta_95ci": success_interval.tolist(), "development_hypothesis_supported": supported,
        "secondary_contrasts_descriptive": contrasts, "complete_development_matrix": complete_matrix,
        "heldout_used": False, "formal_confirmation": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    device, gpu = require_cuda()
    plan = json.loads((args.study/"plan.json").read_text())
    progress = json.loads((args.study/"progress.json").read_text())
    result = analyze(plan, progress, device)
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output/"analysis.json", {**result, "gpu": gpu,
        "plan_sha256": sha256(args.study/"plan.json"), "outcomes_sha256": sha256(args.study/"progress.json")})


if __name__ == "__main__":
    main()
