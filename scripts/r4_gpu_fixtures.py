"""Independent analytic CUDA fixtures for P2; NOT LEAP manipulation evidence."""
import copy
import torch
from r4_belief import so3
from r4_gpu_geometry import ellipsoid


def fixture(device, config, seed=1101, constant_force=False, missing_vision=False, dropout=False, saturated=False):
    generator = torch.Generator(device=device).manual_seed(seed)
    tensor = lambda x: torch.tensor(x, device=device, dtype=torch.float64)
    radii, coarse = tensor([.03, .024, .020]), tensor([.029, .025, .021])
    v, n, faces = ellipsoid(coarse)
    prior = {"schema_version": 2, "role": "coarse_estimate", "source": "synthetic_fixture",
        "vertices_object_m": v.tolist(), "normals_object": n.tolist(), "faces": faces.tolist(),
        "roi_vertex_indices": list(range(len(v))), "T_world_object_initial": torch.eye(4, device=device, dtype=torch.float64).tolist(),
        "initial_time_s": 0.0, "compliance_initial_m_per_n": .001}
    triangle = [[[-.003, -.003, -.001], [.003, .003, -.001], [.003, -.003, -.001]],
                [[-.003, -.003, -.001], [-.003, .003, -.001], [.003, .003, -.001]]]
    calibration = {"schema_version": 2, "role": "hand_sensor_calibration", "hand": "leap_right",
        "size": [1, 1], "fov_deg": [3, 3], "gamma": 0, "surface_margin_m": .00005,
        "pads": {finger: {"triangles_sensor_m": triangle} for finger in ["if", "mf", "rf", "th"]},
        "threshold_n": .05, "max_age_s": .1, "noise_std_n": .005, "saturation_n": 5,
        "force_convention": "force_on_hand_in_sensor_xyz", "calibration_status": "synthetic_fixture"}
    frames, truth = [], []
    compliance = .0008
    for i in range(8):
        now = i * .1
        translation = tensor([.002+.0003*i, -.001, .0005*i])
        rotation = so3(tensor([.01, -.02, .015*i]))
        directions = torch.randn((512, 3), device=device, dtype=torch.float64, generator=generator)
        directions /= directions.norm(dim=-1, keepdim=True)
        surface = directions * radii
        normals = surface / radii.square()
        normals /= normals.norm(dim=-1, keepdim=True)
        points = surface @ rotation.T + translation
        points += torch.randn(points.shape, device=device, dtype=torch.float64, generator=generator)*.0001
        measured = torch.eye(4, device=device, dtype=torch.float64)
        measured[:3, :3] = so3(torch.randn((3,), device=device, dtype=torch.float64, generator=generator)*.002) @ rotation
        measured[:3, 3] = translation + torch.randn((3,), device=device, dtype=torch.float64, generator=generator)*.0002
        force = .8 if constant_force else .2 + i*.2
        transform = torch.eye(4, device=device, dtype=torch.float64)
        transform[:3, :3] = rotation
        pad = torch.stack([radii[0]*0, radii[0]*0, radii[2] - compliance*force + .001])
        transform[:3, 3] = pad @ rotation.T + translation
        force_noise = float(torch.randn((), device=device, generator=generator))*.005
        packet = {"sensor_id": "if", "time_s": now, "received_time_s": now,
                  "valid": not dropout, "reason": "fixture_dropout" if dropout else "ok",
                  "T_world_sensor": transform.tolist(), "force_sensor_n": None if dropout else [[[0, 0, force+force_noise]]],
                  "saturated": None if dropout else [[saturated]]}
        vision = None if missing_vision else {"time_s": now, "source": "synthetic_fixture", "points_world_m": points.tolist(),
            "normals_world": (normals@rotation.T).tolist(), "sigma_m": .0001,
            "pose_measurement": {"T_world_object": measured.tolist(), "translation_sigma_m": .0002,
                                 "rotation_sigma_rad": .002, "source": "synthetic_fixture"}}
        frames.append({"schema_version": 2, "role": "observation", "split": "debug", "source": "synthetic_fixture",
            "time_s": now, "joint_position_rad": [0.]*16, "joint_target_rad": [0.]*16, "tactile": [packet], "vision": vision})
        actual = torch.eye(4, device=device, dtype=torch.float64)
        actual[:3, :3], actual[:3, 3] = rotation, translation
        truth.append(actual.tolist())
    payload = {"calibration": calibration, "prior": prior, "frames": frames, "config": copy.deepcopy(config),
               "modality": "VF", "ablation": "joint", "seed": seed, "occlusion": 0.0}
    evaluation = {"role": "evaluation_only", "radii_m": radii.tolist(), "poses": truth, "compliance_m_per_n": compliance}
    return payload, evaluation
