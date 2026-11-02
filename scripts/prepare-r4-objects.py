#!/usr/bin/env python3
"""Generate development-only analytic geometry; never materialize held-out instances."""
import argparse
import copy
import json
import random
from pathlib import Path

from r4_contract import sha256, write_json


def box(position, half_size):
    return {"type": "box", "position": position, "size": half_size}


def parts_for(seed, family):
    rng = random.Random(seed)
    w, d, h = rng.uniform(.018, .026), rng.uniform(.018, .026), rng.uniform(.018, .028)
    if family == "stepped_prism":
        # Explicit terraced bevel approximation, not an exact smooth chamfer.
        parts = [box([0, 0, -.004], [w, d, h - .004]), box([0, 0, h - .004], [w - .003, d - .003, .004])]
    elif family == "grooved_block":
        parts = [box([0, 0, -.006], [w, d, h - .006]), box([-w + .005, 0, h - .006], [.005, d, .006]), box([w - .005, 0, h - .006], [.005, d, .006])]
    elif family == "necked_column":
        parts = [{"type": "cylinder", "position": [0, 0, -.006], "size": [w, h - .006]},
                 {"type": "cylinder", "position": [0, 0, h - .006], "size": [w * .65, .006]}]
    else:
        parts = [box([0, 0, -h + .005], [w, d * .5, .005]),
                 box([-w + .004, 0, .005], [.004, d * .5, h - .005]),
                 box([w - .004, 0, .005], [.004, d * .5, h - .005])]
    return parts, h


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    families = ["stepped_prism", "grooved_block", "necked_column", "u_handle"]
    entries = []
    for index, seed in enumerate(range(101, 113)):
        family = families[index // 3]
        parts, height = parts_for(seed, family)
        identity = f"{family}-{seed}"
        obj_dir = args.output / identity
        obj_dir.mkdir()
        target = {"schema_version": 1, "split": "debug", "task": "precision_place", "geometry_role": "evaluation_only",
                  "object_id": identity, "initial_position": [0, 0, height + .001], "initial_quaternion": [1, 0, 0, 0],
                  "target_position": [.08, 0, height], "target_quaternion": [.9659258263, 0, 0, .2588190451],
                  "collision_representation": "analytic_convex_parts", "collision_parts": parts, "mass_kg": .08,
                  "provenance": "Procedural ground truth; accessible to evaluator only, not a video reconstruction"}
        write_json(obj_dir / "evaluation.json", target)
        entries.append({"id": identity, "seed": seed, "split": "debug", "evaluation_sha256": sha256(obj_dir / "evaluation.json")})
    write_json(args.output / "manifest.json", {"dataset": "R4-LocalGeom-v1", "generated": entries,
               "heldout_seeds_reserved_not_generated": list(range(201, 225)), "heldout_used": False,
               "observation_generation": "awaiting_verification; truth geometry is not a reconstructed planning model"})
    print(json.dumps({"development_objects": len(entries), "heldout_generated": 0, "output": str(args.output)}))


if __name__ == "__main__":
    main()
