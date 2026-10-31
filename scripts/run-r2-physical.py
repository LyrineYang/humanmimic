"""Replay a cached SMPL video through SONIC Protocol v3 and actual MuJoCo physics.

Run in humanoid-r1. Extraction stays in humanoid-r2. The original simulator,
absolute 200 Hz pacing, policy, gains and no-reset recording are reused.
"""

import argparse
import csv
import importlib.util
import json
import os
from pathlib import Path
import pty
import select
import shutil
import socket
import subprocess
import sys
import time
import traceback

import numpy as np
import zmq
import msgpack

from r2_common import PROJECT, SONIC, STORAGE, sha256, storage_check, write_json

spec = importlib.util.spec_from_file_location("r1_reproduction", PROJECT / "scripts/run-r1-reproduction.py")
r1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r1)


def pack_chunk(fields):
    descriptions, body = [], []
    for name, value in fields.items():
        value = np.ascontiguousarray(value)
        descriptions.append({"name": name, "dtype": "i64" if value.dtype == np.int64 else "f32", "shape": list(value.shape)})
        body.append(value.tobytes())
    # Match SONIC's pack_pose_message: count is 1 even for a multi-frame chunk;
    # each field's leading dimension carries the number of motion samples.
    header = json.dumps({"v": 3, "endian": "le", "count": 1, "fields": descriptions}, separators=(",", ":")).encode()
    if len(header) > 1280:
        raise ValueError("Protocol header overflow")
    return b"pose" + header.ljust(1280, b"\x00") + b"".join(body)


def read_rows(path):
    if not path.exists():
        return []
    with path.open() as stream:
        return list(csv.DictReader(stream))


def last_input_frame(path):
    if not path.exists():
        return None
    with path.open("rb") as stream:
        stream.seek(max(0, path.stat().st_size - 4096))
        text = stream.read().decode(errors="replace")
    lines = text.splitlines()
    if not text.endswith("\n"):
        lines = lines[:-1]
    for line in reversed(lines):
        cells = line.split(",")
        if len(cells) >= 16:
            try:
                return int(cells[1])
            except ValueError:
                pass
    return None


def reference_clock(extraction, physical):
    spec = importlib.util.spec_from_file_location("r2_body_clock", PROJECT / "scripts/evaluate-r2-body.py")
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    audit, stamps, source_times, _ = evaluator.timing_audit(extraction, physical)
    write_json(physical / "reference-clock-audit.json", audit)
    return audit, stamps, source_times


