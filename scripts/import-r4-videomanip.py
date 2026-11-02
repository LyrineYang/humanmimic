#!/usr/bin/env python3
"""Convert numeric VideoManip LEAP output to an explicit, audited trajectory."""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from r4_contract import JOINT_NAMES, SOURCE_JOINT_NAMES, sha256, validate_contract, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qpos", type=Path, required=True)
    parser.add_argument("--indices", type=Path, required=True)
    parser.add_argument("--timestamps", type=Path, required=True, help="Full source timeline numeric NPY, seconds")
    parser.add_argument("--metadata", type=Path, required=True, help="Explicit hand, joint_names, rotation, transform, source video path and commit")
    parser.add_argument("--source-urdf", type=Path, help="Required for the VideoManip URDF base frame; supplies its fixed base-to-palm transform")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    meta = json.loads(args.metadata.read_text())
    if meta.get("hand") != "leap_right" or meta.get("joint_names") != SOURCE_JOINT_NAMES:
        raise ValueError("Require verified LEAP source joint order; default upstream Inspire is not interchangeable")
    semantics = meta.get("base_rotation")
    if semantics not in {"rotvec", "euler_XYZ_intrinsic"}:
        raise ValueError("Specify verified base_rotation; do not guess from upstream comments")
    if meta.get("units") != {"length": "m", "angle": "rad"}:
        raise ValueError("Source units must explicitly be metres and radians")
    transform = np.asarray(meta.get("T_world_source"), dtype=float)
    if transform.shape != (4, 4) or not np.isfinite(transform).all():
        raise ValueError("Expected finite 4x4 T_world_source")
    if not np.allclose(transform[3], [0, 0, 0, 1]) or not np.allclose(transform[:3, :3].T @ transform[:3, :3], np.eye(3), atol=1e-6) or not np.isclose(np.linalg.det(transform[:3, :3]), 1, atol=1e-6):
        raise ValueError("World transform must be rigid, not a scale/reflection")
    q = np.load(args.qpos, allow_pickle=False)
    indices = np.load(args.indices, allow_pickle=False)
    timeline = np.load(args.timestamps, allow_pickle=False)
    if q.ndim != 2 or q.shape[1] != 22 or q.dtype.kind not in "fi" or not np.isfinite(q).all():
        raise ValueError("Require finite N x 22 LEAP positions (6 base + 16 fingers)")
    if indices.shape != (len(q),) or indices.dtype.kind not in "iu" or np.any(indices < 0) or np.any(np.diff(indices.astype(np.int64)) <= 0):
        raise ValueError("Indices must be unique, increasing integers aligned with qpos")
    if timeline.ndim != 1 or timeline.dtype.kind not in "fi" or not np.isfinite(timeline).all() or np.any(np.diff(timeline) <= 0) or timeline[0] < 0 or int(indices.max()) >= len(timeline):
        raise ValueError("Full source timestamps invalid or insufficient")
    video = Path(meta["source_video"])
    if not video.is_absolute():
        video = args.metadata.parent / video
    video_hash = sha256(video)
    if meta.get("source_video_sha256") and meta["source_video_sha256"] != video_hash:
        raise ValueError("Source video changed")
    rotations = Rotation.from_rotvec(q[:, 3:6]) if semantics == "rotvec" else Rotation.from_euler("XYZ", q[:, 3:6])
    base_to_palm = np.eye(4)
    if meta.get("wrist_frame") == "urdf_base":
        if not args.source_urdf:
            raise ValueError("URDF base is not the palm frame; --source-urdf is required")
        urdf = ET.parse(args.source_urdf).getroot()
        joint = urdf.find("joint[@name='base_joint']")
        if joint is None or joint.get("type") != "fixed" or joint.find("parent").get("link") != "base" or joint.find("child").get("link") != "palm_lower":
            raise ValueError("Unsupported source base-to-palm chain; verify it explicitly")
        origin = joint.find("origin")
        base_to_palm[:3, 3] = np.fromstring(origin.get("xyz", "0 0 0"), sep=" ")
        base_to_palm[:3, :3] = Rotation.from_euler("xyz", np.fromstring(origin.get("rpy", "0 0 0"), sep=" ")).as_matrix()
    elif meta.get("wrist_frame") != "palm":
        raise ValueError("Specify wrist_frame as urdf_base or palm")
    transformed_rotation = Rotation.from_matrix(transform[:3, :3]) * rotations * Rotation.from_matrix(base_to_palm[:3, :3])
    quat = transformed_rotation.as_quat()[:, [3, 0, 1, 2]]
    positions_in_source = q[:, :3] + rotations.apply(base_to_palm[:3, 3])
    positions = positions_in_source @ transform[:3, :3].T + transform[:3, 3]
    frames = [{"time_s": float(timeline[index]), "source_index": int(index), "joint_position": row[6:].tolist(),
               "wrist_position": pos.tolist(), "wrist_quaternion": rot.tolist()}
              for index, row, pos, rot in zip(indices, q, positions, quat)]
    if meta.get("kind") not in {"video_reconstruction", "synthetic_fixture"}:
        raise ValueError("Declare whether these arrays came from a real reconstruction or a synthetic fixture")
    result = {"schema_version": 1, "kind": meta["kind"], "split": meta["split"], "hand": "leap_right",
              "joint_names": JOINT_NAMES, "units": {"length": "m", "angle": "rad", "time": "s"},
              "frame": "world_z_up", "quaternion_order": "wxyz", "frames": frames,
              "provenance": {"source_video_sha256": video_hash, "source_commit": meta["source_commit"],
                             "input_qpos_sha256": sha256(args.qpos), "indices_sha256": sha256(args.indices),
                             "timestamps_sha256": sha256(args.timestamps), "metadata_sha256": sha256(args.metadata),
                             "rotation_semantics": semantics, "T_world_source": transform.tolist(),
                             "T_sourcebase_palm": base_to_palm.tolist(),
                             "source_urdf_sha256": sha256(args.source_urdf) if args.source_urdf else None,
                             "missing_source_indices": sorted(set(range(int(indices[0]), int(indices[-1]) + 1)) - set(indices.tolist()))}}
    validate_contract(result)
    write_json(args.output, result)
    print(json.dumps({"status": "passed", "scope": "format conversion, not physical acceptance", "frames": len(frames), "output": str(args.output)}))


if __name__ == "__main__":
    main()
