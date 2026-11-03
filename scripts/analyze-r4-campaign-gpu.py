#!/usr/bin/env python3
"""CUDA object-paired analysis of the reduced E2 and primary E3 campaign.

One predeclared E3 contrast: task_risk_reduction versus global_uncertainty.
Secondary/ablation intervals are descriptive, not multiplicity-adjusted claims.
"""
import argparse
import copy
from pathlib import Path
import torch
from r4_campaign import ROOT, digest, read, write
from r4_cuda import require_cuda


def analyze(rows, outcomes, config, device, study="E3"):
    if device.type != "cuda":
        raise ValueError("No CPU numerical fallback")
    selected = [r for r in rows if r["stage"] == study and r["variant"] == "core"]
    expected_ids = [r["id"] for r in selected]
    if len(set(expected_ids)) != len(expected_ids):
        raise ValueError("Duplicate planned trials")
    if any(key not in outcomes for key in expected_ids):
        return {"status": "awaiting_verification", "reason": "Incomplete matrix; missing trials cannot be discarded",
                "planned": len(selected), "finished": sum(key in outcomes for key in expected_ids)}
    group_field = "probe" if study == "E3" else "group"
    groups = config["E3"]["strategies"] if study == "E3" else config["E2"]["groups"]
    objects = config["objects"]
    expected_pairs = {(s, t) for s in config["seeds"] for t in config["tasks"]}
    expected = {(o, s, t, g) for o in objects for s, t in expected_pairs for g in groups}
    actual = [(r["object_id"], r["seed"], r["task"], r[group_field]) for r in selected]
    if set(actual) != expected or len(actual) != len(expected):
        raise ValueError("Require the complete predeclared development matrix exactly once")
    for obj in objects:
        for seed, task in expected_pairs:
            uuids = {r["gpu_uuid"] for r in selected if (r["object_id"], r["seed"], r["task"]) == (obj, seed, task)}
            if len(uuids) != 1:
                raise ValueError("Paired variants changed GPU hardware")
    errors, successes = [], []
    for obj in objects:
        oe, os = [], []
        for group in groups:
            values = [outcomes[r["id"]] for r in selected if r["object_id"] == obj and r[group_field] == group]
            success = [v.get("task_status") == "passed" and v.get("execution_status") == "completed" for v in values]
            error = [v["penalized_position_error_m"] if ok else .1 for v, ok in zip(values, success)]
            tensor = torch.tensor(error, dtype=torch.float64, device=device)
            if not bool(torch.isfinite(tensor).all()) or bool((tensor < 0).any()):
                raise ValueError("Nonfinite/negative error in successful trial")
            oe.append(tensor.mean())
            os.append(torch.tensor(success, dtype=torch.float64, device=device).mean())
        errors.append(torch.stack(oe)); successes.append(torch.stack(os))
    errors, successes = torch.stack(errors), torch.stack(successes)
    generator = torch.Generator(device=device).manual_seed(41101)
    indices = torch.randint(len(objects), (10000, len(objects)), generator=generator, device=device)
    q = torch.tensor([.025, .975], dtype=torch.float64, device=device)
    before, after = config["E3"]["primary_contrast"] if study == "E3" else ("G0F1", "G1F1")

    def contrast(baseline, method):
        b, a = groups.index(baseline), groups.index(method)
        gain = errors[:, b]-errors[:, a]
        success_delta = successes[:, a]-successes[:, b]
        base = float(errors[:, b].mean())
        return {"baseline": baseline, "method": method,
                "relative_error_reduction": float(gain.mean())/base if base > 0 else None,
                "mean_gain_m": float(gain.mean()),
                "paired_gain_95ci_m": torch.quantile(gain[indices].mean(-1), q).tolist(),
                "success_delta_95ci": torch.quantile(success_delta[indices].mean(-1), q).tolist()}
    primary = contrast(before, after)
    supported = (primary["relative_error_reduction"] is not None and primary["relative_error_reduction"] >= .2
                 and primary["paired_gain_95ci_m"][0] > 0 and primary["success_delta_95ci"][0] >= -.05)
    return {"status": "passed" if supported else "failed", "study": study, "primary": primary,
            "unit": "objects; average paired seeds/tasks within each object", "tasks": config["tasks"],
            "groups": groups, "trials": len(selected), "mean_penalized_position_error_m": errors.mean(0).tolist(),
            "success_rate": successes.mean(0).tolist(), "development_hypothesis_supported": supported,
            "secondary_descriptive": [contrast(g, after) for g in groups if g not in [before, after]],
            "heldout_used": False, "formal_confirmation": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--ledger", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    plan, ledger = read(args.plan), read(args.ledger)
    plan_sha = digest(args.plan)
    config_path = ROOT/"configs/r4-e3-campaign.json"
    if digest(config_path) != plan["frozen_sha256"][str(config_path)]:
        raise ValueError("Analysis protocol changed after freeze")
    outcomes = {}
    for row in plan["jobs"]:
        job = ledger["jobs"].get(plan_sha+":"+row["id"])
        if job and job["status"] == "finished":
            if job["gpu_uuid"] != row["gpu_uuid"]:
                raise ValueError("Ledger hardware differs from paired plan")
            outcomes[row["id"]] = job["outcome"]
    device, gpu = require_cuda()
    results = {s: analyze(plan["jobs"], outcomes, read(config_path), device, s) for s in ["E3", "E2"]}
    task_results, ablations = {}, {}
    for task in read(config_path)["tasks"]:
        config = read(config_path); config["tasks"] = [task]
        task_results[task] = analyze([r for r in plan["jobs"] if r.get("task") == task], outcomes, config, device)
    for ablation in ["recent_memory", "geometry_feedback_off"]:
        config = read(config_path)
        config["E3"]["strategies"] = [ablation, "task_risk_reduction"]
        config["E3"]["primary_contrast"] = [ablation, "task_risk_reduction"]
        rows = []
        for source in plan["jobs"]:
            if source["stage"] != "E3" or source.get("probe") != "task_risk_reduction" or source["variant"] not in ["core", ablation]:
                continue
            row = copy.deepcopy(source)
            row.update(variant="core", probe=ablation if source["variant"] == ablation else "task_risk_reduction")
            rows.append(row)
        result = analyze(rows, outcomes, config, device)
        if "development_hypothesis_supported" in result:
            result["unadjusted_thresholds_met"] = result.pop("development_hypothesis_supported")
            result["status"] = "descriptive"
        ablations[ablation] = result
    args.output.mkdir(parents=True, exist_ok=False)
    write(args.output/"analysis.json", {"results": results, "gpu": gpu, "plan_sha256": plan_sha,
          "ledger_sha256": digest(args.ledger), "analysis_source_sha256": digest(__file__),
          "E3_by_task": task_results, "ablations_descriptive": ablations,
          "training": False, "heldout_used": False})


if __name__ == "__main__":
    main()