def render_measured_video(physical, reference, control_stamps, source_times):
    """Replay actual states on the source grid using verified consumption ticks."""
    import cv2
    import mujoco
    actual = np.load(physical / "actual-state.npz")
    configuration = json.loads((physical / "simulation-config.json").read_text())
    conversion = json.loads((reference.parent / "conversion.json").read_text())
    model = mujoco.MjModel.from_xml_path(str(SONIC / configuration["wbc_config"]["ROBOT_SCENE"]))
    data = mujoco.MjData(model)
    camera = mujoco.MjvCamera()
    camera.distance, camera.azimuth, camera.elevation = 2.7, 135, -15
    fps, width, height = 25, 640, 360
    frame_times = np.arange(int(np.ceil(conversion["source_duration_seconds"] * fps))) / fps
    frame_times = frame_times[frame_times <= source_times[-1] + 1e-8]
    # Interpolate the recorded reference clock, never an error-minimizing shift.
    queries = np.interp(frame_times, source_times, control_stamps)
    right = np.clip(np.searchsorted(actual["monotonic"], queries), 0, len(actual["monotonic"]) - 1)
    left = np.maximum(right - 1, 0)
    indices = np.where(abs(actual["monotonic"][left] - queries) <= abs(actual["monotonic"][right] - queries), left, right)
    gaps = abs(actual["monotonic"][indices] - queries)
    valid = (queries >= actual["monotonic"][0]) & (queries <= actual["monotonic"][-1]) & (gaps <= .015)
    video = physical / "actual-execution.mp4"
    if video.exists():
        raise ValueError("Preserve existing actual-state video before re-rendering")
    command = ["ffmpeg", "-hide_banner", "-loglevel", "warning", "-nostdin", "-n", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0", "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(video)]
    with (physical / "video-encode.log").open("x") as log:
        encoder = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=log, stderr=log)
        try:
            with mujoco.Renderer(model, height=height, width=width) as renderer:
                for number, (source_t, index, covered) in enumerate(zip(frame_times, indices, valid)):
                    if covered:
                        data.qpos[:] = actual["qpos"][index]  # Offline replay after control stopped.
                        mujoco.mj_forward(model, data)
                        camera.lookat[:] = [data.qpos[0], data.qpos[1], .65]
                        renderer.update_scene(data, camera=camera)
                        frame = cv2.cvtColor(renderer.render(), cv2.COLOR_RGB2BGR)
                    else:
                        frame = np.zeros((height, width, 3), np.uint8)
                        cv2.putText(frame, "NO RECORDED ACTUAL STATE", (20, 180), cv2.FONT_HERSHEY_SIMPLEX, .65, (255, 255, 255), 1)
                    cv2.putText(frame, "SONIC: recorded actual MuJoCo states", (12, 24), cv2.FONT_HERSHEY_SIMPLEX, .55, (255, 255, 255), 1)
                    cv2.putText(frame, f"Source {source_t:.2f}s | sim {actual['sim_time'][index]:.2f}s", (12, 47), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
                    if number == 0:
                        cv2.imwrite(str(physical / "preview.png"), frame)
                    encoder.stdin.write(frame.tobytes())
        finally:
            encoder.stdin.close()
            code = encoder.wait(timeout=30)
            if code:
                raise RuntimeError("Actual-state video encoding failed")
    write_json(physical / "actual-render-mapping.json", {"status": "passed" if valid.all() else "failed", "scope": "Offline actual-state replay on source time; no new physical execution", "renderer_script_sha256": sha256(__file__), "physical_execution_script_sha256": json.loads((physical / "execution-manifest.json").read_text())["r2_script_sha256"], "fps": fps, "frames": len(frame_times), "source_times_seconds": frame_times.tolist(), "native_control_monotonic": queries.tolist(), "recorded_actual_state_indices": indices.tolist(), "nearest_sample_gaps_seconds": gaps.tolist(), "valid_actual_state": valid.tolist(), "source_zero_monotonic": float(control_stamps[0]), "time_shift_fitted": False, "actual_state_sha256": sha256(physical / "actual-state.npz")})


def run(args):
    storage_check(args.output)
    for p in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            command = p.read_bytes().split(b"\x00")[0].decode()
        except (OSError, UnicodeError):
            continue
        if Path(command).name == "g1_deploy_onnx_ref":
            raise RuntimeError(f"Existing SONIC controller is active: {p.parent.name}")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    reference = np.load(args.reference)
    count = len(reference["timestamps"])
    warmup, future = 50, 51
    fields = {}
    for name in ("smpl_joints", "smpl_pose", "joint_pos", "joint_vel", "body_quat"):
        values = np.asarray(reference[name], dtype=np.float32)
        fields[name] = np.concatenate((np.repeat(values[:1], warmup, axis=0), values, np.repeat(values[-1:], future, axis=0)))
    fields["frame_index"] = np.arange(count + warmup + future, dtype=np.int64)
    wire = pack_chunk(fields)
    (output / "reference-wire.bin").write_bytes(wire)
    shutil.copy2(args.reference, output / "source-reference.npz")
    shutil.copy2(PROJECT / "configs/r1-dds.xml", output / "dds.xml")
    write_json(output / "dds-sdk.json", {"DomainId": 0, "Config": (output / "dds.xml").read_text()})
    (output / "reference").mkdir()
    for name in ("config", "configs"):
        target = SONIC / "gear_sonic_deploy" / name
        if target.exists():
            (output / name).symlink_to(target, target_is_directory=True)
    motions = output / "motion-input"
    motions.mkdir()
    (motions / "macarena_001__A545").symlink_to(SONIC / "gear_sonic_deploy/reference/example/macarena_001__A545", target_is_directory=True)
    context = zmq.Context()
    publisher = context.socket(zmq.PUB)
    publisher.bind("tcp://127.0.0.1:*")
    pose_port = int(publisher.getsockopt_string(zmq.LAST_ENDPOINT).rsplit(":", 1)[1])
    with socket.socket() as free:
        free.bind(("127.0.0.1", 0))
        debug_port = free.getsockname()[1]
    subscriber = context.socket(zmq.SUB)
    subscriber.setsockopt(zmq.SUBSCRIBE, b"g1_debug")
    subscriber.setsockopt(zmq.RCVHWM, 10000)
    subscriber.connect(f"tcp://127.0.0.1:{debug_port}")
    original_models = PROJECT / "models/sonic-default/policy/release"
    model = STORAGE / "models/sonic-default/policy/release"
    model.mkdir(parents=True, exist_ok=True)
    required = ("model_decoder.onnx", "model_encoder.onnx", "observation_config.yaml")
    model_hashes = {}
    for name in required:
        expected = sha256(original_models / name)
        target = model / name
        if not target.exists():
            shutil.copy2(original_models / name, target)
        if sha256(target) != expected:
            raise ValueError(f"D-cached SONIC weights differ from the passed R1 release: {name}")
        model_hashes[name] = expected
    # Keep any existing TensorRT caches, but ensure all new native caches are
    # created beside the D copy rather than changing the preserved R1 assets.
    for original in original_models.iterdir():
        if original.is_file() and original.name not in required and not (model / original.name).exists():
            shutil.copy2(original, model / original.name)
    binary = SONIC / "gear_sonic_deploy/target/release/g1_deploy_onnx_ref"
    command = [str(binary), "lo", str(model / "model_decoder.onnx"), str(motions), "--obs-config", str(model / "observation_config.yaml"), "--encoder-file", str(model / "model_encoder.onnx"), "--input-type", "zmq", "--zmq-host", "localhost", "--zmq-port", str(pose_port), "--output-type", "zmq", "--zmq-out-port", str(debug_port), "--disable-crc-check", "--enable-csv-logs", "--logs-dir", str(output / "controller-csv"), "--record-input-file", str(output / "controller-input.csv"), "--enable-motion-recording", "--target-motion-logfile", str(output / "controller-reference.csv")]
    identity = {"status": "awaiting_verification", "expectation": "Consume every complete source sample through the released SMPL encoder, no falls/state overwrites; warmup and future context are recorded separately", "reference_sha256": sha256(args.reference), "source_frames_50hz": count, "warmup_frames": warmup, "future_context_padding_frames": future, "simulator_startup_timeout_seconds": args.simulator_startup_timeout, "controller": command, "controller_cwd": str(output), "model_root": str(model), "immutable_model_hashes_equal_r1": model_hashes, "binary_sha256": sha256(binary), "r1_simulator_sha256": sha256(PROJECT / "scripts/run-r1-reproduction.py"), "r2_script_sha256": sha256(__file__), "gpu": subprocess.check_output(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"], text=True).strip(), "wire_sha256": sha256(output / "reference-wire.bin"), "timing": "full offline cache sent as Protocol-v3 chunk; native controller clock consumes 50Hz, no sender clock fit", "source_content_trimmed": False, "cloud_cost_usd": 0}
    write_json(output / "execution-manifest.json", identity)
    started = time.monotonic()
    sim = controller = None
    master = None
    events, packets = [], []
    transcript = ""
    enabled = policy_started = released = None
    sends = 0
    last_send = 0
    complete, failure = False, None
    try:
        with (output / "simulator.log").open("w") as sim_log, (output / "controller.log").open("w") as ctl_log, (output / "controller-output.jsonl").open("w") as data_log:
            sim = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--output", str(output), "--sim-worker"], stdout=sim_log, stderr=subprocess.STDOUT, start_new_session=True)
            while not (output / "sim-ready.json").exists():
                if sim.poll() is not None or time.monotonic() - started > args.simulator_startup_timeout:
                    raise RuntimeError("Simulator initialization failed; inspect simulator.log")
                time.sleep(0.05)
            master, slave = pty.openpty()
            controller = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave, cwd=output, start_new_session=True, env={**os.environ, "R1_DDS_CONFIG_FILE": str(output / "dds-sdk.json")})
            os.close(slave)
            physics_started = False
            while True:
                now = time.monotonic()
                if now - started > 180 + count / 50:
                    raise RuntimeError("Configured run deadline exceeded; no automatic retry")
                if select.select([master], [], [], 0.004)[0]:
                    try:
                        text = os.read(master, 65536).decode(errors="replace")
                    except OSError:
                        text = ""
                    transcript += text
                    ctl_log.write(text); ctl_log.flush()
                if "G1Deploy object created successfully!" in transcript and not physics_started:
                    (output / "simulation-start.flag").touch()
                    physics_started = True
                    events.append({"name": "physics_started", "monotonic": now})
                if "Init Done" in transcript and enabled is None:
                    os.write(master, b"\n")
                    enabled = now
                    events.append({"name": "zmq_enable_requested", "monotonic": now})
                if enabled is not None and policy_started is None and now - last_send > 0.05:
                    publisher.send(wire)
                    sends += 1; last_send = now
                if sends >= 3 and "Protocol v3: Received SMPL action" in transcript and policy_started is None:
                    os.write(master, b"]")
                    policy_started = now
                    events.append({"name": "policy_start_requested", "monotonic": now})
                while subscriber.poll(0):
                    packet = subscriber.recv()
                    payload = msgpack.unpackb(packet[len(b"g1_debug"):], raw=False)
                    row = {"receive_monotonic": time.monotonic(), "payload": payload}
                    packets.append(row); data_log.write(json.dumps(row) + "\n")
                    if released is None:
                        (output / "release.flag").touch()
                        released = now
                        events.append({"name": "band_release_requested", "monotonic": now})
                consumed = last_input_frame(output / "controller-input.csv")
                if consumed is not None and consumed >= warmup + count:
                    complete = True
                    events.append({"name": "complete_source_consumed", "monotonic": now, "next_control_frame": consumed})
                    break
                if (output / "fall.json").exists():
                    raise RuntimeError("Physical fall; failed trajectory retained")
                if controller.poll() is not None or sim.poll() is not None:
                    raise RuntimeError("Controller/simulator exited before complete source consumption")
                if "[ERROR]" in transcript or "Stopping control system." in transcript:
                    raise RuntimeError("Controller reported an error")
    except Exception:
        failure = traceback.format_exc()
    finally:
        if master is not None:
            try: os.write(master, b"O")
            except OSError: pass
        (output / "stop.flag").touch()
        r1.stop_process(controller); r1.stop_process(sim)
        if master is not None: os.close(master)
        subscriber.close(0); publisher.close(0); context.term()
        write_json(output / "run-events.json", {"events": events, "source_completed": complete, "failure": failure, "packets": len(packets), "whole_cache_sends_before_policy": sends})
    return evaluate_recorded(args.reference, output, complete, failure, args.video)


def evaluate_recorded(reference, output, complete, failure, video):
    count = len(np.load(reference)["timestamps"])
    modes = read_rows(output / "controller-csv/encoder_mode.csv")
    active = [row for row in modes if float(list(row.values())[-1]) == 2]
    metrics = {"status": "failed", "scope": "SMPL-stream physical execution only; extraction quality/body error/demo assessed separately", "source_completed": complete, "failure": failure, "smpl_encoder_seen": bool(active), "body_reference_error_status": "awaiting_verification", "cloud_cost_usd": 0}
    if active and (output / "actual-state.npz").exists():
        try:
            clock, consumed_stamps, consumed_source_times = reference_clock(reference.parent, output)
        except (ValueError, FileNotFoundError, KeyError) as error:
            metrics["failure"] = f"Native reference clock not verified: {error}"
            write_json(output / "physical-metrics.json", metrics)
            return 1
        start = float(consumed_stamps[0])
        stop = start + count / 50
        actual = np.load(output / "actual-state.npz")
        mask = (actual["monotonic"] >= start) & (actual["monotonic"] < stop)
        config = json.loads((PROJECT / "configs/r1-evaluation.json").read_text())
        if mask.any():
            times = actual["monotonic"][mask]
            height = actual["qpos"][mask, 2]
            tilt = r1.longest_duration(actual["root_up_cosine"][mask] < np.cos(np.deg2rad(config["fall_tilt_degrees"])), times)
            contact = r1.longest_duration(actual["nonfoot_floor_contact"][mask], times)
            fell = (output / "fall.json").exists() or height.min() < config["fall_root_height_m"] or tilt >= config["fall_tilt_duration_s"] or contact >= config["nonfoot_contact_duration_s"]
            band_off = not actual["elastic_band"][mask].any()
            finite = bool(np.isfinite(actual["qpos"]).all() and np.isfinite(actual["qvel"]).all())
            coverage = times[-1] - times[0] >= count / 50 - 0.03
            metrics.update({"status": "passed" if complete and clock["full_source_consumed"] and not failure and not fell and band_off and finite and coverage else "failed", "source_physical_start_monotonic": start, "source_physical_end_monotonic": stop, "actual_source_window_samples": int(mask.sum()), "physical_time_covered_seconds": float(times[-1] - times[0]), "full_source_window_covered": bool(coverage), "fell": bool(fell), "band_off_during_source": bool(band_off), "finite_actual_states": finite, "minimum_root_height_m": float(height.min()), "longest_excess_tilt_seconds": tilt, "longest_nonfoot_contact_seconds": contact, "free_root_gravity_contact_control": True, "actual_state_overwrites": False})
            metrics["source_clock"] = clock
            if video:
                render_measured_video(output, reference, consumed_stamps, consumed_source_times)
    write_json(output / "physical-metrics.json", metrics)
    print(json.dumps(metrics, indent=2))
    return 0 if metrics["status"] == "passed" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--video", action="store_true")
    parser.add_argument("--render-only", action="store_true", help="Re-evaluate and render a stopped recorded run on its verified native reference clock")
    parser.add_argument("--simulator-startup-timeout", type=float, default=120, help="Initialization wait only; physical/control acceptance is unchanged")
    parser.add_argument("--sim-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.simulator_startup_timeout <= 0:
        parser.error("--simulator-startup-timeout must be positive")
    if args.sim_worker:
        r1.sim_worker(args.output.resolve())
    elif args.reference and args.render_only:
        output = args.output.resolve()
        storage_check(output)
        if not (output / "stop.flag").exists() or not (output / "actual-state.npz").exists():
            parser.error("--render-only requires a stopped recorded physical run")
        for command_line in Path("/proc").glob("[0-9]*/cmdline"):
            try:
                executable = command_line.read_bytes().split(b"\x00")[0].decode()
            except (OSError, UnicodeError):
                continue
            if Path(executable).name == "g1_deploy_onnx_ref":
                parser.error("Wait for active control to stop before offline rendering")
        events = json.loads((output / "run-events.json").read_text())
        raise SystemExit(evaluate_recorded(args.reference, output, events["source_completed"], events["failure"], True))
    elif args.reference:
        raise SystemExit(run(args))
    else:
        parser.error("--reference is required")
