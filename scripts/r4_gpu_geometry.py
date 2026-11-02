"""Small CUDA geometry helpers shared by preparation and independent evaluation."""
import math
import torch


def ellipsoid(radii, rings=12, sectors=24):
    device, dtype = radii.device, radii.dtype
    vertices = [[0., 0., 1.]]
    for row in range(1, rings):
        latitude = math.pi * row / rings
        for col in range(sectors):
            angle = 2*math.pi*col/sectors
            vertices.append([math.sin(latitude)*math.cos(angle), math.sin(latitude)*math.sin(angle), math.cos(latitude)])
    vertices.append([0., 0., -1.])
    faces = []
    for col in range(sectors):
        nxt = (col+1) % sectors
        faces.append([0, 1+col, 1+nxt])
        for row in range(rings-2):
            a, b = 1+row*sectors+col, 1+row*sectors+nxt
            faces.extend([[a, a+sectors, b], [b, a+sectors, b+sectors]])
        a, b = 1+(rings-2)*sectors+col, 1+(rings-2)*sectors+nxt
        faces.append([a, len(vertices)-1, b])
    vertices = torch.tensor(vertices, device=device, dtype=dtype) * radii
    normals = vertices / radii.square()
    normals /= normals.norm(dim=-1, keepdim=True)
    return vertices, normals, torch.tensor(faces, device=device, dtype=torch.long)


def mesh_samples(vertices, faces, count, generator):
    tri = vertices[faces]
    area = torch.linalg.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0]).norm(dim=-1)
    chosen = torch.multinomial(area, count, replacement=True, generator=generator)
    uv = torch.rand((count, 2), device=vertices.device, dtype=vertices.dtype, generator=generator)
    root = uv[:, 0].sqrt()
    barycentric = torch.stack([1-root, root*(1-uv[:, 1]), root*uv[:, 1]], -1)
    return (tri[chosen] * barycentric[:, :, None]).sum(1)


def nearest_distance(a, b, chunk=512):
    return torch.cat([torch.cdist(part, b).min(-1).values for part in a.split(chunk)])
