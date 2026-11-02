#!/usr/bin/env python3
"""Real target-hardware readiness checks. This performs bounded CUDA computation."""
import argparse
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import mujoco
import numpy as np
import torch

from r4_contract import JOINT_NAMES, sha256, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hand-asset", type=Path, default=Path(os.environ.get("R4_DATA_ROOT", Path(__file__).resolve().parents[2]/"humanmimic-data/r4")) / "assets/leap_hand")
    parser.add_argument("--core-only", action="store_true", help="Verify dependencies/CUDA without optional LEAP research assets")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    result = {"status": "awaiting_verification", "python": sys.version, "executable": sys.executable,
              "platform": platform.platform(), "glibc": platform.libc_ver(),
              "versions": {n: importlib.metadata.version(n) for n in ["numpy", "scipy", "mujoco", "torch", "torchvision", "trimesh", "imageio-ffmpeg"]},
              "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"), "errors": []}
    check = subprocess.run([sys.executable, "-m", "pip", "check"], capture_output=True, text=True)
    result["pip_check"] = {"returncode": check.returncode, "output": check.stdout + check.stderr}
    if check.returncode:
        result["errors"].append("pip dependency conflicts")
    try:
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable")
        if torch.cuda.device_count() != 1:
            raise RuntimeError("Expose exactly one checked idle GPU")
        torch.set_num_threads(8)
        torch.manual_seed(1101)
        a = torch.randn(512, 512, device="cuda")
        b = torch.randn(512, 512, device="cuda")
        expected = a.double() @ b.double()
        actual = a @ b
        torch.cuda.synchronize()
        error = float((actual.double() - expected).abs().max())
        probe = torch.randn(4096, 3, device="cuda", requires_grad=True)
        loss = probe.square().sum(1).mean()
        loss.backward()
        torch.cuda.synchronize()
        gradients_ok = bool(torch.isfinite(probe.grad).all())
        result["cuda"] = {"device": torch.cuda.get_device_name(), "capability": list(torch.cuda.get_device_capability()),
                          "compiled_architectures": torch.cuda.get_arch_list(), "toolkit": torch.version.cuda,
                          "max_absolute_fp32_error": error, "predeclared_error_limit": 0.001,
                          "finite_gradients": gradients_ok, "peak_allocated_bytes": torch.cuda.max_memory_allocated()}
        if error > .001 or not gradients_ok or "sm_70" not in torch.cuda.get_arch_list():
            raise RuntimeError("CUDA numerical/architecture check failed")
    except Exception as exc:
        result["errors"].append(str(exc))
    if args.core_only:
        result["model"] = {"status": "awaiting_verification", "reason": "Optional LEAP loading explicitly excluded from core check"}
    try:
        if args.core_only:
            return finish(args, result)
        model = mujoco.MjModel.from_xml_path(str(args.hand_asset / "right_hand.xml"))
        names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i) for i in range(model.njnt)]
        if model.nu != 16 or names != JOINT_NAMES:
            raise RuntimeError("LEAP joint/model mismatch")
        result["model"] = {"nq": model.nq, "nv": model.nv, "nu": model.nu, "joint_names": names,
                           "asset_manifest_sha256": sha256(args.hand_asset / "provenance.json")}
    except Exception as exc:
        result["errors"].append(str(exc))
    finish(args, result)


def finish(args, result):
    result["status"] = "failed" if result["errors"] else "passed"
    result["scope"] = "Dependencies and real single-GPU computation; optional MJCF loading; not manipulation acceptance"
    write_json(args.output / "result.json", result)
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(result["errors"]))


if __name__ == "__main__":
    main()
