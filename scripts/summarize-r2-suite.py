"""Report every reviewed debug/test source, including missing and failed runs."""

import argparse
import json
from pathlib import Path

from r2_common import sha256, storage_check, write_json


def summarize(manifest, manifest_hash):
    groups = {}
    for role in ("debug", "heldout"):
        rows = []
        for item in manifest[role]:
            row = {key: item[key] for key in ("id", "source_url", "source_sha256", "action_class")}
            row.update(status="awaiting_verification", audit=item.get("audit_json"), run_id=item.get("run_id"))
            if row["audit"] and Path(row["audit"]).is_file():
                audit = json.loads(Path(row["audit"]).read_text())
                row["status"] = audit["status"]
                if audit.get("source_sha256", audit.get("extraction", {}).get("source_sha256")) != item["source_sha256"]:
                    row.update(status="failed", reason="Audit/source identity differs", integrity_error=True)
                if role == "heldout" and audit.get("frozen_suite_sha256") != manifest_hash:
                    row.update(status="failed", reason="Heldout audit is not bound to this frozen suite", integrity_error=True)
                for field in ("physical_status", "body_status", "media_status", "visual_status", "all_robot_frames_available"):
                    if field in audit:
                        row[field] = audit[field]
                row["audit_sha256"] = sha256(row["audit"])
            rows.append(row)
        groups[role] = rows
    debug_done = len(groups["debug"]) == 5 and all(row["status"] in ("passed", "failed") for row in groups["debug"])
    tests_done = len(groups["heldout"]) == 5 and all(row["status"] in ("passed", "failed") for row in groups["heldout"])
    test_passed = sum(row["status"] == "passed" for row in groups["heldout"])
    diversity = all(len({row["action_class"] for row in groups[role]}) >= 3 for role in ("debug", "heldout"))
    frozen = manifest["status"] == "frozen"
    integrity = not any(row.get("integrity_error") for rows in groups.values() for row in rows)
    status = "awaiting_verification"
    if frozen and debug_done and tests_done:
        status = "passed" if diversity and integrity and test_passed >= 4 else "failed"
    return {"status": status, "scope": "R2 5-debug/5-heldout complete-video engineering acceptance only; R3/R4 remain separate", "frozen_suite": frozen, "manifest_sha256": manifest_hash, "source_and_freeze_identities_valid": integrity, "debug_terminal": sum(row["status"] in ("passed", "failed") for row in groups["debug"]), "heldout_terminal": sum(row["status"] in ("passed", "failed") for row in groups["heldout"]), "heldout_passed": test_passed, "heldout_required_passes": 4, "each_group_at_least_three_action_classes": diversity, "groups": groups, "cloud_cost_usd": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New summary directory")
    args = parser.parse_args()
    storage_check(args.output)
    args.output.mkdir(parents=True, exist_ok=False)
    report = summarize(json.loads(args.manifest.read_text()), sha256(args.manifest))
    write_json(args.output / "suite-summary.json", report)
    lines = ["# R2 整批结果", "", f"状态：{report['status']}；调试完成{report['debug_terminal']}/5，保留完成{report['heldout_terminal']}/5，通过{report['heldout_passed']}/5（要求≥4）。", "", "| 分组 | 来源 | 类别 | 状态 | 原始审计 |", "| --- | --- | --- | --- | --- |"]
    for role, rows in report["groups"].items():
        for row in rows:
            audit = f"[审计]({row['audit']})" if row["audit"] else "未运行"
            lines.append(f"| {role} | [{row['id']}]({row['source_url']}) | {row['action_class']} | {row['status']} | {audit} |")
    lines += ["", "结果包含所有来源及失败，源视频保持完整；单目提取不是人体三维真值。视频/实际状态/事件细节保存在每条审计对应的运行目录。R3/R4及整个项目不因R2结论而完成。"]
    (args.output / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({key: report[key] for key in ("status", "debug_terminal", "heldout_terminal", "heldout_passed")}, indent=2))
    raise SystemExit({"passed": 0, "failed": 1, "awaiting_verification": 2}[report["status"]])
