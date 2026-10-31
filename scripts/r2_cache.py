"""Verify immutable video extraction artifacts independently of new control."""

import ast
import json
from pathlib import Path

from r2_common import sha256


def verify_cached_extraction(extraction):
    extraction = Path(extraction)
    identity = json.loads((extraction / "input.json").read_text())
    if sha256(extraction / "source-original.mp4") != identity["input_sha256"]:
        raise ValueError("Original source identity changed")
    snapshot = extraction / "source-snapshot"
    for relative, digest in json.loads((snapshot / "sha256.json").read_text()).items():
        if sha256(snapshot / relative) != digest:
            raise ValueError(f"Execution source snapshot changed: {relative}")
    tree = ast.parse((snapshot / "scripts/extract-r2-video.py").read_text())
    definitions = {target.id: node.value for node in tree.body if isinstance(node, ast.Assign) for target in node.targets if isinstance(target, ast.Name)}
    stages, outputs = (ast.literal_eval(definitions[name]) for name in ("STAGES", "OUTPUTS"))
    markers, artifacts = {}, {}
    for stage in stages:
        path = extraction / f"{stage}-complete.json"
        complete = json.loads(path.read_text())
        if complete["status"] != "passed" or set(complete["sha256"]) != set(outputs[stage]):
            raise ValueError(f"Incomplete stage evidence: {stage}")
        for filename, digest in complete["sha256"].items():
            if sha256(extraction / filename) != digest:
                raise ValueError(f"Changed {stage} artifact: {filename}")
            artifacts[filename] = digest
        markers[stage] = sha256(path)
    return {"summary": {"status": "passed", "verified_stages": list(stages), "source_sha256": identity["input_sha256"], "role": identity["role"]},
            "fingerprint": {"input_sha256": sha256(extraction / "input.json"), "snapshot_manifest_sha256": sha256(snapshot / "sha256.json"), "stage_markers_sha256": markers, "artifacts_sha256": artifacts}}
