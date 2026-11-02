#!/usr/bin/env python3
"""CUDA regressions for the four server-research review findings.

Analytic development fixtures only. No CPU fallback or manipulation claim.
"""
import argparse
import copy
import json
from pathlib import Path
import torch
from r4_belief import BeliefEstimator
from r4_belief_evaluation import sample_truth
from r4_contract import sha256, write_json
from r4_cuda import require_cuda
from r4_gpu_fixtures import fixture

ACTIVE_OUTPUT = None


def equal_data(left, right):
    if isinstance(left, torch.Tensor):
        return isinstance(right, torch.Tensor) and torch.equal(left, right)
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(equal_data(left[k], right[k]) for k in left)
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(equal_data(a, b) for a, b in zip(left, right))
    return left == right


def main():
    global ACTIVE_OUTPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--extended", action="store_true", help="Also exercise full VB fitting and visual-only moving-pose preparation")
    args = parser.parse_args()
    device, gpu = require_cuda()
    cfg = json.loads((Path(__file__).resolve().parents[1]/"configs/r4-p1p2.json").read_text())["estimator"]
    args.output.mkdir(parents=True, exist_ok=False)
    ACTIVE_OUTPUT = args.output
    write_json(args.output/"manifest.json", {"status": "running", "gpu": gpu,
        "sources_sha256": {p.name: sha256(p) for p in Path(__file__).parent.glob("*r4*.py")}})
    checks, details = {}, {}
    def union_case(name, parts, outer_kind, outer_size, rotation=None):
        scene = {"geometry_role": "evaluation_only", "split": "debug", "collision_parts": parts}
        points = sample_truth(scene, device, torch.Generator(device=device).manual_seed(71101), count=2048)
        if rotation is not None:
            points = points@rotation
        size = torch.tensor(outer_size, device=device, dtype=torch.float64)
        # Independent outer solid: joined identical sections form one box/cylinder.
        excess = points.abs()-size if outer_kind == "box" else torch.stack([points[:, :2].norm(dim=-1)-size[0], points[:, 2].abs()-size[1]], -1)
        error = (excess.clamp_min(0).norm(dim=-1)+excess.max(-1).values.clamp_max(0)).abs()
        checks[name] = bool((error < 1e-8).all())
        details[name] = {"incorrect_samples": int((error >= 1e-8).sum()), "maximum_outer_surface_error_m": float(error.max())}
    boxes = [{"type": "box", "size": [.02, .02, .01], "position": [0, 0, z]} for z in [-.01, .01]]
    union_case("joined_boxes_exclude_internal_interface", boxes, "box", [.02, .02, .02])
    cylinders = [{"type": "cylinder", "size": [.02, .01], "position": [0, 0, z]} for z in [-.01, .01]]
    union_case("joined_cylinders_exclude_internal_caps", cylinders, "cylinder", [.02, .02])
    duplicates = [{"type": "box", "size": [.02, .02, .02]}]*2
    union_case("duplicate_exposed_faces_retained", duplicates, "box", [.02, .02, .02])
    from r4_belief import so3
    turn = so3(torch.tensor([.6, 0., 0.], device=device, dtype=torch.float64))
    rotated = copy.deepcopy(boxes)
    for part in rotated:
        part["position"] = (torch.tensor(part["position"], device=device, dtype=torch.float64)@turn.T).tolist()
        angle = torch.tensor(.3, device=device, dtype=torch.float64)
        part["quaternion"] = [float(angle.cos()), float(angle.sin()), 0., 0.]
    union_case("rotated_joined_boxes", rotated, "box", [.02, .02, .02], rotation=turn)
    payload, _ = fixture(device, cfg)
    changed = copy.deepcopy(payload["frames"])
    for frame in changed:
        # Exactly the same binary contact and health, opposite direction and
        # a different amplitude. VB has no right to distinguish these records.
        force = torch.tensor(frame["tactile"][0]["force_sensor_n"], device=device, dtype=torch.float64)
        frame["tactile"][0]["force_sensor_n"] = (-1.3*force).tolist()
    vb = BeliefEstimator(payload["prior"], payload["calibration"], cfg, device, "VB")
    before, after = vb.prepare(payload["frames"]), vb.prepare(changed)
    checks["VB_fixed_bits_ignore_force_amplitude_direction"] = equal_data(before, after)
    details["VB_contact_rows"] = [len(before["contacts"]), len(after["contacts"])]
    vf = BeliefEstimator(payload["prior"], payload["calibration"], cfg, device, "VF")
    checks["VF_retains_force_direction_information"] = not equal_data(vf.prepare(payload["frames"]), vf.prepare(changed))
    shape = BeliefEstimator(payload["prior"], payload["calibration"], cfg, device, "VF", "shape_only")
    result = shape.fit(payload["frames"], steps=24)
    write_json(args.output/"shape-measured-pose.json", result)
    poses = torch.tensor(result["T_world_object"], device=device, dtype=torch.float64)
    measured = torch.tensor([f["vision"]["pose_measurement"]["T_world_object"] for f in payload["frames"]], device=device, dtype=torch.float64)
    checks["shape_only_freezes_each_independent_measurement"] = bool(torch.allclose(poses, measured, atol=1e-10, rtol=0))
    details["frozen_pose_max_error"] = float((poses-measured).abs().max())
    if args.extended:
        from r4_modalities import observation_view
        from r4_memory import EvidenceMemory
        projected = observation_view(payload["frames"], payload["calibration"], "VB", device)
        checks["VB_boundary_removes_all_force_vectors"] = all("force_sensor_n" not in p and "contact_bits" in p for f in projected for p in f["tactile"])
        checks["VB_has_no_continuous_force_tracks"] = not before["force_tracks"]
        # Force-dependent ranking must also disappear when a packet exceeds the
        # point budget, not only for the original single-taxel fixture.
        grid_cal, small_cfg = copy.deepcopy(payload["calibration"]), copy.deepcopy(cfg)
        grid_cal["size"], small_cfg["maximum_points"] = [4, 4], 32
        grid_a, grid_b = copy.deepcopy(payload["frames"]), copy.deepcopy(payload["frames"])
        loads = torch.zeros((16, 3), device=device, dtype=torch.float64)
        loads[:, 2] = torch.linspace(.2, .8, 16, device=device)
        for a, b in zip(grid_a, grid_b):
            a["tactile"][0]["force_sensor_n"] = loads.reshape(4, 4, 3).tolist()
            b["tactile"][0]["force_sensor_n"] = loads.flip(0).reshape(4, 4, 3).tolist()
            a["tactile"][0]["saturated"] = b["tactile"][0]["saturated"] = [[False]*4 for _ in range(4)]
        limited = BeliefEstimator(payload["prior"], grid_cal, small_cfg, device, "VB")
        left, right = limited.prepare(grid_a), limited.prepare(grid_b)
        checks["VB_budget_selection_ignores_load_ranking"] = equal_data(left, right) and len(left["contacts"]) == 8 and all(len(c[3]) == 1 for c in left["contacts"])
        # V's persistent keyframe selector must not retain tactile information.
        view_a = observation_view(grid_a, grid_cal, "V", device)
        view_b = observation_view(grid_b, grid_cal, "V", device)
        ma, mb = EvidenceMemory(device, "fixture", "V"), EvidenceMemory(device, "fixture", "V")
        for a, b in zip(view_a, view_b):
            ma.append(a, "fixture", "V")
            mb.append(b, "fixture", "V")
        checks["V_memory_has_no_tactile_information"] = equal_data(ma.entries, mb.entries) and all(not frame["tactile"] for frame in ma.select())
        # Same solve, not merely the preprocessing: all numerical output must
        # remain identical when only continuous forces change in binary mode.
        from r4_estimator_worker import replay
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("review_p2", Path(__file__).with_name("check-r4-p2-gpu.py"))
        helper = module_from_spec(spec)
        spec.loader.exec_module(helper)
        binary = copy.deepcopy(payload)
        binary.update(modality="VB", memory_mode="diverse", object_id="fixture", episode_id="binary-invariance")
        binary["config"]["steps"] = 24
        one = replay(binary, device)
        binary["frames"] = changed
        two = replay(binary, device)
        checks["VB_fit_and_memory_invariance"] = helper.fingerprint(one) == helper.fingerprint(two)
        write_json(args.output/"VB-original.json", one)
        write_json(args.output/"VB-force-changed.json", two)
        visual = copy.deepcopy(payload)
        visual["ablation"] = "shape_only"
        for frame in visual["frames"]:
            del frame["vision"]["pose_measurement"]
        visual["config"]["steps"] = 80
        result = replay(visual, device)
        write_json(args.output/"shape-visual-pose.json", result)
        belief = result["beliefs"][-1]
        checks["shape_only_without_anchor_has_visual_pose_provenance"] = belief.get("independent_pose", {}).get("source") == "visual_only_coarse_registration" and belief["state_updated"]
        checks["shape_only_preparation_counted_in_budget"] = result["gradient_steps"] <= 80 and belief.get("independent_pose", {}).get("gradient_steps", 0) > 0
        blank = copy.deepcopy(payload["frames"])
        for frame in blank:
            frame["vision"] = None
        missing = BeliefEstimator(payload["prior"], payload["calibration"], cfg, device, "VF", "shape_only").fit(blank, steps=24)
        checks["shape_only_missing_pose_rejects_static_fallback"] = not missing["state_updated"] and missing.get("reason") == "independent_pose_unavailable"
        write_json(args.output/"shape-missing-pose.json", missing)
    write_json(args.output/"result.json", {"status": "passed" if all(checks.values()) else "failed", "checks": checks,
        "details": details, "gpu": gpu, "scope": "review-specific analytic GPU checks; not manipulation acceptance", "heldout_used": False})
    manifest = json.loads((args.output/"manifest.json").read_text())
    manifest.update(status="complete", result_sha256=sha256(args.output/"result.json"))
    write_json(args.output/"manifest.json", manifest)
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        if ACTIVE_OUTPUT is not None:
            path = ACTIVE_OUTPUT/"manifest.json"
            manifest = json.loads(path.read_text()) if path.exists() else {}
            manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
            write_json(path, manifest)
        raise
