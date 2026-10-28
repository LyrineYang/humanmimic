"""Report all ten fixed R1 trials without dropping failures or replacing missing runs."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def audit(directory):
    manifest_path = ROOT / "configs/r1-suite.json"
    manifest = read(manifest_path)
    readiness = read(directory / "readiness.json")
    if readiness["status"] != "passed" or readiness["manifest_sha256"] != hashlib.sha256(manifest_path.read_bytes()).hexdigest():
        raise ValueError("Suite readiness or frozen manifest changed; create a new suite directory")
    evaluation_path = ROOT / manifest["evaluation_file"]
    if hashlib.sha256(evaluation_path.read_bytes()).hexdigest() != manifest["evaluation_sha256"]:
        raise ValueError("Frozen evaluation rules changed after preparation")
    rules = read(evaluation_path)
    binary = next(i["sha256"] for i in manifest["runtime_inputs"] if i["path"].endswith("g1_deploy_onnx_ref"))
    dds = next(i["sha256"] for i in manifest["runtime_inputs"] if i["path"] == "configs/r1-dds.xml")
    results, motion_results = [], []
    for motion in manifest["motions"]:
        statuses = []
        for trial in range(1, manifest["trials_per_motion"] + 1):
            run = directory / f"{motion['name']}-trial-{trial:02d}"
            status, detail = "awaiting_verification", "Not run or incomplete evidence"
            required = ["metrics.json", "full-sample-metrics.json", "completion-audit.json", "run-config.json"]
            evidence = ["actual-state.npz", "actual-execution.mp4", "controller-csv/q.csv", "controller-reference.csv"]
            rmse = None
            if all((run / name).is_file() and (run / name).stat().st_size > 0 for name in required + evidence):
                online, full, completion, config = [read(run / name) for name in required]
                rmse = full.get("joint_rmse_rad")
                expected = dict(rules, motion_name=motion["name"], reference_frames=motion["frames"],
                                reference_csv_sha256=next(f["sha256"] for f in motion["files"] if f["name"] == "joint_pos.csv"))
                same_config = all(config.get(k) == v for k, v in expected.items())
                same_policy = all(config.get("model_hashes", {}).get(Path(i["path"]).name) == i["sha256"]
                                  for i in manifest["runtime_inputs"] if "/policy/release/" in i["path"])
                physics = (online.get("fell") is False and online.get("actual_state_overwrites") is False
                           and all(online.get(k) is True for k in ["elastic_band_off_during_playback", "finite_states",
                               "dds_commands_received", "nonzero_control_torques", "free_root_gravity_contact_controller"]))
                passed = (same_config and same_policy and config.get("binary_sha256") == binary
                          and config.get("upstream_commit") == manifest["upstream_commit"]
                          and config.get("upstream_patch_sha256") == manifest["upstream_patch_sha256"]
                          and config.get("dds_xml_sha256") == dds
                          and online.get("status") == full.get("status") == completion.get("status") == "passed"
                          and online.get("motion_completed") is True and completion.get("video_decodes") is True
                          and full.get("all_motion_frames_present") is True and full.get("control_samples") == motion["frames"]
                          and isinstance(rmse, (int, float)) and rmse <= rules["joint_rmse_max_rad"] and physics)
                status = "passed" if passed else "failed"
                detail = "Complete frozen-config trial audit" if passed else "Trial failed or does not match the frozen evidence requirements"
            elif (run / "metrics.json").exists() and read(run / "metrics.json").get("status") == "failed":
                status, detail = "failed", "Controller/physics trial failure; raw evidence retained"
            elif any((run / name).exists() for name in ["artifact-error.json", "audit-failed.flag", "launcher-failed.flag"]):
                status, detail = "failed", "Artifact generation/audit failed; inspect the retained error"
            statuses.append(status)
            results.append({"motion": motion["name"], "trial": trial, "status": status,
                            "joint_rmse_rad": rmse, "run_directory": str(run.relative_to(ROOT)), "detail": detail})
        motion_results.append({"motion": motion["name"], "both_trials_passed": statuses == ["passed", "passed"]})
    passed_count = sum(m["both_trials_passed"] for m in motion_results)
    pending = any(r["status"] == "awaiting_verification" for r in results)
    status = "awaiting_verification" if pending else "passed" if passed_count >= manifest["minimum_passing_motions"] else "failed"
    result = {"status": status, "passing_motions": passed_count, "required_passing_motions": manifest["minimum_passing_motions"],
              "trials": results, "motions": motion_results, "scope": "R1 five-motion/two-trial gate only; R2-R4 remain separate"}
    (directory / "suite-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if status == "passed" else 2 if pending else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, required=True)
    args = parser.parse_args()
    directory = args.suite.resolve()
    if not directory.is_relative_to(ROOT / "runs"):
        parser.error("--suite must be below the project's runs/ directory")
    raise SystemExit(audit(directory))
