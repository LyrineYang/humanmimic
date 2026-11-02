#!/usr/bin/env python3
"""Render declared synthetic RGB-D observations for geometry-mechanism development."""
import argparse
import json
import math
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import imageio.v2 as imageio
import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from r4_contract import sha256, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--views", type=int, default=24)
    parser.add_argument("--points", type=int, default=32768)
    parser.add_argument("--seed", type=int, default=1101)
    args = parser.parse_args()
    scene = json.loads(args.scene.read_text())
    if scene.get("split") not in {"debug", "readiness"} or scene.get("geometry_role") != "evaluation_only":
        raise ValueError("Only development/readiness synthetic observation generation is authorized")
    if not 4 <= args.views <= 48 or not 256 <= args.points <= 65536:
        raise ValueError("Observation generation exceeds preparation bounds")
    if scene.get("collision_representation") != "analytic_convex_parts":
        raise ValueError("This generator is for the procedural analytic-object mechanism track")
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "rgb").mkdir()
    # No dynamics are run: these are input observations, never claimed as execution video.
    xml = ET.Element("mujoco")
    ET.SubElement(xml, "option", gravity="0 0 -9.81")
    visual = ET.SubElement(xml, "visual")
    ET.SubElement(visual, "global", offwidth="320", offheight="240")
    ET.SubElement(visual, "headlight", ambient=".4 .4 .4", diffuse=".6 .6 .6", specular="0 0 0")
    world = ET.SubElement(xml, "worldbody")
    ET.SubElement(world, "light", pos=".3 .3 .5", dir="0 0 -1")
    ET.SubElement(world, "camera", name="observer", fovy="45")
    body = ET.SubElement(world, "body", name="object")
    for i, part in enumerate(scene["collision_parts"]):
        ET.SubElement(body, "geom", name=f"part_{i}", type=part["type"], size=" ".join(map(str, part["size"])),
                      pos=" ".join(map(str, part.get("position", [0, 0, 0]))), rgba=".85 .45 .12 1")
    model = mujoco.MjModel.from_xml_string(ET.tostring(xml, encoding="unicode"))
    data = mujoco.MjData(model)
    renderer = mujoco.Renderer(model, height=240, width=320)
    from OpenGL import GL
    gl_renderer = GL.glGetString(GL.GL_RENDERER).decode()
    rng = np.random.default_rng(args.seed)
    f = 120 / math.tan(math.radians(22.5))
    yy, xx = np.mgrid[:240, :320]
    cameras, point_sets, normal_sets = [], [], []
    writer = imageio.get_writer(args.output / "synthetic-observations.mp4", fps=12, codec="libx264")
    try:
        for i in range(args.views):
            azimuth = 2 * math.pi * i / args.views
            camera_position = np.array([.22 * math.cos(azimuth), .22 * math.sin(azimuth), .10 if i % 2 == 0 else .17])
            forward = -camera_position / np.linalg.norm(camera_position)
            right = np.cross(forward, [0, 0, 1]); right /= np.linalg.norm(right)
            up = np.cross(right, forward)
            world_mj = np.column_stack([right, up, -forward])
            model.cam_pos[0] = camera_position
            model.cam_quat[0] = Rotation.from_matrix(world_mj).as_quat()[[3, 0, 1, 2]]
            mujoco.mj_forward(model, data)
            renderer.update_scene(data, camera="observer")
            rgb = renderer.render().copy()
            imageio.imwrite(args.output / "rgb" / f"{i:04d}.png", rgb)
            writer.append_data(rgb)
            renderer.enable_depth_rendering()
            depth = renderer.render().copy()
            renderer.disable_depth_rendering()
            renderer.enable_segmentation_rendering()
            segmentation = renderer.render().copy()
            renderer.disable_segmentation_rendering()
            mask = segmentation[:, :, 1] == int(mujoco.mjtObj.mjOBJ_GEOM)
            noisy_depth = depth + rng.normal(0, .0005, depth.shape)
            local = np.stack([(xx - 159.5) / f * noisy_depth, (yy - 119.5) / f * noisy_depth, noisy_depth], axis=-1)
            world_cv = world_mj @ np.diag([1, -1, -1])
            xyz = local @ world_cv.T + camera_position
            # Surface normals use clean neighboring depth on this controlled sensor track.
            # They are simulated observations, not predictions from RGB; record this explicitly.
            clean_local = np.stack([(xx - 159.5) / f * depth, (yy - 119.5) / f * depth, depth], axis=-1)
            clean_xyz = clean_local @ world_cv.T + camera_position
            n = np.cross(clean_xyz[2:, 1:-1] - clean_xyz[:-2, 1:-1], clean_xyz[1:-1, 2:] - clean_xyz[1:-1, :-2])
            norm = np.linalg.norm(n, axis=-1)
            valid = mask[1:-1, 1:-1] & mask[2:, 1:-1] & mask[:-2, 1:-1] & mask[1:-1, 2:] & mask[1:-1, :-2] & (norm > 1e-10)
            normals = n[valid] / norm[valid, None]
            points = xyz[1:-1, 1:-1][valid]
            normals[np.sum(normals * (camera_position - points), axis=1) < 0] *= -1
            point_sets.append(points); normal_sets.append(normals)
            cameras.append({"index": i, "K": [[f, 0, 159.5], [0, f, 119.5], [0, 0, 1]],
                            "R_world_opencv": world_cv.tolist(), "camera_position": camera_position.tolist()})
    finally:
        writer.close(); renderer.close()
    points = np.concatenate(point_sets)
    normals = np.concatenate(normal_sets)
    if len(points) < args.points:
        raise ValueError("Not enough independent observations for requested point budget")
    selected = rng.choice(len(points), args.points, replace=False)
    np.savez_compressed(args.output / "observations.npz", points=points[selected], normals=normals[selected])
    result = {"status": "passed", "kind": "synthetic_rgbd_mechanism_observations", "split": scene["split"],
              "object_id": scene.get("object_id", "readiness"), "source_geometry_sha256": sha256(args.scene),
              "points": args.points, "views": args.views, "depth_noise_std_m": .0005,
              "normal_source": "simulated depth finite differences; not an RGB-estimated normal",
              "renderer": gl_renderer, "cameras": cameras, "seed": args.seed,
              "observations_sha256": sha256(args.output / "observations.npz"),
              "boundary": "Calibration and depth are controlled sensor inputs. This does not validate monocular reconstruction or manipulation.",
              "heldout_used": False}
    write_json(args.output / "manifest.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "cameras"}, indent=2))


if __name__ == "__main__":
    main()
