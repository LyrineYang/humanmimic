"""Run the official SONIC controller against MuJoCo and retain physical evidence.

No qpos/qvel values are assigned during physical execution. Rendering is a
separate replay of the recorded actual states after the controller has stopped.
"""

import argparse
import csv
import hashlib
import json
import os
import pickle
from pathlib import Path
import pty
import select
import signal
import shutil
import socket
import subprocess
import sys
import time
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "vendor/GR00T-WholeBodyControl"


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def run_paced_simulation(sim):
    """Preserve official updates while preventing cumulative sleep overshoot."""
    sim_cnt = 0
    redis_stamp = time.time()
    deadline = time.monotonic()
    while sim._running and (sim.sim_env.viewer is None or sim.sim_env.viewer.is_running()):
        sim.sim_env.sim_step()
        now = time.time()
        if now - redis_stamp > .1 and sim.redis_client is not None:
            head_pose = sim.sim_env.get_head_pose()
            sim.redis_client.set("head_pos", pickle.dumps(head_pose[:3]))
            sim.redis_client.set("head_quat", pickle.dumps(head_pose[3:]))
            redis_stamp = now
        if sim_cnt % int(sim.viewer_dt / sim.sim_dt) == 0:
            sim.sim_env.update_viewer()
        if sim_cnt % int(sim.reward_dt / sim.sim_dt) == 0:
            sim.sim_env.update_reward()
        if sim_cnt % int(sim.image_dt / sim.sim_dt) == 0:
            sim.sim_env.update_render_caches()
        deadline += sim.sim_dt
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
        elif remaining < -1.0:
            raise RuntimeError("Simulation pacing fell over one second behind wall time")
        sim_cnt += 1


def sim_worker(output):
    from gear_sonic.utils.mujoco_sim.configs import SimLoopConfig
    from gear_sonic.utils.mujoco_sim.base_sim import BaseSimulator
    import mujoco
    import unitree_sdk2py.core.channel as sdk_channel

    sdk_channel.ChannelConfigHasInterface = (output / "dds.xml").read_text()

    cfg = SimLoopConfig(interface="sim", enable_onscreen=False, enable_offscreen=False)
    config = cfg.load_wbc_yaml()
    assert config["INTERFACE"] == "lo" and config["DOMAIN_ID"] == 0
    sim = BaseSimulator(config, onscreen=False, offscreen=False)
    env = sim.sim_env
    model, data = env.mj_model, env.mj_data
    assert any(model.jnt_type == mujoco.mjtJoint.mjJNT_FREE)
    assert model.opt.gravity[2] < 0 and env.elastic_band.enable
    body_names = [model.joint(int(i)).name for i in env.body_joint_index]
    addresses = model.jnt_qposadr[env.body_joint_index]
    write_json(output / "simulation-config.json", {
        "wbc_config": config, "body_joint_names": body_names,
        "qpos_addresses": addresses.tolist(), "nq": model.nq, "nv": model.nv,
        "free_root": True, "gravity": model.opt.gravity.tolist(),
        "state_assignment_during_execution": False,
        "auto_reset_disabled": True,
        "pacing": "Absolute monotonic deadline; official sim_step and auxiliary updates retained",
    })
    rows = []
    original_step = env.sim_step
    started = time.monotonic()

    def check_fall_without_reset():
        env.fall = bool(data.qpos[2] < 0.2)
        if env.fall:
            write_json(output / "fall.json", {"monotonic": time.monotonic(),
                       "sim_time": data.time, "height": float(data.qpos[2])})
            sim._running = False

    # Preserve failed states. The official default silently resets after a fall.
    env.check_fall = check_fall_without_reset

    def step_and_record():
        if (output / "release.flag").exists() and env.elastic_band.enable:
            env.handle_keyboard_button("9")
            assert not env.elastic_band.enable
            write_json(output / "released.json", {"monotonic": time.monotonic(),
                       "sim_time": data.time})
        original_step()
        nonfoot_contact = False
        for contact in data.contact[:data.ncon]:
            b1 = int(model.geom_bodyid[contact.geom1])
            b2 = int(model.geom_bodyid[contact.geom2])
            if (b1 == 0) != (b2 == 0):
                name = model.body(b2 if b1 == 0 else b1).name
                if "ankle" not in name and "foot" not in name:
                    nonfoot_contact = True
        rows.append((time.monotonic(), float(data.time), data.qpos.copy(),
                     data.qvel.copy(), data.ctrl.copy(), data.qpos[addresses].copy(),
                     float(data.xmat[env.root_body_id][8]),
                     bool(env.elastic_band.enable), bool(sim.unitree_bridge.low_cmd_received),
                     nonfoot_contact))
        if (output / "stop.flag").exists() or time.monotonic() - started > 600:
            sim._running = False

    env.sim_step = step_and_record
    signal.signal(signal.SIGTERM, lambda *_: setattr(sim, "_running", False))
    write_json(output / "sim-ready.json", {"monotonic": time.monotonic()})
    try:
        # Do not let an unpowered robot collapse while TensorRT engines load.
        # The initial MJCF state is left untouched; physics starts once the
        # controller has installed its motor-command writer and control thread.
        while not (output / "simulation-start.flag").exists():
            if (output / "stop.flag").exists() or time.monotonic() - started > 360:
                return
            time.sleep(.02)
        run_paced_simulation(sim)
    finally:
        if rows:
            names = ["monotonic", "sim_time", "qpos", "qvel", "ctrl", "body_q",
                     "root_up_cosine", "elastic_band", "dds_command_received", "nonfoot_floor_contact"]
            np.savez_compressed(output / "actual-state.npz", **{
                name: np.asarray([row[i] for row in rows]) for i, name in enumerate(names)})
        sim.close()


