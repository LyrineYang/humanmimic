#!/usr/bin/env python3
"""Prepare/dispatch the E3-first local development campaign. No training.

matrix and preflight are read-only preparation; prepare freezes real manifests;
run alone launches bounded CUDA jobs. The persistent ledger is shared by every
plan under $R4_DATA_ROOT/runs/r4-e3-development-20261102, not by output directory.
"""
import argparse
import json
import os
from pathlib import Path
import random
import shutil
import signal
import subprocess
import sys
import time

from r4_campaign import (ROOT, Ledger, assert_frozen, digest, exclusive, idle_device,
                         inventory, output_bytes, read, stop_group, validate_limits, write)


def configuration():
    limits = read(ROOT/"configs/budget.json")["local_r4_campaign"]
    config = read(ROOT/"configs/r4-e3-campaign.json")
    validate_limits(limits)
    if limits["campaign_id"] != config["campaign_id"]:
        raise ValueError("Campaign/budget identity mismatch")
    return config, limits


def runtime_check():
    from importlib.metadata import version
    expected = read(ROOT/"configs/r4-runtime.json")
    if sys.version.split()[0] != expected["python"]:
        raise ValueError("Activate the declared R4 Python environment before freezing/running jobs")
    for package in ["torch", "mujoco"]:
        if version(package) != expected[package]:
            raise ValueError("R4 environment version mismatch: " + package)


def matrix(config):
    rows = []
    rng = random.Random(41101)
    case_index = 0
    for obj in config["objects"]:
        for seed in config["seeds"]:
            for task in config["tasks"]:
                base = {"case_index": case_index, "object_id": obj, "seed": seed, "task": task,
                        "slot": case_index % 4, "stage": "E3", "timeout_s": config["E3"]["trial_timeout_s"]}
                variants = [{"variant": "core", "group": "G1F1", "memory": "diverse", "probe": p}
                            for p in config["E3"]["strategies"]]
                variants += [{"variant": a["name"], **{k: a[k] for k in ["group", "memory", "probe"]}}
                             for a in config["E3"]["ablations"]]
                rng.shuffle(variants)
                for variant in variants:
                    rows.append({**base, **variant, "priority": "E3_core" if variant["variant"] == "core" else "E3_ablation"})
                for group in config["E2"]["groups"]:
                    rows.append({**base, "stage": "E2", "variant": "core", "priority": "E2",
                                 "group": group, "memory": "diverse", "probe": "no_probe"})
                case_index += 1
        for seed in config["E1"]["seeds"]:
            slot = config["objects"].index(obj) % 4
            for occlusion in config["E1"]["occlusions"]:
                for modality in config["E1"]["modalities"]:
                    rows.append({"object_id": obj, "seed": seed, "stage": "E1", "variant": "core", "priority": "E1",
                        "slot": slot, "occlusion": occlusion, "modality": modality, "timeout_s": config["E1"]["trial_timeout_s"]})
    rows.sort(key=lambda r: config["priority"].index(r["priority"]))
    for i, row in enumerate(rows):
        row["id"] = "trial-{:04d}".format(i)
    return rows


