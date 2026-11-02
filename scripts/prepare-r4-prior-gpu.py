#!/usr/bin/env python3
"""Initialize a generic coarse ellipsoid using public RGB-D only, on CUDA.

Partial-view PCA is a biased initializer, not a recovered hidden surface. Users
may supply a better observed coarse mesh in the same strict prior schema.
"""
import argparse
import json
from pathlib import Path
import torch
from r4_contract import sha256, write_json
from r4_cuda import require_cuda
from r4_gpu_geometry import ellipsoid
from r4_public import validate_frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    device, gpu = require_cuda()
    previous = -1
    chosen = None
    with (args.observations / "observations.jsonl").open() as handle:
        for line in handle:
            frame = validate_frame(json.loads(line), previous)
            previous = frame["time_s"]
            if frame["vision"] and len(frame["vision"]["points_world_m"]) >= 32:
                chosen = frame
                break
    if chosen is None:
        raise ValueError("No adequate observed RGB-D frame; do not initialize from truth")
    points = torch.tensor(chosen["vision"]["points_world_m"], device=device, dtype=torch.float64)
    center = points.mean(0)
    _, axes = torch.linalg.eigh((points-center).T @ (points-center) / len(points))
    axes[:, 0] *= torch.linalg.det(axes).sign()
    local = (points-center) @ axes
    radii = torch.quantile(local.abs(), .98, dim=0).clamp_min(.005)
    vertices, normals, faces = ellipsoid(radii)
    transform = torch.eye(4, device=device, dtype=torch.float64)
    transform[:3, :3], transform[:3, 3] = axes, center
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output/"prior.json", {"schema_version": 2, "role": "coarse_estimate", "source": "observed_rgbd",
        "vertices_object_m": vertices.tolist(), "normals_object": normals.tolist(), "faces": faces.tolist(),
        "roi_vertex_indices": list(range(len(vertices))), "T_world_object_initial": transform.tolist(),
        "initial_time_s": chosen["time_s"], "compliance_initial_m_per_n": .001})
    write_json(args.output/"manifest.json", {"status": "awaiting_verification", "execution_status": "completed",
        "gpu": gpu, "observation_sha256": sha256(args.observations/"observations.jsonl"), "frame_time_s": chosen["time_s"],
        "source_sha256": sha256(Path(__file__)), "heldout_used": False,
        "limitation": "Single-view generic ellipsoid; unknown hidden topology and partial-view center bias. Not an oracle or successful shape reconstruction."})


if __name__ == "__main__":
    main()
