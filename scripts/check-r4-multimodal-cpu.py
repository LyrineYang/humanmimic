#!/usr/bin/env python3
"""Bounded CPU diagnostics: touch_grid transducer and analytic local-state examples."""
import argparse
import json
import os
import platform
import time
from pathlib import Path

import mujoco
import numpy as np

from r4_contract import sha256, write_json
from r4_multimodal import fit_contact_patch, score_touches, static_friction_lower_bound, validate_measurement


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise RuntimeError("Set CUDA_VISIBLE_DEVICES='' for this CPU-only diagnostic")
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    xml = '''<mujoco model="cpu_transducer_check">
      <option timestep="0.002" gravity="0 0 -9.81"/>
      <extension><plugin plugin="mujoco.sensor.touch_grid"/></extension>
      <worldbody>
        <geom type="plane" size="1 1 .01"/>
        <body name="probe" pos="0 0 .03">
          <freejoint/>
          <geom type="sphere" size=".01" mass=".05"/>
          <site name="grid_site" pos="0 0 .01" size=".001"/>
          <site name="touch_zone" type="sphere" size=".04"/>
        </body>
      </worldbody>
      <sensor>
        <touch name="normal_sum" site="touch_zone"/>
        <plugin name="pad" plugin="mujoco.sensor.touch_grid" objtype="site" objname="grid_site">
          <config key="nchannel" value="3"/><config key="size" value="4 4"/>
          <config key="fov" value="90 60"/><config key="gamma" value="0"/>
        </plugin>
      </sensor>
    </mujoco>'''
    (args.output/"sensor-scene.xml").write_text(xml)
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    history = []
    for _ in range(500):
        mujoco.mj_step(model, data)
        history.append([data.time, *data.sensordata.copy()])
    history = np.asarray(history)
    np.savez_compressed(args.output/"sensor-readings.npz", samples=history)
    # Only sensordata feeds this transducer check; no contact.pos/normal/GT shape input.
    normal = float(history[-50:, 1].mean())
    grid = history[-50:, 2:].reshape(50, 3, 4, 4).mean(0)
    grid_normal = float(grid[0].sum())
    sensor_ok = abs(normal-.05*9.81) < .01 and abs(grid_normal-normal) < .01
    mujoco.mj_forward(model, data)
    site = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "grid_site")
    transform = np.eye(4)
    transform[:3, :3] = data.site_xmat[site].reshape(3, 3)
    transform[:3, 3] = data.site_xpos[site]
    packet = {"schema_version": 1, "kind": "force", "source": "simulated_sensor",
              "sensor_id": "cpu_probe", "time_s": float(data.time), "received_time_s": float(data.time)+.01, "valid": True,
              "T_world_sensor": transform.tolist(), "units": {"length": "m", "force": "N", "time": "s"},
              # touch_grid uses [z,x,y] channels, force on the sensor body.
              "force_sensor_n": [float(grid[1].sum()), float(grid[2].sum()), grid_normal]}
    assert validate_measurement(packet, 1.02)
    write_json(args.output/"sensor-packet.json", packet)
    force = np.linspace(.2, 1.5, 16)
    # Independent analytic fixture, not measurements from the ball/plane above.
    shape, pose, compliance = .003, .002, .001
    displacement = shape+pose+compliance*force
    fit = fit_contact_patch(displacement, force, .0001, pose_observation_m=pose, pose_sigma_m=.0001)
    no_pose = fit_contact_patch(displacement, force, .0001)
    constant_load = fit_contact_patch(np.full(16, .006), np.ones(16), .0001,
                                      pose_observation_m=pose, pose_sigma_m=.0001)
    candidates = [{"id": "critical_patch", "measurement_jacobian": [1, 0], "noise_variance": 1e-6,
                   "cost_seconds": 1., "predicted_force_n": 1., "reachable": True},
                  {"id": "uncertain_backside", "measurement_jacobian": [0, 1], "noise_variance": 1e-6,
                   "cost_seconds": 1., "predicted_force_n": 1., "reachable": True}]
    decision = score_touches(np.diag([4e-6, 100e-6]), [[1, 0]], candidates)
    success = sensor_ok and fit["status"] == "passed" and no_pose["status"] == constant_load["status"] == "unobservable" and decision["selected"] == "critical_patch"
    result = {"status": "passed" if success else "failed", "is_research_result": False,
              "scope": "Native force transducer and analytic inference/decision diagnostics; no LEAP manipulation or WSM inference",
              "cpu_only": True, "mujoco": mujoco.__version__, "python": platform.python_version(),
              "sensor": {"steps": 500, "normal_n": normal, "grid_normal_n": grid_normal, "expected_static_weight_n": .4905,
                         "grid_channels": "z,x,y; 4x4 angular bins; not DIGIT optical contact geometry"},
              "analytic_patch_fixture": {"fit": fit, "without_pose_anchor": no_pose, "constant_load": constant_load,
                                        "naive_shape_error_m": float(displacement.mean()-shape)},
              "task_touch_selection": decision,
              "friction": static_friction_lower_bound([1, 2], [.4, 1.]),
              "wall_seconds": time.monotonic()-started,
              "source_sha256": {name: sha256(Path(__file__).parent/name) for name in ["r4_multimodal.py", "check-r4-multimodal-cpu.py"]},
              "heldout_used": False, "gpu_jobs": 0, "paid_usd": 0}
    write_json(args.output/"result.json", result)
    print(json.dumps(result, indent=2))
    raise SystemExit(not success)


if __name__ == "__main__":
    main()