def gate_files(gates_path, cases):
    """Evidence gates, not editable boolean overrides. Analytic P2 is insufficient."""
    gates = read(gates_path)
    files = [Path(gates_path)]
    covered = set()
    for item in gates["successful_baselines"]:
        directory = Path(item).resolve()
        manifest = read(directory/"manifest.json")
        result = read(directory/"private-evaluation/result.json")
        if manifest.get("status") != "complete" or manifest.get("split") != "debug" or result.get("task_status") != "passed" or result.get("execution_status") != "passed":
            raise ValueError("Successful development physical baseline required")
        match = [c for c in cases if c["object_id"] == manifest["object_id"] and c["seed"] == manifest["sensor_seed"]
                 and digest(c["reference"]) == manifest["reference_sha256"]
                 and digest(c["evaluation_scene"]) == manifest["evaluation_scene_sha256"]
                 and digest(c["sensor_config"]) == manifest["sensor_config_sha256"]]
        if len(match) != 1 or manifest["config_sha256"] != digest(ROOT/"configs/r4-stage1.json"):
            raise ValueError("Baseline does not match frozen reference/physics/sensors")
        for name, sha in manifest["source_sha256"].items():
            if digest(ROOT/"scripts"/name) != sha:
                raise ValueError("Baseline code changed; rerun affected physical check")
        for name, sha in result["artifacts_sha256"].items():
            artifact = directory/"private-evaluation"/name
            if digest(artifact) != sha:
                raise ValueError("Baseline evidence changed")
            files.append(artifact)
        if not result["video"]["frames"] or result["policy_abort"]:
            raise ValueError("Baseline requires complete actual execution video and no policy abort")
        covered.add((match[0]["object_id"].rsplit("-", 1)[0], match[0]["task"]))
        files += [directory/"manifest.json", directory/"private-evaluation/result.json"]
    expected = {(c["object_id"].rsplit("-", 1)[0], c["task"]) for c in cases}
    if covered != expected:
        raise ValueError("Need successful fixed references for all four families and both tasks")
    report_path = Path(gates["leap_calibration_report"])
    report = read(report_path)
    if (report.get("status") != "passed" or report.get("scope") != "LEAP full-hand force bound and pose/compliance coverage"
            or report.get("split") != "debug" or not report.get("gpu") or report.get("heldout_used") is not False
            or not all(report.get("checks", {}).get(k) is True for k in
                       ["full_hand_load", "conservative_force_bound", "pose_compliance_coverage"])):
        raise ValueError("Full LEAP calibration required; distal/analytic fixtures do not qualify")
    fraction = report.get("coverage_fraction", 0)
    if (report.get("coverage_trials", 0) < 20 or isinstance(fraction, bool)
            or not isinstance(fraction, (int, float)) or not .8 <= fraction <= 1):
        raise ValueError("LEAP coverage gate requires >=20 development trials and >=0.8 joint coverage")
    if report.get("policy_sha256") != digest(ROOT/"configs/r4-control.json"):
        raise ValueError("Force-bound calibration does not bind current policy")
    if not report.get("artifacts_sha256") or not report.get("sources_sha256"):
        raise ValueError("Calibration must bind raw trial artifacts and producer sources")
    for path, sha in {**report["artifacts_sha256"], **report["sources_sha256"]}.items():
        if not Path(path).is_absolute() or digest(path) != sha:
            raise ValueError("Calibration evidence/source hash mismatch")
        files.append(Path(path))
    files.append(report_path)
    if read(ROOT/"configs/r4-control.json")["probe"]["compliance_bound_status"] != "calibrated_development_bound":
        raise ValueError("Probe bound remains uncalibrated; do not merely change the status string")
    return files


def source_files():
    root = Path(os.environ.get("R4_DATA_ROOT", str(ROOT.parent/"humanmimic-data/r4")))
    # Asset and environment mutations also invalidate a frozen comparison.
    assets = [p for p in (root/"assets/leap_hand").rglob("*") if p.is_file()]
    environment = list((Path(sys.prefix)/"conda-meta").glob("*.json"))
    environment += list((Path(sys.prefix)/"lib/python3.10/site-packages").glob("*.dist-info/RECORD"))
    return (list((ROOT/"scripts").glob("*r4*.py")) + list((ROOT/"configs").glob("r4*.json"))
            + [ROOT/"configs/budget.json"] + assets + environment)


