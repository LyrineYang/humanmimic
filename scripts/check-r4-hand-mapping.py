#!/usr/bin/env python3
"""Compare independent URDF FK with MuJoCo FK in the same palm frame."""
import argparse
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from r4_contract import JOINT_NAMES, SOURCE_JOINT_NAMES, sha256, write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--data-root", type=Path, default=Path(os.environ["R4_DATA_ROOT"]))
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    urdf_path = args.data_root / "sources/VideoManip/reconstruction/dex_retargeting/added/example/position_retargeting/leap_hand/leap_hand_right.urdf"
    urdf = ET.parse(urdf_path).getroot()
    asset = args.data_root / "assets/leap_hand"
    xml = ET.parse(asset / "right_hand.xml").getroot()
    xml.find("compiler").set("meshdir", str(asset / "assets"))
    xml.find("worldbody/body").set("pos", "0 0 0")
    xml.find("worldbody/body").set("quat", "1 0 0 0")
    model = mujoco.MjModel.from_xml_string(ET.tostring(xml, encoding="unicode"))
    data = mujoco.MjData(model)
    rows = []
    for amplitude in [0., .2, .5, .8]:
        q = np.array([amplitude, 0., amplitude, amplitude] * 3 + [amplitude] * 4)
        data.qpos[:] = q
        mujoco.mj_forward(model, data)
        angles = dict(zip(SOURCE_JOINT_NAMES, q))
        parents = {j.find("child").get("link"): j for j in urdf.findall("joint")}
        transforms = {l.get("name"): np.eye(4) for l in urdf.findall("link") if l.get("name") not in parents}

        def forward(link):
            if link in transforms:
                return transforms[link]
            joint = parents[link]
            origin, pose, motion = joint.find("origin"), np.eye(4), np.eye(4)
            if origin is not None:
                pose[:3, 3] = np.fromstring(origin.get("xyz", "0 0 0"), sep=" ")
                pose[:3, :3] = Rotation.from_euler("xyz", np.fromstring(origin.get("rpy", "0 0 0"), sep=" ")).as_matrix()
            if joint.get("type") == "revolute":
                motion[:3, :3] = Rotation.from_rotvec(np.fromstring(joint.find("axis").get("xyz"), sep=" ") * angles[joint.get("name")]).as_matrix()
            transforms[link] = forward(joint.find("parent").get("link")) @ pose @ motion
            return transforms[link]

        source_base_to_palm = forward("palm_lower")
        for target_name, source_name in zip(JOINT_NAMES, SOURCE_JOINT_NAMES):
            joint = urdf.find(f"joint[@name='{source_name}']")
            expected = np.linalg.inv(source_base_to_palm) @ forward(joint.find("child").get("link"))
            jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, target_name)
            bid = model.jnt_bodyid[jid]
            position_error = np.linalg.norm(expected[:3, 3] - data.xpos[bid])
            angular_error = (Rotation.from_matrix(expected[:3, :3]) * Rotation.from_matrix(data.xmat[bid].reshape(3, 3)).inv()).magnitude()
            rows.append({"pose": amplitude, "joint": target_name, "position_error_m": float(position_error), "rotation_error_rad": float(angular_error)})
    result = {"comparisons": len(rows), "source_urdf_sha256": sha256(urdf_path),
              "T_sourcebase_palm": source_base_to_palm.tolist(),
              "maximum_position_error_m": max(row["position_error_m"] for row in rows),
              "maximum_rotation_error_rad": max(row["rotation_error_rad"] for row in rows),
              "limits": {"position_m": .0005, "rotation_rad": .01}, "rows": rows}
    result["status"] = "passed" if result["maximum_position_error_m"] < .0005 and result["maximum_rotation_error_rad"] < .01 else "failed"
    write_json(args.output, result)
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))
    raise SystemExit(result["status"] != "passed")


if __name__ == "__main__":
    main()
