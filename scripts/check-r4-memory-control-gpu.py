#!/usr/bin/env python3
"""GPU checks for memory, LEAP FK/IK, control switches and probe abstention.

MuJoCo is used only as a reference for known hand FK. All estimator/planner and
numerical comparisons run on CUDA; no fallback or manipulation-success claim.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import mujoco
import torch
from r4_contract import JOINT_NAMES, sha256, write_json
from r4_cuda import require_cuda
from r4_gpu_fixtures import fixture
from r4_hand_model import export_hand, HandModel
from r4_memory import EvidenceMemory
from r4_control import ReferenceController
from r4_probe import ProbeSelector
from r4_pose_tracker import track_pose
from r4_scene import make_scene


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--belief", type=Path, required=True, help="Independent P2 GPU fixture result")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    device, gpu = require_cuda()
    root = Path(__file__).resolve().parents[1]
    cfg = json.loads((root/"configs/r4-p1p2.json").read_text())
    policy = json.loads((root/"configs/r4-control.json").read_text())
    physics = json.loads((root/"configs/r4-stage1.json").read_text())["physics"]
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output/"manifest.json", {"status": "running", "gpu": gpu, "belief_sha256": sha256(args.belief),
        "source_sha256": {p.name: sha256(p) for p in Path(__file__).parent.glob("*r4*.py")}})
    checks = {}
    payload, _ = fixture(device, cfg["estimator"])
    memory = EvidenceMemory(device, "fixture", "episode-a")
    for i in range(48):
        frame = copy.deepcopy(payload["frames"][i % 8])
        frame["time_s"] = i*.1
        if frame["vision"]:
            frame["vision"]["time_s"] = i*.1
        for packet in frame["tactile"]:
            packet["time_s"] = packet["received_time_s"] = i*.1
        memory.append(frame, "fixture", "episode-a")
    count = len(memory.entries)
    memory.append(frame, "fixture", "episode-a")
    checks["duplicates_do_not_add_information"] = len(memory.entries) == count and memory.rejected_duplicates == 1
    selected = memory.select("diverse")
    checks["bounded_persistent_history"] = len(memory.entries) <= 32 and len(selected) <= 8 and selected[0]["time_s"] < memory.select("recent")[0]["time_s"] and selected[-1]["time_s"] == frame["time_s"]
    try:
        memory.append(frame, "different_object", "episode-a")
        checks["identity_switch_rejected"] = False
    except ValueError:
        checks["identity_switch_rejected"] = True
    belief = json.loads(args.belief.read_text())["beliefs"][-1]
    memory.commit(belief)
    prediction = memory.predict(belief["time_s"]+1)
    old_cov = torch.tensor(belief["covariance"], device=device)
    new_cov = torch.tensor(prediction["covariance"], device=device)
    checks["missing_data_inflates_uncertainty"] = bool((new_cov.diag() > old_cov.diag()).all()) and not prediction["actionable"]
    scene = {"initial_position": [.3, 0, .04], "collision_representation": "analytic_convex_parts",
             "collision_parts": [{"type": "box", "size": [.02, .02, .02]}]}
    hand_path = Path(os.environ["R4_DATA_ROOT"])/"assets/leap_hand"
    model = mujoco.MjModel.from_xml_string(make_scene(hand_path, scene, physics, sensor_config=cfg["sensor"]))
    data = mujoco.MjData(model)
    known = export_hand(model)
    hand = HandModel(known, device)
    wrist = torch.eye(4, device=device, dtype=torch.float64)
    wrist[:3, 3] = torch.tensor([0., 0., .18], device=device)
    q = torch.tensor([.3, 0, .3, .3]*3+[.3]*4, device=device, dtype=torch.float64)
    wrist_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "wrist_free")
    wadr = model.jnt_qposadr[wrist_joint]
    data.qpos[wadr:wadr+7] = [0, 0, .18, 1, 0, 0, 0]
    for index, name in enumerate(JOINT_NAMES):
        joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        data.qpos[model.jnt_qposadr[joint]] = float(q[index])
    mujoco.mj_forward(model, data)
    actual = []
    for finger in ["if", "mf", "rf", "th"]:
        site = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, f"r4_{finger}_sensor")
        actual.append(data.site_xpos[site].tolist())
    actual = torch.tensor(actual, device=device, dtype=torch.float64)
    predicted = hand.forward(q, wrist)[:, :3, 3]
    fk_error = float((actual-predicted).abs().max())
    checks["cuda_FK_matches_known_LEAP"] = fk_error < 1e-7
    batch = hand.forward(torch.stack([q, q+.01]), wrist)
    checks["batched_FK_matches_individual"] = bool(torch.allclose(batch[0], hand.forward(q, wrist), atol=1e-10) and
                                                   torch.allclose(batch[1], hand.forward(q+.01, wrist), atol=1e-10))
    desired_q = q+.01
    target = hand.forward(desired_q, wrist)[:, :3, 3]
    solved = hand.ik(q, wrist, target)
    checks["cuda_IK_reduces_tip_error"] = bool((hand.forward(solved, wrist)[:, :3, 3]-target).norm() < (predicted-target).norm())
    auto_jac=torch.autograd.functional.jacobian(lambda x:hand.forward(x,wrist)[:,:3,3],q,vectorize=True)
    checks['analytic_hand_jacobian_matches_autodiff']=bool(torch.allclose(hand.position_jacobian(q,wrist),auto_jac,atol=1e-10,rtol=1e-10))
    offset=hand.tensor([.003,-.004,.005])
    def surface_positions(value):
        transforms=hand.forward(value,wrist)
        return (transforms[:,:3,:3]@offset)+transforms[:,:3,3]
    surface_auto=torch.autograd.functional.jacobian(surface_positions,q,vectorize=True)
    checks['surface_contact_jacobian_matches_autodiff']=bool(torch.allclose(hand.position_jacobian(q,wrist,surface_positions(q)),surface_auto,atol=1e-10,rtol=1e-10))
    from r4_sensor_bridge import SensorBridge
    from r4_tactile_geometry import HandTactileSurface
    calibration=SensorBridge(model,cfg['sensor']).calibration
    support_model=HandTactileSurface(calibration,cfg['estimator'],device)
    support={f:support_model.calibrate_surface(p['triangles_sensor_m']) for f,p in calibration['pads'].items()}
    supported=ReferenceController(known,payload['prior'],policy['control'],device,support=support)
    region=support['mf'];index=int(torch.where(region['valid'])[0][0])
    force=torch.zeros((192,3),device=device,dtype=torch.float64);force[index,2]=.3
    packet={'sensor_id':'mf','valid':True,'time_s':0.,'force_sensor_n':force.reshape(12,16,3).tolist(),
            'saturated':torch.zeros((12,16),device=device,dtype=torch.bool).tolist(),'T_world_sensor':wrist.tolist()}
    contact=supported.forces({'time_s':0.,'tactile':[packet]})['mf']['contact_world_m']
    checks['force_contact_uses_public_taxel_hand_surface']=bool(torch.allclose(hand.tensor(contact),region['points'][index]+wrist[:3,3],atol=1e-10))
    normal=region['normals'][index];axis=hand.tensor([1.,.3,.2]);tangent=axis-normal*(axis@normal);tangent/=tangent.norm()
    force[index]=-.7*normal+.4*tangent;packet['force_sensor_n']=force.reshape(12,16,3).tolist()
    resolved=supported.forces({'time_s':0.,'tactile':[packet]})['mf']
    checks['normal_force_excludes_tangential_load']=abs(resolved['normal_load_n']-.7)<1e-10 and resolved['norm_n']>.8
    controller = ReferenceController(known, payload["prior"], policy["control"], device)
    direction=hand.tensor([1.,0.,0.])
    loading=controller.force_adjustment(q,wrist,{'mf':{'norm_n':.3,'force_world_n':[.3,0.,0.]}})
    unloading=controller.force_adjustment(q,wrist,{'mf':{'norm_n':1.7,'force_world_n':[1.7,0.,0.]}})
    checks['force_feedback_moves_against_load_when_under_target']=float(direction@auto_jac[1]@loading)<0
    checks['force_feedback_moves_with_load_when_over_target']=float(direction@auto_jac[1]@unloading)>0
    obs = copy.deepcopy(payload["frames"][-1])
    obs["joint_position_rad"] = q.tolist()
    noisy = copy.deepcopy(obs)
    noisy["tactile"][0]["force_sensor_n"] = torch.full((16, 12, 3), .005, device=device).tolist()
    checks["taxel_noise_does_not_create_contact"] = controller.forces(noisy)[noisy["tactile"][0]["sensor_id"]]["norm_n"] == 0
    obs["tactile"][0]["force_sensor_n"] = [[[0, 0, .3]]]
    reference = {"joint_position": q.tolist(), "T_world_wrist": wrist.tolist()}
    baseline = controller.command(obs, reference, belief, geometry=False, force_feedback=False)
    controlled = controller.command(obs, reference, belief, geometry=True, force_feedback=True)
    checks["G0F0_preserves_reference"] = bool(torch.allclose(torch.tensor(baseline["joint_position"], device=device), q.float(), atol=1e-6))
    checks["bounded_control_residual"] = float((torch.tensor(controlled["joint_position"], device=device)-q).abs().max()) <= .060001
    missing = controller.command(obs,reference,None,geometry=False,force_feedback=True)
    missing_off = controller.command(obs,reference,None,geometry=False,force_feedback=False)
    released = controller.command(obs,reference,None,geometry=False,force_feedback=True,release=True)
    checks['force_feedback_without_object_belief'] = float((torch.tensor(missing['joint_position'],device=device)-q).abs().max())>1e-5
    checks['missing_belief_F0_preserves_reference'] = bool(torch.allclose(torch.tensor(missing_off['joint_position'],device=device),q.float(),atol=1e-6))
    checks['release_disables_force_closing'] = bool(torch.allclose(torch.tensor(released['joint_position'],device=device),q.float(),atol=1e-6))
    unknown=copy.deepcopy(belief);unknown['null_projector']=torch.eye(len(belief['covariance']),device=device).tolist()
    unobserved=controller.command(obs,reference,unknown,geometry=True,force_feedback=True)
    checks['force_feedback_survives_unobservable_pose']=bool(torch.allclose(torch.tensor(unobserved['joint_position'],device=device),torch.tensor(missing['joint_position'],device=device),atol=1e-6))
    integral=ReferenceController(known,payload['prior'],policy['control'],device)
    first=integral.command(obs,reference,None,geometry=False,force_feedback=True)
    duplicate=integral.command(obs,reference,None,geometry=False,force_feedback=True)
    checks['duplicate_timestamp_does_not_integrate_force']=first['joint_position']==duplicate['joint_position']
    later=copy.deepcopy(obs)
    for i in range(300):
        later['time_s']=obs['time_s']+(i+1)*.02
        for packet in later['tactile']:packet['time_s']=later['time_s']
        accumulated=integral.command(later,reference,None,geometry=False,force_feedback=True)
    checks['accumulated_force_remains_bounded']=float((hand.tensor(accumulated['joint_position'])-q).abs().max())<=.06000001
    integral.command(later,reference,None,geometry=False,force_feedback=True,release=True)
    checks['release_resets_force_memory']=bool((integral.force_residual==0).all())
    obs["tactile"][0]["force_sensor_n"] = [[[0, 0, 3.]]]
    checks["common_force_abort"] = all(controller.command(obs, reference, belief, geometry=g, force_feedback=f)["abort_episode"] for g in [False, True] for f in [False, True])
    selector = ProbeSelector(device, policy["probe"])
    probe_belief = copy.deepcopy(belief)
    size = len(belief["covariance"])
    # Declared moderate-uncertainty decision fixture, not an empirical posterior.
    # 1e-8 produced a task gain below the existing meaningful-gain cutoff;
    # abstaining there was correct. Keep the cutoff and test a useful query.
    probe_belief["covariance"] = (torch.eye(size, device=device, dtype=torch.float64)*1e-5).tolist()
    probe_belief["null_projector"] = torch.zeros((size, size), device=device).tolist()
    vertices = torch.tensor(belief["vertices_object_m"], device=device, dtype=torch.float64)
    pose = torch.tensor(belief["T_world_object"][-1], device=device, dtype=torch.float64)
    indices = [0, len(vertices)//3, 2*len(vertices)//3, len(vertices)-1]
    tips = (vertices[indices]@pose[:3, :3].T+pose[:3, 3]).tolist()
    denied = selector.select(probe_belief, indices, tips, "precision_place", "task_risk_reduction")
    checks["uncalibrated_force_bound_abstains"] = denied["selected"] is None
    selected_probe = selector.select(probe_belief, indices, tips, "precision_place", "task_risk_reduction", calibrated_bound=True, current_forces_n=[0.]*4)
    checks["task_J_from_model_is_finite"] = bool(torch.isfinite(torch.tensor(selected_probe["task_jacobian"], device=device)).all())
    checks["safe_positive_gain_candidate"] = selected_probe["selected"] is not None and selected_probe["selected"]["predicted_force_upper_n"] <= 2
    loaded = selector.select(probe_belief, indices, tips, "precision_place", "task_risk_reduction", calibrated_bound=True, current_forces_n=[1.9]*4)
    checks["probe_force_bound_includes_existing_load"] = loaded["selected"] is None
    tiny = copy.deepcopy(probe_belief)
    tiny["covariance"] = (torch.eye(size, device=device, dtype=torch.float64)*1e-8).tolist()
    task_choice = selector.select(tiny, indices, tips, "precision_place", "task_risk_reduction", calibrated_bound=True, current_forces_n=[0.]*4)
    global_choice = selector.select(tiny, indices, tips, "precision_place", "global_uncertainty", calibrated_bound=True, current_forces_n=[0.]*4)
    checks["global_baseline_not_filtered_by_task_gain"] = task_choice["selected"] is None and global_choice["selected"] is not None
    probe_belief["covariance"] = torch.zeros((size, size), device=device).tolist()
    no_gain = selector.select(probe_belief, indices, tips, "precision_place", "task_risk_reduction", calibrated_bound=True, current_forces_n=[0.]*4)
    checks["zero_gain_abstains"] = no_gain["selected"] is None
    track_frame = copy.deepcopy(payload["frames"][-1])
    track_frame["time_s"] += .1
    track_frame["vision"]["time_s"] = track_frame["time_s"]
    points = torch.tensor(track_frame["vision"]["points_world_m"], device=device, dtype=torch.float64)
    points[:, 0] += .001
    track_frame["vision"]["points_world_m"] = points.tolist()
    tracked = track_pose(memory.predict(track_frame["time_s"]), track_frame, device)
    checks["pose_tracking_between_shape_updates"] = tracked is not None and abs(tracked["T_world_object"][-1][0][3]-belief["T_world_object"][-1][0][3]-.001) < .001
    write_json(args.output/"result.json", {"status": "passed" if all(checks.values()) else "failed", "checks": checks,
        "fk_max_error_m": fk_error, "gpu": gpu, "memory": memory.summary(selected), "probe": selected_probe,
        "scope": "GPU module checks; not E2/E3 manipulation success, full collision certification or uncertainty calibration"})
    manifest = json.loads((args.output/"manifest.json").read_text())
    manifest.update(status="complete", result_sha256=sha256(args.output/"result.json"))
    write_json(args.output/"manifest.json", manifest)
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