def prepare(args, config, limits):
    runtime_check()
    if len(args.gpus) != 4 or len(set(args.gpus)) != 4:
        raise ValueError("Freeze four distinct GPU UUIDs; no implicit index remapping")
    devices = inventory()
    if any(g not in devices for g in args.gpus):
        raise ValueError("Unknown GPU UUID")
    case_doc, record_doc = read(args.cases), read(args.records)
    cases = case_doc["cases"]
    expected = {(o, s, t) for o in config["objects"] for s in config["seeds"] for t in config["tasks"]}
    if (case_doc.get("split") != "debug" or len(cases) != 72 or
            {(c["object_id"], c["seed"], c["task"]) for c in cases} != expected):
        raise ValueError("Require all 72 development object/seed/task inputs, no substitutes")
    records = record_doc["records"]
    if (record_doc.get("split") != "debug" or len(records) != 12 or
            {(r["object_id"], r["seed"]) for r in records} != {(o, 1101) for o in config["objects"]}):
        raise ValueError("E1 requires twelve frozen seed-1101 development recordings")
    evidence = gate_files(args.gates, cases)
    args.output.mkdir(parents=True, exist_ok=False)
    # Reuse the established source/identity/public-private validators, plan-only.
    for command in [
        ["run-r4-control-study-gpu.py", "--cases", str(args.cases), "--study", "E3", "--output", str(args.output/"control-validation")],
        ["run-r4-e1-gpu.py", "--records", str(args.records), "--occlusions", "0", ".8", "--output", str(args.output/"e1-validation")]]:
        subprocess.run([sys.executable, str(ROOT/"scripts"/command[0]), *command[1:]], check=True)
    frozen = source_files()+[args.cases, args.records]+evidence
    for case in cases:
        frozen += [Path(case[k]) for k in ["reference", "evaluation_scene", "sensor_config", "mission", "prior"]]
    for record in records:
        frozen += [Path(record[k]) for k in ["prior", "evaluation_scene", "actual_state", "collection_manifest"]]
        frozen += [Path(record["observations"])/n for n in ["observations.jsonl", "calibration.json"]]
    rows = matrix(config)
    policy = read(ROOT/"configs/r4-control.json")
    policy_paths = {}
    for memory in ["diverse", "recent"]:
        policy["memory"]["mode"] = memory
        path = args.output/("policy-"+memory+".json")
        write(path, policy)
        policy_paths[memory] = path
        frozen.append(path)
    cases_by_id = {(c["object_id"], c["seed"], c["task"]): c for c in cases}
    record_paths = {}
    for record in records:
        path = args.output/(record["object_id"]+"-record.json")
        write(path, {"split": "debug", "records": [record]})
        record_paths[record["object_id"]] = path
        frozen.append(path)
    for row in rows:
        dest = args.output/"trials"/row["id"]
        if row["stage"] == "E1":
            argv = ["run-r4-e1-gpu.py", "--records", str(record_paths[row["object_id"]]), "--occlusions", str(row["occlusion"]),
                    "--modalities", row["modality"], "--execute", "--output", str(dest)]
        else:
            case = cases_by_id[(row["object_id"], row["seed"], row["task"])]
            argv = ["run-r4-physical.py", "--reference", case["reference"], "--evaluation-scene", case["evaluation_scene"],
                    "--sensor-config", case["sensor_config"], "--sensors", "--render", "--prior", case["prior"], "--mission", case["mission"],
                    "--policy-config", str(policy_paths[row["memory"]]), "--controller-group", row["group"],
                    "--probe-strategy", row["probe"], "--output", str(dest)]
        row.update(argv=argv, output=str(dest), gpu_uuid=args.gpus[row["slot"]])
    data_root = Path(os.environ.get("R4_DATA_ROOT", str(ROOT.parent/"humanmimic-data/r4"))).resolve()
    rows.append({"id": "analysis", "kind": "analysis", "stage": "E3", "variant": "analysis", "timeout_s": 120,
                 "gpu_uuid": args.gpus[0], "output": str(args.output/"analysis"),
                 "argv": ["analyze-r4-campaign-gpu.py", "--plan", str(args.output/"plan.json"),
                          "--ledger", str(data_root/"runs"/config["campaign_id"]/"ledger.json"), "--output", str(args.output/"analysis")]})
    write(args.output/"plan.json", {"campaign_id": config["campaign_id"], "kind": "development_matrix", "jobs": rows,
          "gpus": {g: devices[g] for g in args.gpus}, "frozen_sha256": {str(p.resolve()): digest(p) for p in frozen},
          "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
          "python": sys.executable, "environment_prefix": sys.prefix, "data_root": str(data_root),
          "heldout_used": False, "training": False})


def prepare_prerequisites(args, config):
    """Only existing implementation checks; these cannot satisfy scientific gates."""
    runtime_check()
    gpu = inventory()[args.gpu]
    args.output.mkdir(parents=True, exist_ok=False)
    entries = [("check-r4-p1-gpu.py", [], 600), ("check-r4-p2-gpu.py", ["--coverage"], 12000),
               ("check-r4-memory-control-gpu.py", ["--belief", str(args.output/"check-1/joint/belief.json")], 1200),
               ("check-r4-campaign-analysis-gpu.py", [], 120)]
    jobs = []
    for i, (script, flags, timeout) in enumerate(entries):
        destination = args.output/("check-"+str(i))
        jobs.append({"id": "prerequisite-"+str(i), "stage": "prerequisites", "gpu_uuid": args.gpu,
                     "timeout_s": timeout, "argv": [script, *flags, "--output", str(destination)], "output": str(destination)})
    write(args.output/"plan.json", {"campaign_id": config["campaign_id"], "kind": "implementation_checks", "jobs": jobs,
        "gpus": {args.gpu: gpu}, "frozen_sha256": {str(p): digest(p) for p in source_files()},
        "python": sys.executable, "environment_prefix": sys.prefix,
        "data_root": str(Path(os.environ.get("R4_DATA_ROOT", str(ROOT.parent/"humanmimic-data/r4"))).resolve()),
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
        "heldout_used": False, "training": False})