def stop_process(process, timeout=10):
    if process is None or process.poll() is not None:
        return
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def longest_duration(mask, times):
    maximum = 0.0
    start = None
    for flag, stamp in zip(mask, times):
        if flag and start is None:
            start = stamp
        elif not flag:
            start = None
        if start is not None:
            maximum = max(maximum, float(stamp - start))
    return maximum


def evaluate(output, packets, events, config, complete, failure, preflight):
    actual = np.load(output / "actual-state.npz")
    playing_file = output / "controller-csv/motion_playing.csv"
    playing = set()
    if playing_file.exists():
        with playing_file.open() as f:
            for row in csv.DictReader(f):
                if float(list(row.values())[-1]) > 0.5:
                    playing.add(int(row["index"]))
    selected = [p for p in packets if int(p["payload"]["index"]) in playing]
    if not selected:
        raise RuntimeError("No control samples matched the controller's motion_playing log")
    stamps = np.array([p["receive_monotonic"] for p in selected])
    measured = np.array([p["payload"]["body_q_measured"] for p in selected])
    target = np.array([p["payload"]["body_q_target"] for p in selected])
    difference = np.arctan2(np.sin(measured - target), np.cos(measured - target))
    rmse = float(np.sqrt(np.mean(difference ** 2)))
    physical_mask = (actual["monotonic"] >= stamps[0] - .02) & (actual["monotonic"] <= stamps[-1] + .02)
    physical_times = actual["monotonic"][physical_mask]
    assert physical_mask.any()
    band_off = bool(not actual["elastic_band"][physical_mask].any())
    height = actual["qpos"][physical_mask, 2]
    tilted = actual["root_up_cosine"][physical_mask] < np.cos(np.deg2rad(config["fall_tilt_degrees"]))
    tilt_seconds = longest_duration(tilted, physical_times)
    contact_seconds = longest_duration(actual["nonfoot_floor_contact"][physical_mask], physical_times)
    fell = bool((output / "fall.json").exists() or height.min() < config["fall_root_height_m"]
                or tilt_seconds >= config["fall_tilt_duration_s"]
                or contact_seconds >= config["nonfoot_contact_duration_s"])
    finite = bool(np.isfinite(measured).all() and np.isfinite(target).all()
                  and np.isfinite(actual["qpos"]).all())
    commands_received = bool(actual["dds_command_received"][physical_mask].all())
    nonzero_torques = bool(np.max(np.abs(actual["ctrl"][physical_mask])) > 1e-6)
    enough_preflight = not preflight or stamps[-1] - stamps[0] >= 9.5
    np.savez_compressed(output / "aligned-tracking.npz", receive_monotonic=stamps,
                        measured_joint_position=measured, reference_joint_position=target,
                        angular_error=difference,
                        controller_index=np.array([p["payload"]["index"] for p in selected]))
    metrics = {
        "status": "passed" if (complete or preflight) and not failure and not fell and finite
                  and band_off and commands_received and nonzero_torques and enough_preflight
                  and rmse <= config["joint_rmse_max_rad"] else "failed",
        "scope": "10-second preflight" if preflight else "one complete motion reproduction",
        "motion": config["motion_name"], "motion_completed": complete,
        "joint_rmse_rad": rmse, "joint_rmse_limit_rad": config["joint_rmse_max_rad"],
        "per_joint_rmse_rad": np.sqrt(np.mean(difference ** 2, axis=0)).tolist(),
        "tracking_samples": len(selected), "motion_playing_csv_samples": len(playing),
        "motion_wall_seconds_observed": float(stamps[-1] - stamps[0]),
        "expected_motion_seconds": config["reference_frames"] / config["control_hz"],
        "controller_output_index_gaps": int(np.sum(np.maximum(0, np.diff([p["payload"]["index"] for p in selected]) - 1))),
        "fell": fell, "minimum_root_height_m": float(height.min()),
        "longest_excess_tilt_seconds": tilt_seconds, "longest_nonfoot_floor_contact_seconds": contact_seconds,
        "elastic_band_off_during_playback": band_off, "finite_states": finite,
        "dds_commands_received": commands_received, "nonzero_control_torques": nonzero_torques,
        "free_root_gravity_contact_controller": True, "actual_state_overwrites": False,
        "failure": failure, "events": events, "cloud_cost_usd": 0,
        "R1_five_motion_acceptance": "awaiting_verification",
        "alignment": "Measured joints and reference from the same official controller output tick; no fitted time shift.",
    }
    write_json(output / "metrics.json", metrics)
    return metrics, (float(stamps[0]), float(stamps[-1]))


