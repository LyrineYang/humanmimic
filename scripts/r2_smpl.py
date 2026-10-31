"""Adapt the matched GEM-X SOMA geometry to SONIC's official SMPL convention."""

from pathlib import Path
import sys

import numpy as np
import torch
from scipy.spatial.transform import Rotation, Slerp

from r2_common import SONIC, STORAGE, write_json

sys.path.insert(0, str(SONIC / "gear_sonic/examples/live_camera_teleop"))
from soma_to_smpl import SomaToSmpl, build_soma_to_smpl_index


class SonicSomaAdapter:
    def __init__(self, core):
        self.core = core
        from gem.motion.frontend.joint_sets import SOMA77_JOINT_NAMES
        # The 0.3.3 target rig includes extra procedural joints. Its public
        # positions are selected by public_joint_indices (Root excluded).
        # Never index this public output using target-rig joint_names.
        names = list(core.runtime.public_joint_names)
        if len(names) == 78 and names[0].lower() == "root":
            names = names[1:]
        if tuple(names) != tuple(SOMA77_JOINT_NAMES):
            raise ValueError("SOMA public joint layout differs from the pinned native77 schema")
        if core.runtime.public_joint_indices.numel() != 77:
            raise ValueError("SOMA public joint selector is not 77 joints")
        self.joint_names = names

    def __call__(self, **parameters):
        return self.core(**parameters, return_joints_only=True, repose_to_bind_pose=True)


def frame_values(parameters, index):
    values = {}
    length = parameters["global_orient"].shape[1]
    for name in ("global_orient", "body_pose", "transl", "identity_coeffs", "scale_params"):
        value = parameters[name]
        if name in ("identity_coeffs", "scale_params") and value.ndim == 2:
            selected = value[0]
        else:
            if value.shape[:2] != (1, length):
                raise ValueError(f"Unexpected subject/time dimensions: {name} {value.shape}")
            selected = value[0, index]
        values[name] = selected.reshape(-1).to(device="cpu", dtype=torch.float32)
    return values


@torch.inference_mode()
def convert_motion(output: Path, result):
    from gem.common.soma import SomaFixedGs1BodyAdapter, SomaRuntimeConfig
    parameters = result["pred_soma_params_global"]
    length = parameters["global_orient"].shape[1]
    core = SomaFixedGs1BodyAdapter(SomaRuntimeConfig(data_root=STORAGE / "models/soma-v0.3.3", device="cpu", lod="mid", apply_correctives=False, enable_procedural_transforms=True))
    shim = SonicSomaAdapter(core)
    converter = SomaToSmpl(shim, device="cpu", smooth=0.0, sonic_root=str(SONIC))
    names = converter.soma_joint_names
    if len(names) != 77:
        raise ValueError("Expected exactly 77 public SOMA joints")
    mapping = build_soma_to_smpl_index(names)
    joints_world, local, quaternions = [], [], []
    for start in range(0, length, 32):
        stop = min(start + 32, length)
        packed = {name: torch.stack([frame_values(parameters, i)[name] for i in range(start, stop)]) for name in ("global_orient", "body_pose", "transl", "identity_coeffs", "scale_params")}
        positions = shim(**packed)["joints"]
        if positions.shape != (stop - start, 77, 3):
            raise ValueError(f"Unexpected SOMA joint shape: {positions.shape}")
        q = converter._remove_base_rot(converter._ytoz(converter._aa2quat(packed["global_orient"])), w_last=False)
        selected = positions[:, mapping]
        centered = (selected - selected[:, :1]) @ converter._R_up.T
        rotated = converter._quat_apply(converter._quat_inv(q).repeat_interleave(24, dim=0), centered.reshape(-1, 3)).reshape(-1, 24, 3)
        joints_world.append(positions.cpu().numpy())
        local.append(rotated.cpu().numpy())
        quaternions.append(q.cpu().numpy())
    joints_world = np.concatenate(joints_world).astype(np.float32)
    local = np.concatenate(local).astype(np.float32)
    quaternions = np.concatenate(quaternions).astype(np.float32)
    if not np.isfinite(local).all() or not np.isfinite(quaternions).all():
        raise ValueError("Nonfinite converted references")
    if not np.allclose(np.linalg.norm(quaternions, axis=-1), 1, atol=1e-5):
        raise ValueError("Nonunit body orientation")
    checks = []
    for index in sorted({0, length // 2, length - 1}):
        expected = converter.convert(frame_values(parameters, index))
        joint_error = float(np.max(np.abs(expected["smpl_joints"][0] - local[index])))
        quat_error = float(np.max(np.abs(expected["body_quat"][0] - quaternions[index])))
        checks.append({"frame": index, "joint_max_abs_error_m": joint_error, "quaternion_max_abs_error": quat_error})
        if joint_error > 2e-5 or quat_error > 2e-5:
            raise ValueError("Batched conversion differs from official SONIC conversion")
    times = np.arange(length, dtype=np.float64) / 30
    duration = length / 30
    target_times = np.arange(int(np.ceil(duration * 50)), dtype=np.float64) / 50
    flat = local.reshape(length, -1)
    sampled = np.stack([np.interp(target_times, times, column) for column in flat.T], axis=-1).reshape(-1, 24, 3).astype(np.float32)
    interpolator = Slerp(times, Rotation.from_quat(quaternions[:, [1, 2, 3, 0]]))
    sampled_q = interpolator(np.clip(target_times, times[0], times[-1])).as_quat()[:, [3, 0, 1, 2]].astype(np.float32)
    np.savez_compressed(output / "soma-joints.npz", joints_world_yup_m=joints_world, joint_names=np.asarray(names), timestamps=times, global_orient=parameters["global_orient"][0].numpy())
    np.savez_compressed(output / "smpl-source.npz", smpl_joints=local, body_quat=quaternions, timestamps=times)
    np.savez_compressed(output / "sonic-reference.npz", smpl_joints=sampled, body_quat=sampled_q, smpl_pose=np.zeros((len(target_times), 21, 3), dtype=np.float32), joint_pos=np.zeros((len(target_times), 29), dtype=np.float32), joint_vel=np.zeros((len(target_times), 29), dtype=np.float32), timestamps=target_times, source_normalized_frame_float=np.clip(target_times * 30, 0, length - 1), frame_index=np.arange(len(target_times), dtype=np.int64))
    write_json(output / "conversion.json", {"status": "passed", "scope": "SOMA/SMPL conversion and 30->50 Hz resampling; no robot execution", "joint_names": names, "smpl_indices": mapping, "source_frames": length, "control_frames": len(target_times), "source_duration_seconds": duration, "source_fps": 30, "control_fps": 50, "smoothing": "none beyond official GEM-X Contact/IK", "geometry": "SOMA 0.3.3 MID, runtime procedural reference, joints only", "axes": "Y-up to Z-up; official SONIC base rotation removal and root-local convention", "quaternion_order": "wxyz", "joint_resampling": "linear", "orientation_resampling": "SLERP, endpoint hold only inside the final source frame", "source_content_trimmed": False, "source_translation_retained_but_not_streamed": True, "smpl_pose_field": "zero as in official body-only bridge; encoder uses SMPL positions/orientation", "wrists": "zero as in official body-only bridge", "official_converter_checks": checks, "not_full_smpl_mesh_model": True})
