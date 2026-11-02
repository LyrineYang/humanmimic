"""Exercise the actual converter, including palm offsets and invalid upstream inputs."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from r4_contract import SOURCE_JOINT_NAMES

PROJECT = Path(__file__).resolve().parents[1]


def inputs(tmp_path):
    np.save(tmp_path / "q.npy", np.zeros((2, 22)))
    np.save(tmp_path / "index.npy", np.array([0, 2]))
    np.save(tmp_path / "time.npy", np.array([0., .04, .09]))
    (tmp_path / "source.mp4").write_bytes(b"Synthetic provenance fixture, not a decoded video")
    metadata = {"kind": "synthetic_fixture", "hand": "leap_right", "joint_names": SOURCE_JOINT_NAMES,
                "base_rotation": "rotvec", "wrist_frame": "urdf_base", "units": {"length": "m", "angle": "rad"},
                "T_world_source": np.eye(4).tolist(), "source_video": "source.mp4", "source_commit": "fixture", "split": "readiness"}
    (tmp_path / "hand.urdf").write_text('<robot><joint name="base_joint" type="fixed"><parent link="base"/><child link="palm_lower"/><origin xyz="0 .038 .098" rpy="0 0 -3.141592653589793"/></joint></robot>')
    return metadata


def convert(tmp_path, metadata):
    (tmp_path / "meta.json").write_text(json.dumps(metadata))
    return subprocess.run([sys.executable, str(PROJECT / "scripts/import-r4-videomanip.py"),
                           "--qpos", str(tmp_path / "q.npy"), "--indices", str(tmp_path / "index.npy"),
                           "--timestamps", str(tmp_path / "time.npy"), "--metadata", str(tmp_path / "meta.json"),
                           "--source-urdf", str(tmp_path / "hand.urdf"), "--output", str(tmp_path / "output.json")], capture_output=True, text=True)


def test_preserves_frame_gap_and_converts_base_to_palm(tmp_path):
    result = convert(tmp_path, inputs(tmp_path))
    assert result.returncode == 0, result.stderr
    out = json.loads((tmp_path / "output.json").read_text())
    assert out["kind"] == "synthetic_fixture"
    assert out["frames"][1]["time_s"] == .09
    assert out["provenance"]["missing_source_indices"] == [1]
    assert np.allclose(out["frames"][0]["wrist_position"], [0, .038, .098])
    assert np.allclose(np.abs(out["frames"][0]["wrist_quaternion"]), [0, 0, 0, 1], atol=1e-7)


@pytest.mark.parametrize("change", ["inspire", "missing_rotation", "reflection", "wrong_units", "nonmonotonic_time", "object_pickle"])
def test_reject_invalid_import_without_output(tmp_path, change):
    meta = inputs(tmp_path)
    if change == "inspire": meta["hand"] = "inspire"
    if change == "missing_rotation": meta.pop("base_rotation")
    if change == "reflection": meta["T_world_source"][0][0] = -1
    if change == "wrong_units": meta["units"]["length"] = "mm"
    if change == "nonmonotonic_time": np.save(tmp_path / "time.npy", np.array([0., 0., .09]))
    if change == "object_pickle": np.save(tmp_path / "q.npy", np.array([{"bad": True}], dtype=object))
    result = convert(tmp_path, meta)
    assert result.returncode != 0
    assert not (tmp_path / "output.json").exists()


def test_completed_output_is_not_overwritten(tmp_path):
    meta = inputs(tmp_path)
    (tmp_path / "output.json").write_text("preserve me")
    result = convert(tmp_path, meta)
    assert result.returncode != 0
    assert (tmp_path / "output.json").read_text() == "preserve me"
