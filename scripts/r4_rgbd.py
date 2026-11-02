"""Simulation-side noisy RGB-D sensor, never an object-state exporter."""
import mujoco
import numpy as np


class RGBDSensor:
    def __init__(self, model, object_body, seed=1101):
        self.model = model
        self.object_geoms = np.flatnonzero(model.geom_bodyid == object_body)
        self.renderer = mujoco.Renderer(model, height=240, width=320)
        self.rng = np.random.default_rng(seed)
        self.camera = mujoco.MjvCamera()
        self.camera.lookat[:] = [0, 0, .12]  # fixed rig, not true object tracking
        self.camera.distance, self.camera.azimuth, self.camera.elevation = .55, 135, -25
        self.f = 120 / np.tan(np.deg2rad(model.vis.global_.fovy / 2))

    def sample(self, data):
        self.renderer.update_scene(data, camera=self.camera)
        # Use the rendered camera calibration; no object transform is accessed.
        cameras = self.renderer.scene.camera
        position = (np.asarray(cameras[0].pos) + np.asarray(cameras[1].pos)) / 2
        forward, up = np.asarray(cameras[0].forward), np.asarray(cameras[0].up)
        right = np.cross(forward, up)
        world_cv = np.column_stack([right, -up, forward])
        self.renderer.enable_depth_rendering()
        depth = self.renderer.render().copy()
        self.renderer.disable_depth_rendering()
        self.renderer.enable_segmentation_rendering()
        segmentation = self.renderer.render().copy()
        self.renderer.disable_segmentation_rendering()
        mask = np.isin(segmentation[:, :, 0], self.object_geoms) & (segmentation[:, :, 1] == int(mujoco.mjtObj.mjOBJ_GEOM))
        depth += self.rng.normal(0, .0005, depth.shape)
        yy, xx = np.mgrid[:240, :320]
        local = np.stack([(xx - 159.5) / self.f * depth, (yy - 119.5) / self.f * depth, depth], -1)
        world = local @ world_cv.T + position
        normal = np.cross(world[1:-1, 2:] - world[1:-1, :-2], world[2:, 1:-1] - world[:-2, 1:-1])
        length = np.linalg.norm(normal, axis=-1)
        valid = mask[1:-1, 1:-1] & mask[1:-1, 2:] & mask[1:-1, :-2] & mask[2:, 1:-1] & mask[:-2, 1:-1] & (length > 1e-9)
        points = world[1:-1, 1:-1][valid]
        normals = normal[valid] / length[valid, None]
        normals[np.sum(normals * (position - points), axis=1) < 0] *= -1
        take = self.rng.choice(len(points), min(512, len(points)), replace=False)
        return {"time_s": float(data.time), "source": "simulated_rgbd_with_instance_mask",
                "points_world_m": points[take].tolist(), "normals_world": normals[take].tolist(), "sigma_m": .0005}

    def close(self):
        self.renderer.close()
