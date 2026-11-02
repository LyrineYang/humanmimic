"""Build an independent evaluation world with actuated LEAP and a free object."""
from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from pathlib import Path

from r4_contract import JOINT_NAMES, sha256


def make_scene(hand_asset: Path, task: dict, physics: dict, *, sensor_config=None) -> str:
    root = ET.parse(hand_asset / "right_hand.xml").getroot()
    root.find("compiler").set("meshdir", str((hand_asset / "assets").resolve()))
    option = root.find("option")
    option.set("timestep", str(physics["timestep_seconds"]))
    option.set("gravity", " ".join(map(str, physics["gravity"])))
    option.set("iterations", str(physics["iterations"]))
    root.find("default/position").set("forcelimited", "true")
    limit = physics["finger_torque_limit_nm"]
    root.find("default/position").set("forcerange", f"{-limit} {limit}")
    world = root.find("worldbody")
    palm = world.find("body[@name='palm']")
    palm.set("pos", "0 0 0")
    palm.set("quat", "1 0 0 0")
    ET.SubElement(palm, "freejoint", name="wrist_free")
    # A free wrist is servoed by bounded external wrench in the runner, not teleported.
    ET.SubElement(world, "light", pos="0 -0.3 1.0", dir="0 0 -1", diffuse="0.8 0.8 0.8")
    ET.SubElement(world, "geom", name="floor", type="plane", size="1 1 .05", rgba=".18 .23 .27 1", friction=".8 .005 .0001")
    obj = ET.SubElement(world, "body", name="object", pos=" ".join(map(str, task["initial_position"])),
                        quat=" ".join(map(str, task.get("initial_quaternion", [1, 0, 0, 0]))))
    ET.SubElement(obj, "freejoint", name="object_free")
    parts = task["collision_parts"]
    if not parts:
        raise ValueError("Object requires declared collision geometry")
    if task.get("collision_representation") not in {"analytic_convex_parts", "verified_convex_mesh_parts"}:
        raise ValueError("Use verified analytic convex parts; no silent single-hull conversion of concave meshes")
    for i, part in enumerate(parts):
        if part["type"] not in {"box", "sphere", "cylinder", "capsule", "mesh"}:
            raise ValueError("Unsupported collision part")
        attributes = {"name": f"object_part_{i}", "type": part["type"],
                      "pos": " ".join(map(str, part.get("position", [0, 0, 0]))),
                      "quat": " ".join(map(str, part.get("quaternion", [1, 0, 0, 0]))),
                      "mass": str(task.get("mass_kg", physics["object_mass_kg"]) / len(parts)),
                      "friction": " ".join(map(str, task.get("friction", physics["object_friction"]))), "rgba": ".85 .45 .12 1"}
        if part["type"] == "mesh":
            path = Path(part["file"])
            if not path.is_absolute() or sha256(path) != part["sha256"] or not part.get("convex_verified"):
                raise ValueError("Collision mesh path/hash/convex verification missing or changed")
            name = f"object_mesh_{i}"
            ET.SubElement(root.find("asset"), "mesh", name=name, file=str(path))
            attributes["mesh"] = name
        else:
            attributes["size"] = " ".join(map(str, part["size"]))
        ET.SubElement(obj, "geom", **attributes)
    visual = ET.SubElement(root, "visual")
    ET.SubElement(visual, "global", offwidth="640", offheight="480")
    ET.SubElement(visual, "headlight", diffuse=".7 .7 .7", ambient=".3 .3 .3", specular="0 0 0")
    if sensor_config is not None:
        from r4_sensor_bridge import instrument
        instrument(root, sensor_config)
    return ET.tostring(root, encoding="unicode")
