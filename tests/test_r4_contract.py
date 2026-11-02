"""Reject scientifically invalid imports and prevent accidental heldout execution."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from r4_contract import JOINT_NAMES, read_contract, validate_contract


def fixture():
    return {"schema_version": 1, "kind": "synthetic_fixture", "split": "readiness", "hand": "leap_right",
            "joint_names": JOINT_NAMES.copy(), "units": {"length": "m", "angle": "rad", "time": "s"},
            "frame": "world_z_up", "quaternion_order": "wxyz", "provenance": {"synthetic": True},
            "frames": [{"time_s": i / 50, "source_index": i, "joint_position": [0.] * 16,
                        "wrist_position": [0., 0., .2], "wrist_quaternion": [1., 0., 0., 0.]} for i in range(2)]}


class ContractTests(unittest.TestCase):
    def test_reject_swapped_joints(self):
        doc = fixture()
        doc["joint_names"][0:2] = list(reversed(doc["joint_names"][0:2]))
        with self.assertRaises(ValueError):
            validate_contract(doc)

    def test_reject_nonphysical_data(self):
        for key, value in [("time_s", 0.), ("wrist_quaternion", [2., 0., 0., 0.]),
                           ("joint_position", [99.] * 16), ("wrist_position", [float("nan"), 0., 0.])]:
            doc = fixture()
            doc["frames"][1][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_contract(doc)

    def test_fixture_cannot_claim_video_without_provenance(self):
        doc = fixture()
        doc["kind"] = "video_reconstruction"
        with self.assertRaises(ValueError):
            validate_contract(doc)

    def test_preparation_cannot_consume_heldout(self):
        doc = fixture()
        doc["split"] = "heldout"
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "trajectory.json"
            p.write_text(json.dumps(doc))
            with self.assertRaises(ValueError):
                read_contract(p)


if __name__ == "__main__":
    unittest.main()