def render_actual_video(output, window):
    import mujoco
    import cv2
    data_log = np.load(output / "actual-state.npz")
    config = json.loads((output / "simulation-config.json").read_text())
    model = mujoco.MjModel.from_xml_path(str(UPSTREAM / config["wbc_config"]["ROBOT_SCENE"]))
    data = mujoco.MjData(model)
    camera = mujoco.MjvCamera()
    camera.distance, camera.azimuth, camera.elevation = 2.7, 135, -15
    fps, width, height = 25, 640, 360
    args = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
            "-r", str(fps), "-i", "pipe:0", "-an", "-c:v", "libx264", "-preset", "fast",
            "-crf", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output / "actual-execution.mp4")]
    with (output / "video-encode.log").open("w") as log:
        encoder = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=log, stderr=log)
        try:
            with mujoco.Renderer(model, height=height, width=width) as renderer:
                for stamp in np.arange(window[0], window[1] + 1 / fps, 1 / fps):
                    i = min(int(np.searchsorted(data_log["monotonic"], stamp)), len(data_log["qpos"]) - 1)
                    # This assignment is visualization only, after physical execution ends.
                    data.qpos[:] = data_log["qpos"][i]
                    mujoco.mj_forward(model, data)
                    camera.lookat[:] = [data.qpos[0], data.qpos[1], 0.65]
                    renderer.update_scene(data, camera=camera)
                    frame = renderer.render().copy()
                    cv2.putText(frame, "SONIC: recorded actual MuJoCo states", (12, 24),
                                cv2.FONT_HERSHEY_SIMPLEX, .55, (255, 255, 255), 1)
                    cv2.putText(frame, f"Playback {stamp - window[0]:.2f}s | sim {data_log['sim_time'][i]:.2f}s", (12, 47),
                                cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
                    if stamp == window[0]:
                        cv2.imwrite(str(output / "preview.png"), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                    encoder.stdin.write(frame.tobytes())
        finally:
            encoder.stdin.close()
            code = encoder.wait(timeout=30)
            if code:
                raise RuntimeError(f"FFmpeg exit {code}")


def run(args):
    import zmq
    import msgpack
    evaluation = args.evaluation.resolve()
    config = json.loads(evaluation.read_text())
    reference = UPSTREAM / "gear_sonic_deploy/reference/example" / config["motion_name"]
    reference_csv = reference / "joint_pos.csv"
    if hashlib.sha256(reference_csv.read_bytes()).hexdigest() != config["reference_csv_sha256"]:
        raise ValueError("Reference CSV does not match the frozen evaluation configuration")
    reference_values = np.loadtxt(reference_csv, delimiter=",", skiprows=1)
    if reference_values.shape != (config["reference_frames"], config["effective_joint_count"]):
        raise ValueError("Reference frame/joint count does not match the frozen configuration")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    motions = output / "motion-input"
    motions.mkdir()
    (motions / config["motion_name"]).symlink_to(reference, target_is_directory=True)
    config["run_mode"] = "preflight" if args.preflight else "full"
    config["simulation_pacing"] = "absolute monotonic deadlines at the original 200 Hz"
    config["video_requested"] = not args.no_video
    config["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    config["evaluation_sha256"] = hashlib.sha256(evaluation.read_bytes()).hexdigest()
    config["dds_xml_sha256"] = hashlib.sha256((ROOT / "configs/r1-dds.xml").read_bytes()).hexdigest()
    config["upstream_commit"] = subprocess.check_output(["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"], text=True).strip()
    patch = subprocess.check_output(["git", "-C", str(UPSTREAM), "diff", "--binary"])
    (output / "upstream.patch").write_bytes(patch)
    config["upstream_patch_sha256"] = hashlib.sha256(patch).hexdigest()
    config["binary_sha256"] = hashlib.sha256((UPSTREAM / "gear_sonic_deploy/target/release/g1_deploy_onnx_ref").read_bytes()).hexdigest()
    shutil.copy2(Path(__file__), output / "run-script-snapshot.py")
    shutil.copy2(ROOT / "configs/r1-dds.xml", output / "dds.xml")
    write_json(output / "dds-sdk.json", {"DomainId": 0, "Config": (output / "dds.xml").read_text()})
    config["model_hashes"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (ROOT / "models/sonic-default/policy/release").iterdir() if p.is_file()}
    write_json(output / "run-config.json", config)
    with socket.socket() as port_socket:
        port_socket.bind(("127.0.0.1", 0))
        port = port_socket.getsockname()[1]
    context = zmq.Context()
    subscriber = context.socket(zmq.SUB)
    subscriber.setsockopt(zmq.SUBSCRIBE, b"g1_debug")
    subscriber.setsockopt(zmq.RCVHWM, 10000)
    subscriber.connect(f"tcp://127.0.0.1:{port}")
    sim = controller = None
    master = slave = None
    events, packets = [], []
    complete, failure = False, None
    transcript = ""
    started = time.monotonic()
    started_control = first_output = released = played = physics_started = None
    model_root = ROOT / "models/sonic-default/policy/release"
    binary = UPSTREAM / "gear_sonic_deploy/target/release/g1_deploy_onnx_ref"
    controller_args = [str(binary), "lo", str(model_root / "model_decoder.onnx"), str(motions),
                       "--obs-config", str(model_root / "observation_config.yaml"),
                       "--encoder-file", str(model_root / "model_encoder.onnx"),
                       "--input-type", "keyboard", "--output-type", "zmq", "--disable-crc-check",
                       "--zmq-out-port", str(port), "--enable-csv-logs", "--logs-dir", str(output / "controller-csv"),
                       "--target-motion-logfile", str(output / "controller-reference.csv")]
    write_json(output / "commands.json", {"controller": controller_args,
               "sim": [sys.executable, str(Path(__file__).resolve()), "--sim-worker", "--output", str(output)]})
    try:
        with (output / "simulator.log").open("w") as sim_log, (output / "controller.log").open("w") as ctl_log, \
                (output / "controller-output.jsonl").open("w") as packet_log:
            sim = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--sim-worker", "--output", str(output)],
                                   stdout=sim_log, stderr=subprocess.STDOUT, start_new_session=True)
            while not (output / "sim-ready.json").exists():
                if sim.poll() is not None or time.monotonic() - started > 30:
                    raise RuntimeError("Simulator did not initialize; inspect simulator.log")
                time.sleep(.05)
            master, slave = pty.openpty()
            controller = subprocess.Popen(controller_args, stdin=slave, stdout=slave, stderr=slave,
                                          cwd=UPSTREAM / "gear_sonic_deploy", start_new_session=True,
                                          env={**os.environ, "R1_DDS_CONFIG_FILE": str(output / "dds-sdk.json")})
            os.close(slave)
            slave = None
            while True:
                now = time.monotonic()
                if now - started > 360:
                    failure = "Configured 360-second run timeout"
                    break
                if select.select([master], [], [], .005)[0]:
                    try:
                        chunk = os.read(master, 65536).decode(errors="replace")
                    except OSError:
                        chunk = ""
                    transcript += chunk
                    ctl_log.write(chunk)
                    ctl_log.flush()
                if "G1Deploy object created successfully!" in transcript and physics_started is None:
                    (output / "simulation-start.flag").touch()
                    physics_started = now
                    events.append({"name": "physics_started_after_controller_ready", "monotonic": now})
                if "Init Done" in transcript and started_control is None:
                    os.write(master, b"]")
                    started_control = now
                    events.append({"name": "start_control_key", "monotonic": now})
                while subscriber.poll(0):
                    packet = subscriber.recv()
                    payload = msgpack.unpackb(packet[len(b"g1_debug"):], raw=False)
                    item = {"receive_monotonic": time.monotonic(), "payload": payload}
                    packets.append(item)
                    packet_log.write(json.dumps(item) + "\n")
                    if first_output is None:
                        first_output = now
                if first_output is not None and released is None:
                    (output / "release.flag").touch()
                    released = now
                    events.append({"name": "release_immediately_after_policy_start", "monotonic": now})
                if first_output is not None and played is None and now - first_output > .2 and (output / "released.json").exists():
                    os.write(master, b"T")
                    played = now
                    events.append({"name": "play_requested", "monotonic": now})
                if f": {config['motion_name']} completed." in transcript:
                    complete = True
                    break
                if args.preflight and played is not None and now - played >= 10:
                    break
                if (output / "fall.json").exists():
                    failure = "Simulator recorded a fall without auto-reset"
                    break
                if controller.poll() is not None or sim.poll() is not None:
                    failure = "Controller or simulator exited before completion"
                    break
                if "[ERROR]" in transcript or "Stopping control system." in transcript:
                    failure = "Official controller reported an error"
                    break
    except Exception:
        failure = traceback.format_exc()
    finally:
        if master is not None:
            try:
                os.write(master, b"O")
            except OSError:
                pass
        (output / "stop.flag").touch()
        stop_process(controller)
        stop_process(sim)
        if master is not None:
            os.close(master)
        subscriber.close(linger=0)
        context.term()
        write_json(output / "run-events.json", {"events": events, "complete": complete,
                   "failure": failure, "controller_exit": controller.returncode if controller else None,
                   "simulator_exit": sim.returncode if sim else None})
    if (output / "actual-state.npz").exists() and packets:
        try:
            metrics, window = evaluate(output, packets, events, config, complete, failure, args.preflight)
            if args.no_video:
                metrics["scope"] = "Diagnostic physical execution only; video omitted; not suite acceptance"
                write_json(output / "metrics.json", metrics)
            if not args.preflight and not args.no_video:
                render_actual_video(output, window)
        except Exception:
            error = traceback.format_exc()
            write_json(output / "artifact-error.json", {"status": "failed", "error": error})
            if not (output / "metrics.json").exists():
                write_json(output / "metrics.json", {"status": "failed", "failure": failure or error,
                           "motion_completed": complete, "controller_packets": len(packets),
                           "joint_rmse_rad": None, "reason": "No evaluable playback samples"})
            print(error)
            return 1
        print(json.dumps(metrics, indent=2))
        return 0 if metrics["status"] == "passed" else 1
    write_json(output / "metrics.json", {"status": "failed", "failure": failure,
               "motion_completed": complete, "controller_packets": len(packets)})
    print(failure)
    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evaluation", type=Path, default=ROOT / "configs/r1-evaluation.json",
                        help="Frozen per-motion evaluation JSON; defaults to the original Macarena baseline")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--no-video", action="store_true", help="Diagnostic only; omit video, so this run cannot satisfy suite acceptance")
    parser.add_argument("--sim-worker", action="store_true", help=argparse.SUPPRESS)
    parsed = parser.parse_args()
    if parsed.sim_worker:
        sim_worker(parsed.output.resolve())
    else:
        raise SystemExit(run(parsed))
