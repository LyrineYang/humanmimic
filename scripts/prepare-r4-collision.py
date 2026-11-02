#!/usr/bin/env python3
"""Convert a declared mesh into hashed convex collision parts without hiding concavity."""
import argparse
import importlib.metadata
import json
import time
from pathlib import Path

import coacd
import numpy as np
import trimesh

from r4_contract import sha256, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--scene-template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=.02)
    parser.add_argument("--max-parts", type=int, default=32)
    parser.add_argument("--seed", type=int, default=1101)
    args = parser.parse_args()
    template = json.loads(args.scene_template.read_text())
    if template.get("split") not in {"readiness", "debug"} or template.get("geometry_role") not in {"planning_only", "evaluation_only"}:
        raise ValueError("Declare preparation split and geometry role; no heldout processing")
    mesh = trimesh.load_mesh(args.mesh, process=False)
    if not isinstance(mesh, trimesh.Trimesh) or not mesh.is_watertight or not mesh.is_winding_consistent or not np.isfinite(mesh.vertices).all():
        raise ValueError("Require a finite, watertight, consistently oriented triangle mesh; repair must be explicit")
    if not 0 < mesh.volume or mesh.extents.max() > .5 or mesh.extents.min() < .001:
        raise ValueError("Mesh must have positive volume and declared metre-scale hand-object dimensions")
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    coacd.set_log_level("warn")
    parts = coacd.run_coacd(coacd.Mesh(mesh.vertices, mesh.faces), threshold=args.threshold,
                            max_convex_hull=args.max_parts, preprocess_mode="off", seed=args.seed)
    records = []
    for i, (vertices, faces) in enumerate(parts):
        part = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
        if not part.is_convex or not part.is_watertight or part.volume <= 0:
            raise ValueError("Decomposition produced an invalid/nonconvex part")
        path = (args.output / f"part-{i:03d}.obj").resolve()
        part.export(path)
        records.append({"type": "mesh", "file": str(path), "sha256": sha256(path), "convex_verified": True})
    if not records or len(records) > args.max_parts:
        raise ValueError("Invalid part count")
    template["collision_representation"] = "verified_convex_mesh_parts"
    template["collision_parts"] = records
    template["geometry_provenance"] = {"source_mesh_sha256": sha256(args.mesh), "coacd": importlib.metadata.version("coacd"),
                                      "threshold": args.threshold, "seed": args.seed, "source_volume_m3": float(mesh.volume),
                                      "wall_seconds": time.monotonic() - started,
                                      "metric_surface_error_status": "awaiting_verification; decomposition is not a millimetre accuracy certificate"}
    write_json(args.output / "scene.json", template)
    print(json.dumps({"status": "passed", "scope": "convex decomposition and integrity only", "parts": len(records), "scene": str(args.output / "scene.json")}))


if __name__ == "__main__":
    main()
