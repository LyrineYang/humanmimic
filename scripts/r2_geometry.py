"""Trunk and foot direction in a body frame, with fixed anatomical signs."""

import numpy as np


def body_frame_descriptors(points, up_axis=2):
    """Input order: hips[0:2], shoulders[6:8], matching the evaluator anchors.

    Positive twist/lateral lean turns toward anatomical left; forward lean
    points toward cross(left-hip axis, up). No per-video orientation fitting.
    """
    up = np.eye(3)[up_axis]
    hips = (points[:, 0] + points[:, 1]) / 2
    shoulders = (points[:, 6] + points[:, 7]) / 2
    torso = shoulders - hips
    hip_left = points[:, 0] - points[:, 1]
    shoulder_left = points[:, 6] - points[:, 7]
    hip_left = hip_left - (hip_left @ up)[:, None] * up
    shoulder_left = shoulder_left - (shoulder_left @ up)[:, None] * up

    def unit(value):
        norm = np.linalg.norm(value, axis=-1, keepdims=True)
        return np.divide(value, norm, out=np.full_like(value, np.nan), where=norm > 1e-8)

    left = unit(hip_left)
    shoulder_axis = unit(shoulder_left)
    forward = np.cross(left, up)
    vertical = torso @ up
    horizontal = torso - vertical[:, None] * up
    values = {
        "torso_tilt_rad": np.arctan2(np.linalg.norm(horizontal, axis=-1), vertical),
        "torso_forward_lean_rad": np.arctan2(np.sum(torso * forward, axis=-1), vertical),
        "torso_left_lean_rad": np.arctan2(np.sum(torso * left, axis=-1), vertical),
        "torso_twist_rad": np.arctan2(np.cross(left, shoulder_axis) @ up, np.sum(left * shoulder_axis, axis=-1)),
    }
    for side, hip, knee, ankle in (("left", 0, 2, 4), ("right", 1, 3, 5)):
        leg = np.linalg.norm(points[:, hip] - points[:, knee], axis=-1) + np.linalg.norm(points[:, knee] - points[:, ankle], axis=-1)
        projection = np.sum((points[:, ankle] - points[:, hip]) * forward, axis=-1)
        values[f"{side}_ankle_forward_hip_units"] = np.divide(projection, leg, out=np.full_like(leg, np.nan), where=leg > 1e-8)
    valid = (np.linalg.norm(torso, axis=-1) > 1e-8) & np.isfinite(left).all(axis=-1) & np.isfinite(shoulder_axis).all(axis=-1)
    return {name: np.where(valid, value, np.nan) for name, value in values.items()}


def descriptor_difference(name, actual, reference):
    difference = actual - reference
    if name == "torso_twist_rad":
        difference = (difference + np.pi) % (2 * np.pi) - np.pi
    return difference