def trial_outcome(row, code, timed_out):
    outcome = {"execution_status": "failed", "exit_code": code, "timed_out": timed_out,
               "task_status": "failed", "penalized_position_error_m": .1}
    if code != 0 or timed_out:
        return outcome
    try:
        if row.get("kind") == "analysis":
            read(Path(row["output"])/"analysis.json")
            outcome["execution_status"] = "completed"
        elif row["stage"] in {"E2", "E3"}:
            result = read(Path(row["output"])/"private-evaluation/result.json")
            if result["execution_status"] != "passed":
                raise ValueError("Incomplete physical execution")
            outcome.update(execution_status="completed", task_status=result["task_status"], metrics=result["metrics"],
                           penalized_position_error_m=result["metrics"]["penalized_position_error_m"], policy_summary=result.get("policy_summary"))
        elif row["stage"] == "E1":
            progress = read(Path(row["output"])/"progress.json")
            if progress["status"] != "complete" or any(r["execution_status"] != "completed" for r in progress["outcomes"]):
                raise ValueError("Incomplete E1 replay")
            outcome["execution_status"] = "completed"
        else:
            result = read(Path(row["output"])/"result.json")
            outcome["execution_status"] = "completed" if result["status"] == "passed" else "failed"
    except (OSError, ValueError, KeyError) as exc:
        outcome["error"] = str(exc)
    return outcome


