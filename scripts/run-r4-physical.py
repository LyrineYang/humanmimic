#!/usr/bin/env python3
"""Run a declared LEAP reference under physics and evaluate actual object states."""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import sys
import time
from pathlib import Path

import imageio.v2 as imageio
import mujoco
import numpy as np
from scipy.spatial.transform import Rotation, Slerp

from r4_contract import JOINT_NAMES, read_contract, sha256, write_json
from r4_scene import make_scene
from r4_evaluation import evaluate


def norm_limit(value, limit):
    return value * min(1.0, limit / max(float(np.linalg.norm(value)), 1e-12))


def run(args):
    sensor_config = None
    gpu = None
    if args.policy_config and not (args.sensors and args.prior and args.mission):
        raise ValueError("Online control requires --sensors, --prior and a separate public --mission")
    if args.sensors:
        from r4_cuda import require_cuda
        _, gpu = require_cuda()
        sensor_config = json.loads(args.sensor_config.read_text())["sensor"]
    contract = read_contract(args.reference)  # Heldout is intentionally disabled in this preparation runner.
    task = json.loads(args.evaluation_scene.read_text())
    if task.get("split") not in {"readiness", "debug"} or task.get("geometry_role") != "evaluation_only":
        raise ValueError("Require separate development/readiness evaluation geometry")
    if contract["split"] != task["split"]:
        raise ValueError("Reference/evaluation split mismatch")
    if task.get("task") not in {"lift_hold", "precision_place"}:
        raise ValueError("Unknown task")
    config = json.loads(args.config.read_text())
    physics = config["physics"]
    frames = contract["frames"]
    times = np.array([f["time_s"] for f in frames])
    duration = float(times[-1] - times[0])
    if not 0 < duration <= physics["maximum_episode_seconds"]:
        raise ValueError("Reference exceeds declared episode bound; do not truncate automatically")
    args.output.mkdir(parents=True, exist_ok=False)
    args._created_output = True
    # Instrumented runs keep simulator truth outside the public sensor bundle.
    evaluation_output = args.output / "private-evaluation" if args.sensors else args.output
    if args.sensors:
        evaluation_output.mkdir(mode=0o700)
    manifest = {"status": "running", "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "pid": os.getpid(), "input_kind": contract["kind"], "split": contract["split"],
                "reference_sha256": sha256(args.reference), "evaluation_scene_sha256": sha256(args.evaluation_scene),
                "config_sha256": sha256(args.config), "mujoco": mujoco.__version__,
                "python": sys.version, "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
                "egl_device_id": os.environ.get("MUJOCO_EGL_DEVICE_ID"),
                "source_sha256": {name: sha256(Path(__file__).parent / name) for name in ["run-r4-physical.py", "r4_scene.py", "r4_contract.py", "r4_evaluation.py"]},
                "hand_asset_manifest_sha256": sha256(args.hand_asset / "provenance.json"),
                "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                "execution": "bounded wrist wrench and joint actuators; free object; qpos assigned only at initialization",
                "heldout_used": False}
    if args.sensors:
        manifest.update({"gpu": gpu, "sensor_config_sha256": sha256(args.sensor_config),
                         "object_id": task.get("object_id"), "sensor_seed": sensor_config["seed"],
                         "observation_directory": "public-observations", "evaluation_directory": "private-evaluation",
                         "physics_backend": "MuJoCo CPU rigid-body dynamics; NVIDIA GPU RGB-D rendering",
                         "estimator": "separate CUDA replay process; not run inside simulator"})
        for name in ["r4_sensor_bridge.py", "r4_rgbd.py", "r4_cuda.py"]:
            manifest["source_sha256"][name] = sha256(Path(__file__).parent / name)
    write_json(args.output / "manifest.json", manifest)
    xml = make_scene(args.hand_asset, task, physics, sensor_config=sensor_config)
    (evaluation_output / "scene.xml").write_text(xml)
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    palm = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "palm")
    obj = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "object")
    bridge = observation_writer = rgbd = None
    if args.sensors:
        from r4_sensor_bridge import SensorBridge, ObservationWriter
        from r4_rgbd import RGBDSensor
        bridge = SensorBridge(model, sensor_config)
        observation_writer = ObservationWriter(args.output / "public-observations", bridge, contract["split"])
        rgbd = RGBDSensor(model, obj, sensor_config["seed"])
        from OpenGL import GL
        renderer_name = GL.glGetString(GL.GL_RENDERER).decode()
        vendor = GL.glGetString(GL.GL_VENDOR).decode()
        if "NVIDIA" not in vendor:
            raise RuntimeError(f"P1 collection requires NVIDIA EGL: vendor={vendor}, renderer={renderer_name}")
        manifest["sensor_renderer"] = renderer_name
        write_json(args.output / "manifest.json", manifest)
    finger_joints = np.array([mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n) for n in JOINT_NAMES])
    qadr = model.jnt_qposadr[finger_joints]
    actuator = np.array([mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, n + "_act") for n in JOINT_NAMES])
    if min(finger_joints) < 0 or min(actuator) < 0 or len(actuator) != 16:
        raise ValueError("Hand actuator mapping does not match contract")
    wrist_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "wrist_free")
    wadr = model.jnt_qposadr[wrist_joint]
    data.qpos[wadr:wadr + 7] = frames[0]["wrist_position"] + frames[0]["wrist_quaternion"]
    data.qpos[qadr] = frames[0]["joint_position"]
    data.ctrl[actuator] = frames[0]["joint_position"]
    mujoco.mj_forward(model, data)
    online = None
    if args.policy_config:
        from r4_hand_model import export_hand
        from r4_online_client import OnlineClient
        from r4_public import validate_prior
        mission = json.loads(args.mission.read_text())
        if mission.get("task") != task["task"] or mission.get("object_id") != task.get("object_id", "readiness"):
            raise ValueError("Public task identity does not match evaluation scenario")
        header = {"calibration": bridge.calibration, "prior": validate_prior(json.loads(args.prior.read_text())),
                  "hand": export_hand(model), "estimator": json.loads(args.sensor_config.read_text())["estimator"],
                  "policy": json.loads(args.policy_config.read_text()), "mission": mission,
                  "group": args.controller_group, "probe_strategy": args.probe_strategy}
        online = OnlineClient(header, args.output, timeout=300)
        manifest.update(policy_config_sha256=sha256(args.policy_config), prior_sha256=sha256(args.prior),
                        mission_sha256=sha256(args.mission), controller_group=args.controller_group,
                        probe_strategy=args.probe_strategy, policy_pid=online.process.pid,
                        policy_read_guard_denied_project_data=online.ready["read_guard_denied_project_data"],
                        execution_timing="offline synchronous GPU control; simulation pauses while computing; no realtime claim")
        manifest["estimator"] = "persistent independent CUDA process; public observations only"
        for name in ["r4_online_client.py", "r4_online_worker.py", "r4_memory.py", "r4_hand_model.py", "r4_control.py", "r4_probe.py", "r4_pose_tracker.py", "r4_belief.py", "r4_public.py", "r4_modalities.py", "r4_estimator_worker.py"]:
            manifest["source_sha256"][name] = sha256(Path(__file__).parent/name)
        write_json(args.output/"manifest.json", manifest)
    # All subsequent states come from mj_step. Never assign qpos inside the loop.
    times = times - times[0]
    joint_ref = np.array([f["joint_position"] for f in frames])
    position_ref = np.array([f["wrist_position"] for f in frames])
    rotations = Rotation.from_quat(np.array([f["wrist_quaternion"] for f in frames])[:, [1, 2, 3, 0]])
    rotation_interp = Slerp(times, rotations)
    hand_mass = float(model.body_mass.sum() - model.body_mass[obj])
    renderer = mujoco.Renderer(model, height=480, width=640) if args.render else None
    camera = mujoco.MjvCamera()
    camera.lookat[:] = task.get("camera_lookat", [0, 0, .16])
    camera.distance, camera.azimuth, camera.elevation = .55, 135, -25
    writer = imageio.get_writer(evaluation_output / "actual-execution.mp4", fps=25, codec="libx264", quality=7) if args.render else None
    gl_renderer = None
    if renderer:
        from OpenGL import GL
        gl_renderer = GL.glGetString(GL.GL_RENDERER).decode()
    control_stride = round(1 / physics["control_hz"] / physics["timestep_seconds"])
    video_stride = round(1 / 25 / physics["timestep_seconds"])
    total_steps = round(duration / physics["timestep_seconds"])
    object_geoms = set(np.flatnonzero(model.geom_bodyid == obj).tolist())
    samples, reference_samples, diagnostics, contact_samples, opposition = [], [], [], [], []
    hand_contact_samples = []
    maximum_penetration, max_force, nframes = 0., 0., 0
    finger_contact_steps = 0
    wall_start = time.monotonic()
    velocity = np.zeros(6)
    last_applied_joints = data.ctrl[actuator].copy()
    policy_abort = False
    try:
        for step in range(total_steps + 1):
            # mj_step integrates qpos after computing positions; synchronize recorded poses/contacts.
            mujoco.mj_forward(model, data)
            t = min(float(data.time), duration)
            if step % control_stride == 0:
                target_joints = np.array([np.interp(t, times, joint_ref[:, j]) for j in range(16)])
                target_pos = np.array([np.interp(t, times, position_ref[:, j]) for j in range(3)])
                target_rot = rotation_interp(t)
                if bridge:
                    bridge.sample(data)
                    wrist_observation = np.eye(4)
                    wrist_observation[:3, :3], wrist_observation[:3, 3] = data.xmat[palm].reshape(3, 3), data.xpos[palm]
                    observation = observation_writer.append(data.time, bridge.receive(data.time), data.qpos[qadr], last_applied_joints,
                        rgbd.sample(data) if step % (5*control_stride) == 0 else None, wrist=wrist_observation.tolist())
                    if online:
                        wrist_reference = np.eye(4)
                        wrist_reference[:3, :3], wrist_reference[:3, 3] = target_rot.as_matrix(), target_pos
                        command = online.step(observation, {"joint_position": target_joints.tolist(), "T_world_wrist": wrist_reference.tolist()})
                        policy_abort = command["abort_episode"]
                        target_joints = np.asarray(command["joint_position"])
                        target_transform = np.asarray(command["T_world_wrist"])
                        target_pos, target_rot = target_transform[:3, 3], Rotation.from_matrix(target_transform[:3, :3])
                data.ctrl[actuator] = target_joints
                last_applied_joints = target_joints.copy()
            mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_BODY, palm, velocity, 0)
            force = physics["wrist_position_kp"] * (target_pos - data.xpos[palm]) - physics["wrist_position_kd"] * velocity[3:]
            force += np.array([0, 0, hand_mass * 9.81])
            current_rot = Rotation.from_matrix(data.xmat[palm].reshape(3, 3))
            torque = physics["wrist_rotation_kp"] * (target_rot * current_rot.inv()).as_rotvec() - physics["wrist_rotation_kd"] * velocity[:3]
            data.xfrc_applied[palm, :3] = norm_limit(force, physics["wrist_force_limit_n"])
            data.xfrc_applied[palm, 3:] = norm_limit(torque, physics["wrist_torque_limit_nm"])
            max_force = max(max_force, float(np.linalg.norm(data.xfrc_applied[palm, :3])))
            touching_hand = False
            for contact in data.contact[:data.ncon]:
                g1, g2 = int(contact.geom1), int(contact.geom2)
                if g1 in object_geoms or g2 in object_geoms:
                    maximum_penetration = max(maximum_penetration, -float(contact.dist))
                    other = g2 if g1 in object_geoms else g1
                    if int(model.geom_bodyid[other]) not in {0, obj}:
                        touching_hand = True
            finger_contact_steps += int(touching_hand)
            if step % control_stride == 0:
                samples.append([float(data.time), *data.xpos[obj], *data.xquat[obj], *data.qpos[qadr], *data.xpos[palm], *data.xquat[palm]])
                reference_samples.append([float(data.time), *target_joints, *target_pos, *target_rot.as_quat()[[3, 0, 1, 2]]])
                hand_contact_samples.append(touching_hand)
                diagnostics.append([float(data.time), *data.actuator_force[actuator], *data.xfrc_applied[palm], data.ncon])
                thumb_contact, finger_contact = False, False
                for contact_index, contact in enumerate(data.contact[:data.ncon]):
                    if int(contact.geom1) in object_geoms or int(contact.geom2) in object_geoms:
                        contact_force = np.zeros(6)
                        mujoco.mj_contactForce(model, data, contact_index, contact_force)
                        contact_samples.append([float(data.time), int(contact.geom1), int(contact.geom2), float(contact.dist), *contact_force])
                        other = int(contact.geom2) if int(contact.geom1) in object_geoms else int(contact.geom1)
                        body_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, int(model.geom_bodyid[other])) or ""
                        if contact_force[0] > .05:
                            thumb_contact |= body_name.startswith("th_")
                            finger_contact |= body_name.startswith(("if_", "mf_", "rf_"))
                opposition.append(thumb_contact and finger_contact)
            if writer and step % video_stride == 0:
                renderer.update_scene(data, camera=camera)
                writer.append_data(renderer.render())
                nframes += 1
            if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
                raise RuntimeError("Nonfinite physical state")
            if policy_abort:
                break
            if step < total_steps:
                mujoco.mj_step(model, data)
    finally:
        if online:
            online.close()
        if observation_writer:
            observation_writer.close()
        if rgbd:
            rgbd.close()
        if writer:
            writer.close()
        if renderer:
            renderer.close()
    actual = np.asarray(samples)
    reference = np.asarray(reference_samples)
    np.savez_compressed(evaluation_output / "actual-state.npz", samples=actual, reference=reference,
                        actuator_diagnostics=np.asarray(diagnostics), contacts=np.asarray(contact_samples).reshape(-1, 10),
                        opposing_contacts=np.asarray(opposition), touching_hand=np.asarray(hand_contact_samples))
    write_json(evaluation_output / "geom-names.json", {str(i): mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, i) for i in range(model.ngeom)})
    np.savetxt(evaluation_output / "actual-state.csv", actual, delimiter=",", header=",".join(["time_s", "object_x", "object_y", "object_z", "object_qw", "object_qx", "object_qy", "object_qz", *JOINT_NAMES, "wrist_x", "wrist_y", "wrist_z", "wrist_qw", "wrist_qx", "wrist_qy", "wrist_qz"]), comments="")
    task_pass, task_metrics = evaluate(actual, opposition, hand_contact_samples, task, config, maximum_penetration)
    task_pass = task_pass and not policy_abort
    if policy_abort:
        task_metrics["penalized_position_error_m"] = .1
    result = {"execution_status": "passed", "task_status": "passed" if task_pass else "failed", "input_kind": contract["kind"],
              "is_research_result": False, "split": contract["split"], "steps": step, "requested_steps": total_steps, "control_samples": len(actual),
              "duration_seconds": float(data.time), "wall_seconds": time.monotonic() - wall_start,
              "policy_abort": policy_abort, "requested_duration_seconds": duration,
              "policy_summary": command["diagnostic"] if online else None,
              "metrics": {**task_metrics,
                          "hand_contact_steps": finger_contact_steps, "maximum_wrist_force_n": max_force,
                          "joint_tracking_rmse_rad": float(np.sqrt(np.mean((actual[:, 8:24] - reference[:, 1:17]) ** 2)))},
              "video": {"frames": nframes, "renderer": gl_renderer, "file": "actual-execution.mp4" if nframes else None},
              "artifacts_sha256": {p.name: sha256(p) for p in evaluation_output.iterdir() if p.is_file() and p.name != "manifest.json"}}
    write_json(evaluation_output / "result.json", result)
    manifest["status"] = "complete"
    manifest["task_status"] = result["task_status"]
    if args.sensors:
        manifest["public_artifacts_sha256"] = {name: sha256(args.output / "public-observations" / name)
                                               for name in ["calibration.json", "observations.jsonl"]}
        manifest["actual_state_sha256"] = sha256(evaluation_output / "actual-state.npz")
        manifest["pending_sensor_samples_at_stop"] = len(bridge.pending)
    write_json(args.output / "manifest.json", manifest)
    (args.output / "REPORT.md").write_text(f"# R4 physical preparation\n\nExecution: passed. Task: {result['task_status']}. Input: {contract['kind']}.\n\nActual state, reference, contact and target errors are in result.json/actual-state.npz. This is development evidence; no held-out claim.\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--evaluation-scene", type=Path, required=True)
    parser.add_argument("--hand-asset", type=Path, default=Path(os.environ.get("R4_DATA_ROOT", "../humanmimic-data/r4")) / "assets/leap_hand")
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[1] / "configs/r4-stage1.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--sensors", action="store_true", help="Opt-in P1 public sensor stream plus separate private truth; requires CUDA/NVIDIA EGL")
    parser.add_argument("--sensor-config", type=Path, default=Path(__file__).resolve().parents[1] / "configs/r4-p1p2.json")
    parser.add_argument("--policy-config", type=Path)
    parser.add_argument("--prior", type=Path)
    parser.add_argument("--mission", type=Path)
    parser.add_argument("--controller-group", choices=["G0F0", "G1F0", "G0F1", "G1F1"], default="G1F1")
    parser.add_argument("--probe-strategy", choices=["no_probe", "random", "uniform", "global_uncertainty", "task_risk_reduction"], default="no_probe")
    args = parser.parse_args()
    try:
        print(json.dumps(run(args), indent=2))
    except Exception as exc:
        if getattr(args, "_created_output", False):
            write_json(args.output / "failure.json", {"status": "failed", "error": str(exc), "type": type(exc).__name__})
            manifest_path = args.output / "manifest.json"
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text())
                manifest["status"] = "failed"
                write_json(manifest_path, manifest)
        raise
