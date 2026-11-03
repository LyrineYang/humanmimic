"""CUDA support regions of taxels on known hand surfaces; no object inputs."""
import math
import torch


def unit(x):
    return x/x.norm(dim=-1,keepdim=True).clamp_min(1e-12)


class HandTactileSurface:
    def __init__(self,calibration,config,device):
        if device.type!='cuda':raise RuntimeError('Hand tactile geometry requires CUDA')
        self.cal,self.cfg,self.device=calibration,config,device

    def tensor(self,value):
        return torch.as_tensor(value,device=self.device,dtype=torch.float64)

    def calibrate_surface(self, triangles):
        """CUDA rays intersect known hand geometry, never the manipulated object.

        3x3 rays per angular bin; spatial support includes spread plus calibration
        margin. Edge bins with missing rays are invalid, not exact contact points.
        Finite sampling is an approximation to calibrate in P1, not ground truth.
        """
        tri = self.tensor(triangles)
        if tri.ndim != 3 or tri.shape[1:] != (3, 3):
            raise ValueError("Invalid calibrated hand triangles")
        width, height = self.cal["size"]
        fov = self.tensor(self.cal["fov_deg"]) * math.pi / 180
        yy, xx = torch.meshgrid(torch.arange(height, device=self.device), torch.arange(width, device=self.device), indexing="ij")
        fractions = self.tensor([[x, y] for y in [.05, .5, .95] for x in [.05, .5, .95]])
        a = ((xx.reshape(-1, 1) + fractions[:, 0]) / width * 2 - 1) * fov[0]
        e = ((yy.reshape(-1, 1) + fractions[:, 1]) / height * 2 - 1) * fov[1]
        rays = torch.stack([e.cos() * a.sin(), e.sin(), -e.cos() * a.cos()], -1).reshape(-1, 3)
        edge1, edge2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
        p = torch.linalg.cross(rays[:, None, :], edge2[None, :, :], dim=-1)
        determinant = (p * edge1).sum(-1)
        inverse = torch.where(determinant.abs() > 1e-10, 1 / determinant, torch.zeros_like(determinant))
        distance_to_origin = -tri[:, 0]
        u = (p * distance_to_origin).sum(-1) * inverse
        q = torch.linalg.cross(distance_to_origin, edge1)
        v = (rays[:, None, :] * q).sum(-1) * inverse
        distance = (edge2 * q).sum(-1)[None, :] * inverse
        valid = (determinant.abs() > 1e-10) & (u >= 0) & (v >= 0) & (u + v <= 1) & (distance > 0)
        distance = torch.where(valid, distance, torch.zeros_like(distance))
        far, triangle_id = distance.max(-1)  # outer envelope of the known hand
        near = torch.where(valid, distance, torch.full_like(distance, torch.inf)).min(-1).values
        near = torch.where(torch.isfinite(near), near, torch.zeros_like(near))
        # A bin can hit several known collision pieces. Include their full depth
        # interval rather than inventing a contact on only the outermost piece.
        near_points = (rays * near[:, None]).reshape(width * height, 9, 3)
        far_points = (rays * far[:, None]).reshape(width * height, 9, 3)
        points = torch.cat([near_points, far_points], 1)
        all_normals = unit(torch.linalg.cross(edge1, edge2))
        normals = all_normals[triangle_id].reshape(width * height, 9, 3)
        centers = (near_points[:, 4] + far_points[:, 4]) / 2
        spread = (points - centers[:, None, :]).norm(dim=-1).max(-1).values
        reference_normal = normals[:, 4].repeat_interleave(9, dim=0)
        normal_compatible = (((all_normals[None, :, :] * reference_normal[:, None, :]).sum(-1) > .5) | ~valid).all(-1).reshape(-1, 9).all(-1)
        # Inflate sampled angular support; no sub-taxel localization claim.
        radius = 1.5 * spread + self.cal["surface_margin_m"]
        return {"points": centers, "normals": normals[:, 4], "radius": radius,
                "valid": (far.reshape(-1, 9) > 0).all(-1) & normal_compatible & (radius <= self.cfg["maximum_support_radius_m"])}

