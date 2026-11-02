"""Trusted simulation-side transducer. No contact records enter public packets.

touch_grid measures the entire welded distal body, not just the cosmetic pad.
Calibration therefore includes ALL collidable geometry of that hand body.
Object identity/pose/mesh/materials never appear in the public calibration.
"""
from __future__ import annotations

from collections import deque
import copy
import json
import xml.etree.ElementTree as ET

import mujoco
import numpy as np
from scipy.spatial import ConvexHull


def instrument(root, config):
    """Only sites/sensors are added; mass, joints, actuators and contacts stay intact."""
    extension = root.find("extension")
    if extension is None:
        extension = ET.SubElement(root, "extension")
    ET.SubElement(extension, "plugin", plugin="mujoco.sensor.touch_grid")
    sensors = root.find("sensor")
    if sensors is None:
        sensors = ET.SubElement(root, "sensor")
    for finger, spec in config["sites"].items():
        body = root.find(f".//body[@name='{spec['body']}']")
        if body is None:
            raise ValueError(f"Missing LEAP body: {spec['body']}")
        site = f"r4_{finger}_sensor"
        ET.SubElement(body, "site", name=site, size="0.001", rgba="0 1 0 0.3",
                      pos=" ".join(map(str, spec["position_m"])),
                      quat=" ".join(map(str, spec["quaternion_wxyz"])))
        plugin = ET.SubElement(sensors, "plugin", name=f"r4_{finger}_force_grid",
                               plugin="mujoco.sensor.touch_grid", objtype="site", objname=site)
        for key, value in {"nchannel": "3", "size": " ".join(map(str, config["size"])),
                           "fov": " ".join(map(str, config["fov_deg"])), "gamma": str(config["gamma"])}.items():
            ET.SubElement(plugin, "config", key=key, value=value)


def rotation(quaternion):
    result = np.empty(9)
    mujoco.mju_quat2Mat(result, np.asarray(quaternion, dtype=float))
    return result.reshape(3, 3)


def hand_surface(model, body, site):
    """Known hand collision convex surfaces in sensor coordinates, before any run.

    No scene geometry or mjData is accepted. LEAP distal collision shapes are
    boxes and convex meshes. Fail on other types instead of approximating them.
    """
    triangles = []
    for geom in np.flatnonzero(model.geom_bodyid == body):
        if not (model.geom_contype[geom] or model.geom_conaffinity[geom]):
            continue
        kind = model.geom_type[geom]
        if kind == mujoco.mjtGeom.mjGEOM_BOX:
            vertices = np.asarray([[x, y, z] for x in [-1, 1] for y in [-1, 1] for z in [-1, 1]], float)
            vertices *= model.geom_size[geom]
        elif kind == mujoco.mjtGeom.mjGEOM_MESH:
            mesh = model.geom_dataid[geom]
            start, count = model.mesh_vertadr[mesh], model.mesh_vertnum[mesh]
            vertices = np.asarray(model.mesh_vert[start:start + count], dtype=float)
        else:
            raise ValueError("Uncalibrated distal collision shape")
        hull = ConvexHull(vertices)
        vertices = vertices @ rotation(model.geom_quat[geom]).T + model.geom_pos[geom]
        vertices = (vertices - model.site_pos[site]) @ rotation(model.site_quat[site])
        for face in hull.simplices:
            triangle = vertices[face].copy()
            # Outward orientation is computed from known convex hand geometry.
            if np.dot(np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0]),
                      triangle.mean(0) - vertices.mean(0)) < 0:
                triangle[[1, 2]] = triangle[[2, 1]]
            triangles.append(triangle.tolist())
    if not triangles:
        raise ValueError("No calibrated hand collision surface")
    return triangles


