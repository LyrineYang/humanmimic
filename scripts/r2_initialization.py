"""Fixed reference-only startup, with every video sample retained unchanged."""

import numpy as np
from scipy.spatial.transform import Rotation

HOLD = 50
PREFIX = 100
CHAINS = ((1, 4, 7, 10), (2, 5, 8, 11))
FIELDS = ("smpl_joints", "smpl_pose", "joint_pos", "joint_vel", "body_quat")


def metadata():
    return {"method": "neutral_legs_smoothstep_v1", "static_hold_frames": HOLD,
            "transition_frames": PREFIX, "source_samples_modified": False}


def direction_path(start, end, fraction):
    dot = np.clip(start @ end, -1., 1.)
    angle = np.arccos(dot)
    tangent = end - dot * start
    norm = np.linalg.norm(tangent)
    if norm < 1e-10:
        basis = np.eye(3)[np.argmin(abs(start))]
        tangent = basis - (basis @ start) * start
        norm = np.linalg.norm(tangent)
    tangent /= norm
    result = np.cos(fraction[:, None] * angle) * start + np.sin(fraction[:, None] * angle) * tangent
    result[0], result[-1] = start, end
    return result


def neutral_leg_prefix(first, quaternion):
    first = np.asarray(first, dtype=np.float64)
    if first.shape != (24, 3) or not np.isfinite(first).all():
        raise ValueError("Expected finite SMPL24 positions")
    quaternion = np.asarray(quaternion, dtype=np.float64)
    if quaternion.shape != (4,) or not np.isfinite(quaternion).all() or abs(np.linalg.norm(quaternion) - 1) > 1e-5:
        raise ValueError("Expected unit wxyz orientation")
    rotation = Rotation.from_quat(quaternion[[1, 2, 3, 0]])
    left = rotation.apply(first[1] - first[2])
    left[2] = 0
    if np.linalg.norm(left) < 1e-8:
        raise ValueError("Cannot infer horizontal hip axis")
    left /= np.linalg.norm(left)
    down = rotation.inv().apply([0., 0., -1.])
    forward = rotation.inv().apply(np.cross(left, [0., 0., 1.]))
    u = np.linspace(0., 1., PREFIX)
    fraction = u * u * (3 - 2 * u)
    result = np.repeat(first[None], PREFIX, axis=0)
    for chain in CHAINS:
        for segment, (parent, child) in enumerate(zip(chain, chain[1:])):
            vector = first[child] - first[parent]
            length = np.linalg.norm(vector)
            if length < 1e-8:
                raise ValueError("Degenerate lower-limb segment")
            neutral = forward if segment == 2 else down
            result[:, child] = result[:, parent] + length * direction_path(neutral, vector / length, fraction)
    result[-1] = first
    return result


def padded_fields(reference, future):
    """Return the declared initialization + original source + future context."""
    count = len(reference["smpl_joints"])
    if count == 0 or future < 0:
        raise ValueError("Expected nonempty source and nonnegative padding")
    transition = neutral_leg_prefix(reference["smpl_joints"][0], reference["body_quat"][0]).astype(np.float32)
    fields = {}
    for name in FIELDS:
        values = np.asarray(reference[name], dtype=np.float32)
        if len(values) != count or not np.isfinite(values).all():
            raise ValueError(f"Invalid source field: {name}")
        prefix = transition if name == "smpl_joints" else np.repeat(values[:1], PREFIX, axis=0)
        fields[name] = np.concatenate((np.repeat(prefix[:1], HOLD, axis=0), prefix, values, np.repeat(values[-1:], future, axis=0)))
    fields["frame_index"] = np.arange(HOLD + PREFIX + count + future, dtype=np.int64)
    return fields