def run(args, config, limits):
    plan = read(args.plan)
    if plan["campaign_id"] != config["campaign_id"] or plan["python"] != sys.executable or plan["environment_prefix"] != sys.prefix:
        raise ValueError("Campaign/environment changed; activate the frozen R4 environment")
    timeout_binary = shutil.which("timeout")
    if not timeout_binary:
        raise RuntimeError("GNU timeout is required for independent per-trial watchdogs")
    root = Path(os.environ.get("R4_DATA_ROOT", str(ROOT.parent/"humanmimic-data/r4"))).resolve()
    if str(root) != plan["data_root"]:
        raise ValueError("Data/ledger root changed; cannot reset accounting or substitute unfrozen assets")
    account = root/"runs"/config["campaign_id"]
    locks = [exclusive(account/"coordinator.lock")]
    active = {}
    try:
        ledger = Ledger(account/"ledger.json", limits)
        if any(j["status"] == "running" for j in ledger.state["jobs"].values()):
            raise RuntimeError("Unreconciled previous jobs: inspect PIDs/logs and charge before resuming; never reset ledger")
        devices = inventory()
        for uuid, expected in plan["gpus"].items():
            gpu = idle_device(devices, uuid)
            if gpu["index"] != expected["index"] or gpu["driver"] != expected["driver"]:
                raise RuntimeError("GPU/EGL mapping or driver changed after freeze")
            locks.append(exclusive(root/"runs"/(uuid+".lock")))
        plan_sha = digest(args.plan)
        frozen_cache = {}
        assert_frozen(plan, frozen_cache)
        pending = [j for j in plan["jobs"] if plan_sha+":"+j["id"] not in ledger.state["jobs"]]
        pause_reason = None
        log_root = args.plan.parent/"logs"
        log_root.mkdir(exist_ok=True)
        while pending or active:
            for key, item in list(active.items()):
                process, row, started, log = item
                timeout = time.monotonic()-started >= row["timeout_s"]-2
                if process.poll() is not None or timeout:
                    stop_group(process)
                    log.close()
                    ledger.finish(key, trial_outcome(row, process.returncode, timeout))
                    del active[key]
                    if row["stage"] == "prerequisites" and ledger.state["jobs"][key]["outcome"]["execution_status"] != "completed":
                        raise RuntimeError("Prerequisite failed; stop and diagnose")
            busy = {item[1]["gpu_uuid"] for item in active.values()}
            for row in list(pending):
                if pause_reason:
                    break
                if row["gpu_uuid"] in busy or len(active) >= limits["concurrent_gpus_max"]:
                    continue
                if row.get("kind") == "analysis" and (active or any(r.get("kind") != "analysis" for r in pending)):
                    continue
                used = output_bytes(args.plan.parent)
                threshold = limits["campaign_output_cap_gib"] if args.storage_review else limits["initial_output_review_gib"]
                if args.storage_review:
                    review = read(args.storage_review)
                    if review.get("plan_sha256") != plan_sha or review.get("status") != "passed" or review.get("measured_output_bytes", 0) < (limits["initial_output_review_gib"]-1)*1024**3:
                        raise ValueError("Storage review must bind this plan and measured first 5GiB output")
                # Require headroom for a trial; disk estimates are not throughput evidence.
                if used >= max(0, threshold-1)*1024**3 or shutil.disk_usage(root).free < (limits["minimum_free_disk_gib"]+1)*1024**3:
                    pause_reason = "Storage review/headroom gate; drain current jobs and resume the same ledger after review"
                    break
                if Path(row["output"]).exists():
                    raise RuntimeError("Output exists without completed ledger entry; inspect before resuming")
                assert_frozen(plan, frozen_cache)
                gpu = idle_device(inventory(), row["gpu_uuid"])
                key = plan_sha+":"+row["id"]
                ledger.reserve(key, row["stage"], row["gpu_uuid"], row["timeout_s"], plan_sha)
                env = dict(os.environ, CUDA_VISIBLE_DEVICES=row["gpu_uuid"], MUJOCO_EGL_DEVICE_ID=str(gpu["index"]),
                           MUJOCO_GL="egl", OMP_NUM_THREADS="8", MKL_NUM_THREADS="8", OPENBLAS_NUM_THREADS="8",
                           R4_CAMPAIGN_PROCESS_GROUP="1", PYTHONNOUSERSITE="1")
                log = (log_root/(row["id"]+".log")).open("x")
                started = time.monotonic()
                try:
                    # The independent watchdog also kills workers if the coordinator
                    # is killed. r4_replay keeps its workers in this private group.
                    process = subprocess.Popen([timeout_binary, "--signal=KILL", str(max(.1, row["timeout_s"]-2))+"s",
                        sys.executable, str(ROOT/"scripts"/row["argv"][0]), *row["argv"][1:]],
                        cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                except BaseException as exc:
                    log.close()
                    ledger.finish(key, {"execution_status": "failed", "error": str(exc)})
                    raise
                ledger.state["jobs"][key].update(pid=process.pid, boot_id=ledger.boot)
                ledger.save()
                active[key] = (process, row, started, log)
                busy.add(row["gpu_uuid"])
                pending.remove(row)
            if active:
                time.sleep(.2)
            elif pause_reason:
                write(args.plan.parent/"completion.json", {"status": "awaiting_verification", "reason": pause_reason,
                      "ledger": str(ledger.path), "plan_sha256": plan_sha, "pending_trials": len(pending)})
                return
        write(args.plan.parent/"completion.json", {"status": "complete", "ledger": str(ledger.path),
              "plan_sha256": plan_sha, "research_acceptance": "awaiting_verification", "training": False})
    finally:
        for key, (process, row, started, log) in active.items():
            stop_group(process)
            log.close()
            ledger.finish(key, {"execution_status": "failed", "task_status": "failed", "penalized_position_error_m": .1,
                                "reason": "coordinator interrupted or admission failed"})
        for lock in locks:
            lock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    m = sub.add_parser("matrix"); m.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("preflight"); p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("prepare")
    for field in ["cases", "records", "gates", "output"]:
        p.add_argument("--"+field, type=Path, required=True)
    p.add_argument("--gpus", nargs=4, required=True)
    p = sub.add_parser("prepare-prerequisites"); p.add_argument("--gpu", required=True); p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("run"); p.add_argument("--plan", type=Path, required=True); p.add_argument("--storage-review", type=Path)
    args = parser.parse_args()
    for field in ["output", "cases", "records", "gates", "plan", "storage_review"]:
        if getattr(args, field, None):
            setattr(args, field, getattr(args, field).resolve())
    config, limits = configuration()
    if args.command == "matrix":
        rows = matrix(config)
        write(args.output, {"status": "awaiting_verification", "jobs": rows, "launchable": False,
            "stage_trial_hours": {s: sum(r["timeout_s"] for r in rows if r["stage"] == s)/3600 for s in ["E1", "E2", "E3"]},
            "reason": "Symbolic matrix only; real manifests, scientific gates and a frozen plan are required"})
    elif args.command == "preflight":
        devices = inventory()
        report = {"status": "awaiting_verification", "devices": devices, "limits": limits,
                  "idle_gpus": [g for g, d in devices.items() if not d["compute_pids"] and d["free_mib"] >= 4096],
                  "scientific_readiness": config["readiness"], "training_stack": "not implemented",
                  "runtime": {"python": sys.version, "prefix": sys.prefix}, "experiment_started": False}
        write(args.output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.command == "prepare":
        prepare(args, config, limits)
    elif args.command == "prepare-prerequisites":
        prepare_prerequisites(args, config)
    else:
        def interrupted(signum, frame):
            raise KeyboardInterrupt("Coordinator interrupted; clean up only owned process groups")
        signal.signal(signal.SIGTERM, interrupted)
        run(args, config, limits)


if __name__ == "__main__":
    main()
