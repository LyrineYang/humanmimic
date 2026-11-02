"""Explicit R4 trajectory contract. Validation uses only the Python standard library."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

JOINT_NAMES = [f"{finger}_{joint}" for finger in ("if", "mf", "rf")
               for joint in ("mcp", "rot", "pip", "dip")] + ["th_cmc", "th_axl", "th_mcp", "th_ipl"]
SOURCE_JOINT_NAMES = ["1", "0", "2", "3", "5", "4", "6", "7", "9", "8", "10", "11", "12", "13", "14", "15"]
JOINT_LIMITS = [(-.314, 2.23), (-1.047, 1.047), (-.506, 1.885), (-.366, 2.042)] * 3 + [
    (-.349, 2.094), (-.349, 2.094), (-.47, 2.443), (-1.34, 1.88)]


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def vector(value, size, name):
    if not isinstance(value, list) or len(value) != size:
        raise ValueError(f"{name}: expected {size} values")
    if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in value):
        raise ValueError(f"{name}: expected finite numeric values")


def validate_contract(document):
    required = {"schema_version", "kind", "split", "hand", "joint_names", "units", "frame", "frames", "provenance"}
    if not required.issubset(document):
        raise ValueError(f"Missing fields: {sorted(required - document.keys())}")
    if document["schema_version"] != 1 or document["hand"] != "leap_right":
        raise ValueError("Only schema 1, right LEAP is supported")
    if document["kind"] not in {"synthetic_fixture", "video_reconstruction"}:
        raise ValueError("Unknown input provenance kind")
    if document["split"] not in {"readiness", "debug", "heldout"}:
        raise ValueError("Unknown data split")
    if document["joint_names"] != JOINT_NAMES:
        raise ValueError("Joint names/order differ from the explicit LEAP mapping")
    if document["units"] != {"length": "m", "angle": "rad", "time": "s"}:
        raise ValueError("Units must be metres, radians and seconds")
    if document["frame"] != "world_z_up" or document.get("quaternion_order") != "wxyz":
        raise ValueError("World frame and quaternion convention must be explicit")
    if not isinstance(document["provenance"], dict) or not document["provenance"]:
        raise ValueError("Provenance is required")
    if document["kind"] == "video_reconstruction":
        for field in ("source_video_sha256", "source_commit", "input_qpos_sha256", "rotation_semantics"):
            if not document["provenance"].get(field):
                raise ValueError(f"Missing video provenance: {field}")
    frames = document["frames"]
    if not isinstance(frames, list) or len(frames) < 2:
        raise ValueError("At least two timestamped frames are required")
    previous_t, previous_index = -math.inf, -1
    for i, frame in enumerate(frames):
        t, index = frame.get("time_s"), frame.get("source_index")
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t) or t < 0 or t <= previous_t:
            raise ValueError(f"Frame {i}: timestamps must be finite, nonnegative and strictly increasing")
        if isinstance(index, bool) or not isinstance(index, int) or index <= previous_index:
            raise ValueError(f"Frame {i}: source indices must be strictly increasing integers")
        vector(frame.get("joint_position"), 16, f"frame {i} joints")
        vector(frame.get("wrist_position"), 3, f"frame {i} wrist")
        vector(frame.get("wrist_quaternion"), 4, f"frame {i} quaternion")
        if abs(sum(v * v for v in frame["wrist_quaternion"]) - 1) > 1e-5:
            raise ValueError(f"Frame {i}: quaternion is not normalized")
        for j, (v, (low, high)) in enumerate(zip(frame["joint_position"], JOINT_LIMITS)):
            if not low - 1e-6 <= v <= high + 1e-6:
                raise ValueError(f"Frame {i}: {JOINT_NAMES[j]} outside limits; no silent clipping")
        previous_t, previous_index = t, index
    return document


def read_contract(path, *, allow_heldout=False):
    document = validate_contract(json.loads(Path(path).read_text()))
    if document["split"] == "heldout" and not allow_heldout:
        raise ValueError("Held-out execution is disabled in preparation; freeze and use a separately authorized suite")
    return document
