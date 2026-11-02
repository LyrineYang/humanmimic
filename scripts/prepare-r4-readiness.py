#!/usr/bin/env python3
"""Create a clearly synthetic, intentionally unsuccessful physical control fixture."""
import argparse
from pathlib import Path

from r4_contract import JOINT_NAMES, validate_contract, write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    frames = []
    for i in range(201):
        t = i / 50
        bend = .35 * min(t, 1., max(0., 4. - t))
        joints = [bend, 0., bend, bend] * 3 + [bend] * 4
        frames.append({"time_s": t, "source_index": i, "joint_position": joints,
                       "wrist_position": [0., 0., .18 + .04 * min(t / 2, 1)], "wrist_quaternion": [0., 1., 0., 0.]})
    contract = {"schema_version": 1, "kind": "synthetic_fixture", "split": "readiness", "hand": "leap_right",
                "joint_names": JOINT_NAMES, "units": {"length": "m", "angle": "rad", "time": "s"},
                "frame": "world_z_up", "quaternion_order": "wxyz", "frames": frames,
                "provenance": {"generator": "prepare-r4-readiness.py", "purpose": "actuator/physics/negative task control; not video reconstruction"}}
    validate_contract(contract)
    write_json(args.output / "reference.json", contract)
    write_json(args.output / "evaluation-scene.json", {
        "schema_version": 1, "geometry_role": "evaluation_only", "split": "readiness", "task": "precision_place",
        "initial_position": [.16, .03, .06], "initial_quaternion": [1., 0., 0., 0.],
        "target_position": [.24, .03, .025], "target_quaternion": [.9659258263, 0., 0., .2588190451],
        "collision_representation": "analytic_convex_parts", "collision_parts": [{"type": "box", "size": [.02, .025, .025]}],
        "mass_kg": .08, "camera_lookat": [.03, .025, .16],
        "expected": "execution passed, task failed: object falls under gravity; hand does not acquire it"})
    print(args.output)


if __name__ == "__main__":
    main()