class SensorBridge:
    def __init__(self, model, config):
        self.config = copy.deepcopy(config)
        self.rng = np.random.default_rng(config["seed"])
        self.pending = deque()
        self.bindings = {}
        pads = {}
        for finger, spec in config["sites"].items():
            site = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, f"r4_{finger}_sensor")
            sensor = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, f"r4_{finger}_force_grid")
            body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, spec["body"])
            if min(site, sensor, body) < 0:
                raise ValueError("Missing instrumented LEAP sensor")
            if model.sensor_dim[sensor] != 3 * np.prod(config["size"]):
                raise ValueError("Sensor layout mismatch")
            self.bindings[finger] = (site, int(model.sensor_adr[sensor]), int(model.sensor_dim[sensor]))
            pads[finger] = {"triangles_sensor_m": hand_surface(model, body, site)}
        self.calibration = {"schema_version": 2, "role": "hand_sensor_calibration", "hand": "leap_right",
            "size": config["size"], "fov_deg": config["fov_deg"], "gamma": config["gamma"],
            "surface_margin_m": config["surface_margin_m"], "pads": pads,
            "threshold_n": config["threshold_n"], "max_age_s": config["max_age_s"],
            "noise_std_n": config["noise_std_n"], "saturation_n": config["saturation_n"],
            "force_convention": "force_on_hand_in_sensor_xyz", "calibration_status": "awaiting_verification"}

    def sample(self, data):
        """Read only time, sensordata and hand sites; timestamps remain acquisition-time."""
        cfg = self.config
        width, height = cfg["size"]
        for finger, (site, start, count) in self.bindings.items():
            raw = data.sensordata[start:start + count].reshape(3, height, width)
            xyz = np.moveaxis(raw[[1, 2, 0]], 0, -1).copy()  # zxy -> xyz, signed
            finite = bool(np.isfinite(xyz).all())
            if finite:
                xyz += self.rng.normal(0, cfg["noise_std_n"], xyz.shape)
            saturated = np.any(np.abs(xyz) >= cfg["saturation_n"], axis=-1)
            xyz = np.clip(xyz, -cfg["saturation_n"], cfg["saturation_n"])
            valid = finite and self.rng.random() >= cfg["dropout_probability"]
            transform = np.eye(4)
            transform[:3, :3] = data.site_xmat[site].reshape(3, 3)
            transform[:3, 3] = data.site_xpos[site]
            packet = {"sensor_id": finger, "time_s": float(data.time),
                "received_time_s": float(data.time) + cfg["latency_s"],
                "valid": valid, "reason": "ok" if valid else "dropout_or_nonfinite",
                "T_world_sensor": transform.tolist(),
                "force_sensor_n": xyz.tolist() if valid else None,
                "saturated": saturated.tolist() if valid else None}
            self.pending.append(packet)

    def receive(self, now_s):
        result = []
        while self.pending and self.pending[0]["received_time_s"] <= now_s + 1e-10:
            packet = self.pending.popleft()
            packet["received_time_s"] = float(now_s)  # actual polling arrival
            result.append(packet)
        return result


class ObservationWriter:
    """Public stream and calibration have no path references to evaluation logs."""
    def __init__(self, directory, bridge, split, source="simulated_sensor"):
        directory.mkdir(parents=True, exist_ok=False)
        self.handle = (directory / "observations.jsonl").open("x")
        (directory / "calibration.json").write_text(json.dumps(bridge.calibration, allow_nan=False, indent=2) + "\n")
        self.split, self.source = split, source

    def append(self, now_s, packets, joints, target, vision=None, wrist=None):
        frame = {"schema_version": 2, "role": "observation", "split": self.split,
            "source": self.source, "time_s": float(now_s), "joint_position_rad": list(map(float, joints)),
            "joint_target_rad": list(map(float, target)), "tactile": packets, "vision": vision}
        if wrist is not None:
            frame["T_world_wrist"] = wrist
        self.handle.write(json.dumps(frame, allow_nan=False) + "\n")
        self.handle.flush()
        return frame

    def close(self):
        self.handle.close()
