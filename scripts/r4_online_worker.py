#!/usr/bin/env python3
"""Persistent public-only CUDA estimation/control process, line-delimited JSON."""
import copy
import json
from pathlib import Path
import sys
import time
import torch
from r4_belief import BeliefEstimator
from r4_control import ReferenceController
from r4_cuda import require_cuda
from r4_estimator_worker import install_read_guard
from r4_memory import EvidenceMemory
from r4_probe import ProbeSelector
from r4_pose_tracker import track_pose
from r4_public import keys, validate_frame


def main():
    device, gpu = require_cuda()
    torch.manual_seed(1101)
    torch.use_deterministic_algorithms(True)
    torch.optim.Adam([torch.zeros(1, device=device, requires_grad=True)])
    header = json.loads(sys.stdin.readline())
    keys(header, {"calibration", "prior", "hand", "estimator", "policy", "mission", "group", "probe_strategy"})
    mission, policy = header["mission"], header["policy"]
    keys(mission, {"role", "object_id", "episode_id", "task", "goal_position", "transport_start_s", "release_start_s"})
    if mission["role"] != "public_task_goal" or mission["task"] not in {"lift_hold", "precision_place"}:
        raise ValueError("Require a public task goal, not an evaluation scene")
    group = header["group"]
    if group not in {"G0F0", "G1F0", "G0F1", "G1F1"}:
        raise ValueError("Invalid causal control group")
    execution = policy["execution"]
    if execution["updates_per_episode"]*execution["steps_per_update"] > 200 or execution["maximum_wall_s"] > 300:
        raise ValueError("Episode optimization budget exceeded")
    estimator = BeliefEstimator(header["prior"], header["calibration"], header["estimator"], device)
    if policy["control"]["taxel_contact_threshold_n"] != header["calibration"]["threshold_n"]:
        raise ValueError("Control contact threshold must match sensor calibration")
    memory = EvidenceMemory(device, mission["object_id"], mission["episode_id"], policy["memory"]["capacity"],
                            force_threshold_n=header["calibration"]["threshold_n"])
    controller = ReferenceController(header["hand"], header["prior"], policy["control"], device, support=estimator.support)
    probe = ProbeSelector(device, policy["probe"])
    install_read_guard()
    try:
        (Path(__file__).resolve().parents[1]/"PLAN.md").read_text()
    except PermissionError:
        pass
    else:
        raise RuntimeError("Online worker failed to deny project data")
    print(json.dumps({"ready": True, "gpu": gpu, "read_guard_denied_project_data": True}), flush=True)
    deadline = time.monotonic()+execution["maximum_wall_s"]
    pending, last_keyframe, last_fit, updates = [], -1., -1., 0
    belief, active_probe, previous_time = None, None, -1.
    for line in sys.stdin:
        message = json.loads(line)
        keys(message, {"observation", "reference"})
        observation, reference = message["observation"], message["reference"]
        validate_frame(observation, previous_time)
        now, previous_time = observation["time_s"], observation["time_s"]
        if time.monotonic() > deadline or now > execution["maximum_episode_s"]:
            raise TimeoutError("Online episode resource limit reached")
        pending.extend(observation["tactile"])
        if now-last_keyframe >= .1-1e-9:
            frame = copy.deepcopy(observation)
            frame["tactile"], pending = pending, []
            memory.append(frame, mission["object_id"], mission["episode_id"])
            last_keyframe = now
        update = None
        if (len(memory.entries) >= 8 and updates < execution["updates_per_episode"]
                and now-last_fit >= 1/execution["estimation_hz"]-1e-9):
            selected = memory.select(policy["memory"]["mode"])
            estimator.pose_initializations = memory.pose_cache
            update = estimator.fit(selected, steps=execution["steps_per_update"], wall_deadline=deadline)
            update["geometry_time_s"] = now
            update["memory"] = memory.summary(selected)
            memory.commit(update)
            updates += 1
            last_fit = now
        elif observation["vision"] is not None and memory.belief is not None:
            tracked = track_pose(memory.predict(now), observation, device)
            if tracked is not None:
                memory.commit(tracked)
        belief = memory.predict(now)
        release = now >= mission["release_start_s"]
        reference = copy.deepcopy(reference)
        if now >= mission["transport_start_s"]:
            reference["desired_object_position"] = mission["goal_position"]
        command = controller.command(observation, reference, belief, geometry=group[1] == "1", force_feedback=group[3] == "1", release=release)
        selection = None
        if (belief and not command["abort_episode"] and now+policy["probe"]["duration_s"] <= mission["transport_start_s"]
                and active_probe is None and "contact_indices" in command["diagnostic"]):
            wrist = controller.hand.tensor(observation.get("T_world_wrist", reference["T_world_wrist"]))
            q = controller.hand.tensor(observation["joint_position_rad"])
            sites = controller.hand.forward(q, wrist)
            # Known hand-surface points, not sensor centers or simulator contacts.
            vertex = controller.hand.tensor(belief["vertices_object_m"])
            pose = controller.hand.tensor(belief["T_world_object"][-1])
            world_object = vertex@pose[:3, :3].T+pose[:3, 3]
            tips = []
            for i, finger in enumerate(["if", "mf", "rf", "th"]):
                region = estimator.support[finger]
                local = region["points"][region["valid"]]
                if not len(local):
                    tips.append(sites[i, :3, 3])
                    continue
                world = local@sites[i, :3, :3].T+sites[i, :3, 3]
                tips.append(world[torch.cdist(world, world_object).min(-1).values.argmin()])
            calibrated = policy["probe"]["compliance_bound_status"] == "calibrated_development_bound"
            current_loads = controller.forces(observation)
            selection = probe.select(belief, command["diagnostic"]["contact_indices"], torch.stack(tips).tolist(),
                                     mission["task"], header["probe_strategy"], calibrated_bound=calibrated,
                                     current_forces_n=[current_loads.get(f, {}).get("norm_n") for f in ["if", "mf", "rf", "th"]])
            if selection["selected"]:
                probe.consume(selection)
                active_probe = {**selection["selected"], "start_s": now, "initial_pad": tips[selection["selected"]["finger"]].tolist()}
        if active_probe and not release and not command["abort_episode"]:
            elapsed = now-active_probe["start_s"]
            if elapsed >= active_probe["duration_s"]:
                active_probe = None
            else:
                fraction = min(elapsed/(active_probe["duration_s"]/2), (active_probe["duration_s"]-elapsed)/(active_probe["duration_s"]/2))
                wrist = controller.hand.tensor(command["T_world_wrist"])
                q = controller.hand.tensor(command["joint_position"])
                targets = controller.hand.forward(q, wrist)[:, :3, 3].detach().clone()
                displacement = controller.hand.tensor(active_probe["position_world_m"])-controller.hand.tensor(active_probe["initial_pad"])
                displacement -= controller.hand.tensor(active_probe["normal_world"])*active_probe["step_m"]
                targets[active_probe["finger"]] += displacement*fraction
                limit = policy["control"]["maximum_joint_residual_rad"]
                proposal = controller.hand.ik(q, wrist, targets, limit, 2)
                original = controller.hand.tensor(reference["joint_position"])
                # Probe plus geometry/force correction share one residual budget.
                proposal = original + (proposal-original).clamp(-limit, limit)
                command["joint_position"] = torch.maximum(torch.minimum(proposal, controller.hand.ranges[:, 1]), controller.hand.ranges[:, 0]).tolist()
        command["diagnostic"].update(updates=updates, probe_attempts=probe.count, probe_time_s=probe.elapsed,
                                     memory_frames=len(memory.entries), no_realtime_claim=True)
        print(json.dumps({"command": command, "belief_update": update, "probe_selection": selection}, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
