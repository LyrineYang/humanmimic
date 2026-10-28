"""Verify the R1 environment; these checks do not certify SONIC control."""

import argparse
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import traceback


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    upstream = root / "vendor/GR00T-WholeBodyControl"
    results = {
        "scope": "Environment smoke checks only; no SONIC policy execution or R1 acceptance.",
        "python": sys.version,
        "executable": sys.executable,
        "hostname": platform.node(),
        "MUJOCO_GL": os.environ.get("MUJOCO_GL"),
        "packages": {},
        "checks": {},
    }

    def check(name, function):
        try:
            detail = function()
            results["checks"][name] = {"status": "passed", "detail": detail}
        except Exception:
            results["checks"][name] = {
                "status": "failed", "traceback": traceback.format_exc()
            }
        print(name, results["checks"][name]["status"], flush=True)

    for package in ["torch", "numpy", "scipy", "mujoco", "pin", "opencv-python",
                    "cyclonedds", "gear_sonic", "unitree_sdk2py"]:
        try:
            results["packages"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            results["packages"][package] = None

    def cuda_compute():
        import torch
        assert torch.cuda.is_available(), "PyTorch cannot use CUDA"
        a = torch.arange(256 * 256, dtype=torch.float32).reshape(256, 256) / 65536
        expected = a @ a.T
        actual = (a.cuda() @ a.cuda().T).cpu()
        torch.cuda.synchronize()
        error = float((actual - expected).abs().max())
        assert torch.allclose(actual, expected, atol=1e-3, rtol=1e-4), error
        return {"device": torch.cuda.get_device_name(0), "torch_cuda": torch.version.cuda,
                "max_abs_error": error, "peak_allocated_bytes": torch.cuda.max_memory_allocated()}

    def sim_imports():
        importlib.import_module("unitree_sdk2py.core.channel")
        importlib.import_module("gear_sonic.scripts.run_sim_loop")
        from gear_sonic.utils.network.network_utils import resolve_interface
        interface, mode = resolve_interface("sim")
        assert interface == "lo" and mode == "sim", (interface, mode)
        return {"interface": interface, "mode": mode, "dds_channel_created": False}

    def g1_kinematics():
        from gear_sonic.data.robot_model.instantiation.g1 import instantiate_g1_robot_model
        robot = instantiate_g1_robot_model()
        return {"nq": robot.pinocchio_wrapper.model.nq,
                "nv": robot.pinocchio_wrapper.model.nv}

    def g1_physics():
        import mujoco
        import numpy as np
        scene = upstream / "gear_sonic/data/robot_model/model_data/g1/scene_43dof.xml"
        model = mujoco.MjModel.from_xml_path(str(scene))
        data = mujoco.MjData(model)
        assert any(model.jnt_type == mujoco.mjtJoint.mjJNT_FREE), "No free root joint"
        assert model.opt.gravity[2] < 0, "Gravity disabled"
        for _ in range(200):
            mujoco.mj_step(model, data)
        assert np.isfinite(data.qpos).all() and np.isfinite(data.qvel).all()
        assert data.time > 0
        return {"scene": str(scene.relative_to(root)), "nq": model.nq,
                "nv": model.nv, "actuators": model.nu, "steps": 200,
                "simulation_seconds": data.time, "gravity": model.opt.gravity.tolist(),
                "controller_enabled": False,
                "meaning": "Asset loading and physics engine only; no tracking/stability claim."}

    def offscreen_render():
        import cv2
        import mujoco
        from OpenGL import GL
        scene = upstream / "gear_sonic/data/robot_model/model_data/g1/scene_43dof.xml"
        model = mujoco.MjModel.from_xml_path(str(scene))
        data = mujoco.MjData(model)
        mujoco.mj_forward(model, data)
        camera = mujoco.MjvCamera()
        camera.lookat[:] = [0, 0, 0.7]
        camera.distance = 2.5
        camera.azimuth = 135
        camera.elevation = -20
        with mujoco.Renderer(model, height=240, width=320) as renderer:
            renderer.update_scene(data, camera=camera)
            frame = renderer.render()
            gl_renderer = GL.glGetString(GL.GL_RENDERER)
            gl_vendor = GL.glGetString(GL.GL_VENDOR)
        assert frame.shape == (240, 320, 3), frame.shape
        assert frame.std() > 1, "Rendered image is blank"
        path = args.output / "g1-offscreen.png"
        assert cv2.imwrite(str(path), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        return {"image": str(path.resolve()), "shape": list(frame.shape),
                "gl_renderer": gl_renderer.decode() if gl_renderer else None,
                "gl_vendor": gl_vendor.decode() if gl_vendor else None}

    check("pytorch_cuda_compute", cuda_compute)
    check("official_sim_imports", sim_imports)
    check("g1_urdf_kinematics", g1_kinematics)
    check("g1_headless_physics_engine", g1_physics)
    check("g1_offscreen_render", offscreen_render)
    results["status"] = (
        "passed" if all(x["status"] == "passed" for x in results["checks"].values())
        else "failed"
    )
    (args.output / "environment-smoke.json").write_text(json.dumps(results, indent=2) + "\n")
    return 0 if results["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
