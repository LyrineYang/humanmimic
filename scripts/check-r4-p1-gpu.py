#!/usr/bin/env python3
"""GPU-gated P1 integration: four real LEAP distal assemblies on a force plate.

MuJoCo 3.2.7 dynamics/sensor plugins execute on CPU; EGL rendering and numerical
acceptance execute on NVIDIA CUDA. This does NOT claim GPU physics, a successful
grasp, full-hand calibration, or an experiment executed during source preparation.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import imageio.v2 as imageio
import mujoco
import torch

from r4_contract import sha256, write_json
from r4_cuda import require_cuda
from r4_sensor_bridge import instrument, SensorBridge

ACTIVE_OUTPUT = None


def main():
    global ACTIVE_OUTPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[1]/"configs/r4-p1p2.json")
    parser.add_argument("--hand-asset", type=Path, default=Path(os.environ.get("R4_DATA_ROOT", "../humanmimic-data/r4"))/"assets/leap_hand")
    args = parser.parse_args()
    device, gpu = require_cuda()
    cfg = json.loads(args.config.read_text())
    # Noise-free physical force-direction calibration; health perturbations are
    # checked separately against the same acquired final transducer samples.
    sensor = copy.deepcopy(cfg["sensor"])
    sensor.update(noise_std_n=0, dropout_probability=0)
    source = ET.parse(args.hand_asset/"right_hand.xml").getroot()
    root = ET.Element("mujoco", model="LEAP_four_distal_force_calibration")
    compiler = copy.deepcopy(source.find("compiler"))
    compiler.set("meshdir", str((args.hand_asset/"assets").resolve()))
    root.append(compiler)
    root.append(copy.deepcopy(source.find("asset")))
    root.append(copy.deepcopy(source.find("default")))
    ET.SubElement(root, "option", timestep=".002", gravity="0 0 -9.81", integrator="implicitfast")
    visual = ET.SubElement(root, "visual")
    ET.SubElement(visual, "global", offwidth="640", offheight="480")
    world = ET.SubElement(root, "worldbody")
    ET.SubElement(world, "light", pos="0 0 1")
    ET.SubElement(world, "geom", name="plate", type="plane", size="1 1 .01", friction="1 .005 .0001")
    for index, spec in enumerate(sensor["sites"].values()):
        body = copy.deepcopy(source.find(f".//body[@name='{spec['body']}']"))
        body.set("pos", f"{index*.1-.15} 0 .09")
        body.set("quat", "1 0 0 0")
        for joint in list(body.findall("joint")):
            body.remove(joint)
        ET.SubElement(body, "freejoint")
        world.append(body)
    instrument(root, sensor)
    xml = ET.tostring(root, encoding="unicode")
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    bridge = SensorBridge(model, sensor)
    renderer = mujoco.Renderer(model, height=480, width=640)
    from OpenGL import GL
    renderer_name = GL.glGetString(GL.GL_RENDERER).decode()
    vendor = GL.glGetString(GL.GL_VENDOR).decode()
    if "NVIDIA" not in vendor:
        renderer.close()
        raise RuntimeError(f"NVIDIA EGL required; vendor={vendor}, renderer={renderer_name}")
    args.output.mkdir(parents=True, exist_ok=False)
    ACTIVE_OUTPUT = args.output
    (args.output/"scene.xml").write_text(xml)
    write_json(args.output/"calibration.json", bridge.calibration)
    write_json(args.output/"manifest.json", {"status": "running", "gpu": gpu, "renderer": renderer_name,
        "config_sha256": sha256(args.config), "hand_sha256": sha256(args.hand_asset/"provenance.json"),
        "source_sha256": {name: sha256(Path(__file__).parent/name) for name in ["check-r4-p1-gpu.py", "r4_sensor_bridge.py", "r4_cuda.py"]}})
    camera = mujoco.MjvCamera()
    camera.lookat[:] = [0, 0, .02]
    camera.distance, camera.azimuth, camera.elevation = .6, 90, -40
    writer = imageio.get_writer(args.output/"actual-four-pad-execution.mp4", fps=25, codec="libx264")
    records, world_forces, contact_counts, waiting_empty = [], [], [], None
    try:
        for step in range(1001):
            mujoco.mj_forward(model, data)
            if step % 10 == 0:
                bridge.sample(data)
                packets = bridge.receive(data.time)
                if step == 0:
                    waiting_empty = not packets
                records.extend(packets)
                sample = []
                for finger, (site, start, count) in bridge.bindings.items():
                    force = torch.tensor(data.sensordata[start:start+count].copy(), device=device, dtype=torch.float64).reshape(3, -1).sum(-1)[[1, 2, 0]]
                    rotation = torch.tensor(data.site_xmat[site].copy(), device=device, dtype=torch.float64).reshape(3, 3)
                    sample.append(rotation @ force)
                world_forces.append(torch.stack(sample))
                # Evaluation-only raw count is never exported as a sensor feature.
                contact_counts.append(int(data.ncon))
            if step % 20 == 0:
                renderer.update_scene(data, camera=camera)
                writer.append_data(renderer.render())
            if step < 1000:
                mujoco.mj_step(model, data)
    finally:
        writer.close()
        renderer.close()
    forces = torch.stack(world_forces)
    mass = torch.tensor([model.body_mass[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, s["body"])] for s in sensor["sites"].values()], device=device, dtype=torch.float64)
    expected = torch.zeros((4, 3), device=device, dtype=torch.float64)
    expected[:, 2] = mass * 9.81
    measured = forces[-20:].mean(0)
    checks = {"four_finger_direction_and_load": bool(((measured-expected).norm(dim=-1) < cfg["acceptance"]["force_tolerance_n"]).all()),
              "initial_no_contact": bool(forces[0].abs().max() < 1e-10),
              "multiple_contacts": max(contact_counts) >= 4, "latency_queue": waiting_empty and bool(records) and all(p["received_time_s"] >= p["time_s"]+.02-1e-9 for p in records)}
    dropped_config = copy.deepcopy(sensor)
    dropped_config.update(dropout_probability=1, latency_s=0)
    dropped = SensorBridge(model, dropped_config)
    dropped.sample(data)
    dropped_packets = dropped.receive(data.time)
    checks["dropout_is_unknown"] = len(dropped_packets) == 4 and all(not p["valid"] and p["force_sensor_n"] is None for p in dropped_packets)
    clipped_config = copy.deepcopy(sensor)
    clipped_config.update(saturation_n=.001, threshold_n=.0001, latency_s=0)
    clipped = SensorBridge(model, clipped_config)
    clipped.sample(data)
    clipped_packets = clipped.receive(data.time)
    checks["saturation_is_marked"] = all(bool(torch.tensor(p["saturated"], device=device).any()) for p in clipped_packets)
    with (args.output/"sensor-packets.jsonl").open("x") as handle:
        for packet in records:
            handle.write(json.dumps(packet, allow_nan=False)+"\n")
    write_json(args.output/"force-history.json", {"world_forces_n": forces.tolist(), "evaluation_contact_counts": contact_counts})
    result = {"status": "passed" if all(checks.values()) else "failed", "checks": checks,
        "measured_world_force_n": measured.tolist(), "expected_world_force_n": expected.tolist(), "gpu": gpu,
        "full_hand_contact_region_calibration": "awaiting_verification", "grasp": "awaiting_verification",
        "scope": "Four actual LEAP distal assemblies, gravity/load/health calibration; GPU-gated MuJoCo+NVIDIA EGL integration, not GPU physics",
        "heldout_used": False, "video": "actual-four-pad-execution.mp4"}
    write_json(args.output/"result.json", result)
    manifest = json.loads((args.output/"manifest.json").read_text())
    manifest.update(status="complete", result_sha256=sha256(args.output/"result.json"))
    write_json(args.output/"manifest.json", manifest)
    if not all(checks.values()):
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        if ACTIVE_OUTPUT is not None:
            path = ACTIVE_OUTPUT/"manifest.json"
            manifest = json.loads(path.read_text()) if path.exists() else {}
            manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
            write_json(path, manifest)
        raise
