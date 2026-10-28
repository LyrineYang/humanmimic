"""Verify frozen R1 inputs and emit ten trial commands without launching simulation."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "vendor/GR00T-WholeBodyControl"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def prepare(manifest_path, output):
    manifest = json.loads(manifest_path.read_text())
    evaluation_path = ROOT / manifest["evaluation_file"]
    evaluation = json.loads(evaluation_path.read_text())
    checks = []

    def check(label, condition):
        checks.append({"check": label, "status": "passed" if condition else "failed"})

    check("frozen evaluation", digest(evaluation_path) == manifest["evaluation_sha256"])
    commit = subprocess.check_output(["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"], text=True).strip()
    check("upstream commit", commit == manifest["upstream_commit"])
    patch = subprocess.check_output(["git", "-C", str(UPSTREAM), "diff", "--binary"])
    check("applied SDK DDS patch", hashlib.sha256(patch).hexdigest() == manifest["upstream_patch_sha256"])
    for item in manifest["runtime_inputs"]:
        path = ROOT / item["path"]
        check(item["path"], path.is_file() and digest(path) == item["sha256"])
    check("five distinct motions", len(manifest["motions"]) == len({m["name"] for m in manifest["motions"]}) == 5)
    check("two fixed trials and four-motion gate", manifest["trials_per_motion"] == 2 and manifest["minimum_passing_motions"] == 4)
    resolved = []
    for motion in manifest["motions"]:
        reference = UPSTREAM / "gear_sonic_deploy/reference/example" / motion["name"]
        for item in motion["files"]:
            path = reference / item["name"]
            check(f"{motion['name']}/{item['name']}", path.is_file() and digest(path) == item["sha256"])
        joint_path = reference / "joint_pos.csv"
        if joint_path.is_file() and not joint_path.read_bytes().startswith(b"version https://git-lfs"):
            with joint_path.open() as stream:
                reader = csv.reader(stream)
                check(f"{motion['name']} CSV header", next(reader) == [f"joint_{i}" for i in range(29)])
                rows = list(reader)
            check(f"{motion['name']} frame/joint count", len(rows) == motion["frames"] and all(len(r) == 29 for r in rows))
        else:
            check(f"{motion['name']} materialized reference", False)
        cfg = dict(evaluation, motion_name=motion["name"], reference_frames=motion["frames"],
                   reference_csv_sha256=next(f["sha256"] for f in motion["files"] if f["name"] == "joint_pos.csv"))
        resolved.append((motion, cfg))
    output.mkdir(parents=True, exist_ok=False)
    result = {"status": "passed" if all(c["status"] == "passed" for c in checks) else "failed",
              "scope": "Input readiness only; no controller, physics or trial acceptance was run",
              "manifest_sha256": digest(manifest_path), "checks": checks,
              "R1_five_motion_acceptance": "awaiting_verification", "cloud_cost_usd": 0}
    (output / "readiness.json").write_text(json.dumps(result, indent=2) + "\n")
    if result["status"] != "passed":
        print(json.dumps(result, indent=2))
        return 1
    commands = ["#!/usr/bin/env bash", "set -u", f"cd {shlex.quote(str(ROOT))}", "source scripts/activate-r1.sh || exit 1",
                "# Runs are serial because every controller uses DDS domain 0.",
                "# Continue after failed trials and retain all results; do not replace failures."]
    trials = []
    for motion, cfg in resolved:
        config_path = output / f"{motion['name']}.json"
        config_path.write_text(json.dumps(cfg, indent=2) + "\n")
        for trial in range(1, 3):
            run_path = output / f"{motion['name']}-trial-{trial:02d}"
            run = [sys.executable, str(ROOT / "scripts/run-r1-reproduction.py"), "--evaluation", str(config_path), "--output", str(run_path)]
            summarize = [sys.executable, str(ROOT / "scripts/summarize-r1.py"), "--run", str(run_path)]
            commands.extend([f"# {motion['name']}, trial {trial}",
                             f"if {shlex.join(run)} > {shlex.quote(str(run_path) + '.launch.log')} 2>&1; then",
                             f"  if ! {shlex.join(summarize)} > {shlex.quote(str(run_path) + '.audit.log')} 2>&1; then",
                             f"    touch {shlex.quote(str(run_path / 'audit-failed.flag'))}",
                             f"    echo 'Audit failed: {run_path.name}' >&2", "  fi",
                             "else", f"  echo 'Trial failed: {run_path.name}; retain the evidence' >&2", "fi"])
            trials.append({"motion": motion["name"], "trial": trial, "run_directory": str(run_path.relative_to(ROOT)),
                           "status": "awaiting_verification"})
    commands.append(shlex.join([sys.executable, str(ROOT / "scripts/audit-r1-suite.py"), "--suite", str(output)]))
    (output / "run-trials.sh").write_text("\n".join(commands) + "\n")
    (output / "trials.json").write_text(json.dumps(trials, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "prepared_trials": len(trials),
                      "output": str(output), "executed_trials": 0}, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "configs/r1-suite.json")
    parser.add_argument("--output", type=Path, required=True, help="New directory below runs/; never overwrite previous trials")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "runs"):
        parser.error("--output must be below the project's runs/ directory")
    raise SystemExit(prepare(args.manifest.resolve(), output))
