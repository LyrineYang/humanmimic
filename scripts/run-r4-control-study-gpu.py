#!/usr/bin/env python3
"""Prepare/run E2 or E3 paired physical trials; never reuse another group's video.

Inputs: split=debug, cases=[object_id, seed, task, reference, evaluation_scene,
prior, mission, sensor_config]. All paths absolute. E2 has four G/F groups;
E3 has five probe strategies with identical G1F1 control. Default writes a plan.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from r4_contract import sha256, write_json
from r4_public import keys, validate_prior


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--study", choices=["E2", "E3"], required=True)
    parser.add_argument("--policy-config", type=Path, default=Path(__file__).resolve().parents[1]/"configs/r4-control.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    suite = json.loads(args.cases.read_text())
    if suite.get("split") != "debug" or not 1 <= len(suite["cases"]) <= 72:
        raise ValueError("Only bounded development cases; no heldout execution")
    variants = ([(group, "no_probe") for group in ["G0F0", "G1F0", "G0F1", "G1F1"]] if args.study == "E2" else
                [("G1F1", strategy) for strategy in ["no_probe", "random", "uniform", "global_uncertainty", "task_risk_reduction"]])
    inputs, rows, seen = [], [], set()
    allowed = {f"{family}-{number}" for family, numbers in [("stepped_prism", range(101, 104)), ("grooved_block", range(104, 107)), ("necked_column", range(107, 110)), ("u_handle", range(110, 113))] for number in numbers}
    for i, case in enumerate(suite["cases"]):
        keys(case, {"object_id", "seed", "task", "reference", "evaluation_scene", "prior", "mission", "sensor_config"})
        identity = (case["object_id"], case["seed"], case["task"])
        if identity in seen or case["object_id"] not in allowed or case["seed"] not in [1101, 1102, 1103] or case["task"] not in {"lift_hold", "precision_place"}:
            raise ValueError("Invalid/duplicate development identity")
        seen.add(identity)
        hashes = {}
        for name in ["reference", "evaluation_scene", "prior", "mission", "sensor_config"]:
            path = Path(case[name])
            if not path.is_absolute():
                raise ValueError("Inputs must use absolute paths")
            hashes[name] = sha256(path)
        scene = json.loads(Path(case["evaluation_scene"]).read_text())
        sensor = json.loads(Path(case["sensor_config"]).read_text())
        mission = json.loads(Path(case["mission"]).read_text())
        if scene["split"] != "debug" or scene["object_id"] != identity[0] or scene["task"] != identity[2] or sensor["sensor"]["seed"] != identity[1]:
            raise ValueError("Object/seed/task inputs do not match declared pairing")
        if mission["role"] != "public_task_goal" or mission["object_id"] != identity[0] or mission["task"] != identity[2]:
            raise ValueError("Public task goal mismatch")
        validate_prior(json.loads(Path(case["prior"]).read_text()))
        inputs.append(hashes)
        for group, strategy in variants:
            rows.append({"case_index": i, "object_id": identity[0], "seed": identity[1], "task": identity[2], "group": group, "probe": strategy})
    args.output.mkdir(parents=True, exist_ok=False)
    plan = {"status": "awaiting_verification", "study": args.study, "cases": rows, "inputs_sha256": inputs,
            "policy_sha256": sha256(args.policy_config), "physics_sha256": sha256(Path(__file__).resolve().parents[1]/"configs/r4-stage1.json"),
            "sources_sha256": {p.name: sha256(p) for p in Path(__file__).parent.glob("*r4*.py")},
            "maximum_trial_wall_s": 420, "maximum_suite_wall_s": len(rows)*420, "heldout_used": False, "paid_usd": 0}
    write_json(args.output/"plan.json", plan)
    if not args.execute:
        return
    from r4_cuda import require_cuda
    _, gpu = require_cuda()
    outcomes = []
    for index, row in enumerate(rows):
        case = suite["cases"][row["case_index"]]
        if any(sha256(Path(case[name])) != value for name, value in inputs[row["case_index"]].items()) or sha256(args.policy_config) != plan["policy_sha256"]:
            raise RuntimeError("Frozen inputs changed; do not continue mixed-version comparisons")
        if (sha256(Path(__file__).resolve().parents[1]/"configs/r4-stage1.json") != plan["physics_sha256"] or
                any(sha256(Path(__file__).parent/name) != digest for name, digest in plan["sources_sha256"].items())):
            raise RuntimeError("Frozen source/physics changed; stop mixed-version comparison")
        destination = args.output/f"trial-{index:04d}"
        command = [sys.executable, str(Path(__file__).with_name("run-r4-physical.py")), "--reference", case["reference"],
            "--evaluation-scene", case["evaluation_scene"], "--sensor-config", case["sensor_config"], "--sensors", "--render",
            "--policy-config", str(args.policy_config), "--prior", case["prior"], "--mission", case["mission"],
            "--controller-group", row["group"], "--probe-strategy", row["probe"], "--output", str(destination)]
        outcome = {**row, "path": str(destination), "task_status": "failed", "penalized_position_error_m": .1}
        try:
            with (args.output/f"trial-{index:04d}.log").open("w") as log:
                process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    code = process.wait(timeout=420)
                except subprocess.TimeoutExpired:
                    # Terminate this trial's process group, including its own worker.
                    import signal
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                    raise
                if code:
                    raise RuntimeError(f"Physical runner exited {code}")
            actual = json.loads((destination/"private-evaluation/result.json").read_text())
            outcome.update(execution_status="completed", task_status=actual["task_status"], metrics=actual["metrics"],
                           penalized_position_error_m=actual["metrics"]["penalized_position_error_m"],
                           policy_summary=actual.get("policy_summary"))
        except Exception as exc:
            outcome.update(execution_status="failed", error=str(exc))
        outcomes.append(outcome)
        write_json(args.output/"progress.json", {"status": "running", "gpu": gpu, "outcomes": outcomes, "all_trials_denominator": len(outcomes)})
    write_json(args.output/"progress.json", {"status": "complete", "gpu": gpu, "outcomes": outcomes,
        "all_trials_denominator": len(outcomes), "research_acceptance": "awaiting_verification; requires paired object-level analysis"})


if __name__ == "__main__":
    main()
