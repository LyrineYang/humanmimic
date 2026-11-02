"""Bounded inference-time LEAP reference corrections, using public state only.

Fingertip collision proxies and damped IK are a local planner, not full-hand
collision certification or a learned grasp policy. Actual physics must decide
success, including failures for unreachable or poorly initialized references.
"""
import torch
from r4_hand_model import HandModel


class ReferenceController:
    def __init__(self, hand, prior, config, device):
        self.hand, self.cfg, self.device = HandModel(hand, device), config, device
        self.coarse = self.hand.tensor(prior["vertices_object_m"])
        self.initial = self.hand.tensor(prior["T_world_object_initial"])
        self.generator = torch.Generator(device=device).manual_seed(config["seed"])

    def forces(self, observation):
        result = {}
        for packet in observation["tactile"]:
            if not packet["valid"] or observation["time_s"]-packet["time_s"] > .1+1e-9:
                continue
            force = self.hand.tensor(packet["force_sensor_n"]).reshape(-1, 3)
            saturated = torch.tensor(packet["saturated"], device=self.device, dtype=torch.bool)
            magnitude = force.norm(dim=-1)
            # Rectifying and summing noise in every taxel invents a contact.
            # Apply the calibrated per-taxel contact threshold before aggregating.
            active = magnitude >= self.cfg["taxel_contact_threshold_n"]
            result[packet["sensor_id"]] = {"norm_n": float(magnitude[active].sum()), "saturated": bool(saturated.any())}
        return result

    def command(self, observation, reference, belief, geometry=True, force_feedback=True, release=False):
        q = self.hand.tensor(reference["joint_position"])
        wrist = self.hand.tensor(reference["T_world_wrist"])
        readings = self.forces(observation)
        emergency = any(value["norm_n"] > self.cfg["force_stop_n"] or value["saturated"] for value in readings.values())
        diagnostic = {"geometry_feedback": geometry, "force_feedback": force_feedback, "emergency": emergency,
                      "collision_scope": "four fingertip center proxies; actual-world full collision evaluation remains required"}
        if emergency:
            # Same abort across G/F groups. Do not continue closing or moving wrist.
            return {"joint_position": observation["joint_position_rad"], "T_world_wrist": reference["T_world_wrist"],
                    "abort_episode": True, "diagnostic": diagnostic}
        if release or belief is None or belief.get("prediction_age_s", 0) > self.cfg["maximum_prediction_age_s"]:
            return {"joint_position": q.tolist(), "T_world_wrist": wrist.tolist(), "abort_episode": False,
                    "diagnostic": {**diagnostic, "correction": "reference_only_release_or_missing_belief"}}
        null = self.hand.tensor(belief["null_projector"])
        modes = len(belief["shape_basis"][0])
        last_pose = len(null)-modes-7
        if (null.diag()[last_pose:last_pose+6] > .25).any():
            return {"joint_position": q.tolist(), "T_world_wrist": wrist.tolist(), "abort_episode": False,
                    "diagnostic": {**diagnostic, "correction": "reference_only_unobservable_pose"}}
        pose = self.hand.tensor(belief["T_world_object"][-1])
        grasped = (readings.get("th", {}).get("norm_n", 0) >= self.cfg["minimum_contact_n"] and
                   any(readings.get(f, {}).get("norm_n", 0) >= self.cfg["minimum_contact_n"] for f in ["if", "mf", "rf"]))
        if grasped and "desired_object_position" in reference:
            error = self.hand.tensor(reference["desired_object_position"])-pose[:3, 3]
            correction = error*min(1., self.cfg["maximum_wrist_residual_m"]/max(float(error.norm()), 1e-12))
            wrist = wrist.clone()
            wrist[:3, 3] += correction
        vertices = self.hand.tensor(belief["vertices_object_m"]) if geometry else self.coarse
        normals = self.hand.tensor(belief["normals_object"])
        # Same coarse correspondence construction across G0/G1; geometry switch
        # changes positions, not controller weights, force bounds or observations.
        fingertips = self.hand.forward(q, wrist)[:, :3, 3]
        local = (fingertips-pose[:3, 3])@pose[:3, :3]
        distance, indices = torch.cdist(local, self.coarse).min(-1)
        if not readings or (not any(v["norm_n"] >= self.cfg["minimum_contact_n"] for v in readings.values()) and
                                bool((distance > self.cfg["maximum_local_distance_m"]).all())):
            return {"joint_position": q.tolist(), "T_world_wrist": wrist.tolist(), "abort_episode": False,
                    "diagnostic": {**diagnostic, "correction": "reference_only_outside_local_contact_region"}}
        desired = vertices[indices]@pose[:3, :3].T+pose[:3, 3]
        # Retargeting controls sensor centers, not object-contact points. Preserve
        # the coarse reference offset so an internal sensor site is never forced
        # onto the object surface as if it were a tactile pixel.
        coarse_world = self.coarse[indices]@pose[:3, :3].T+pose[:3, 3]
        desired = fingertips+(desired-coarse_world)
        adjusted = self.hand.ik(q, wrist, desired, self.cfg["maximum_joint_residual_rad"], self.cfg["ik_iterations"])
        candidates = [q, adjusted]
        for _ in range(self.cfg["candidate_count"]-2):
            noise = torch.randn(q.shape, device=self.device, dtype=q.dtype, generator=self.generator)*.01
            candidates.append(torch.clamp(adjusted+noise, min=q-self.cfg["maximum_joint_residual_rad"], max=q+self.cfg["maximum_joint_residual_rad"]))
        baseline_phi = ((local-vertices[indices])*normals[indices]).sum(-1)
        candidates = torch.stack(candidates)
        tip = self.hand.forward(candidates, wrist)[..., :3, 3]
        candidate_local = (tip-pose[:3, 3])@pose[:3, :3]
        phi = ((candidate_local-vertices[indices])*normals[indices]).sum(-1)
        # Relative penetration change avoids treating internal site centers as skin.
        unsafe = (phi-baseline_phi < -self.cfg["maximum_proxy_penetration_m"]).any(-1)
        unsafe |= ((candidates < self.hand.ranges[:, 0]) | (candidates > self.hand.ranges[:, 1])).any(-1)
        scores = (tip-desired).square().sum((-1, -2))+1e-5*(candidates-q).square().sum(-1)
        scores = torch.where(unsafe, torch.full_like(scores, torch.inf), scores)
        selected = candidates[int(scores.argmin())] if torch.isfinite(scores).any() else q
        if force_feedback:
            delta = torch.zeros_like(selected)
            for i, finger in enumerate(["if", "mf", "rf", "th"]):
                reading = readings.get(finger)
                if reading is not None and reading["norm_n"] >= self.cfg["minimum_contact_n"]:
                    correction = self.cfg["force_gain_rad_per_n"]*(self.cfg["contact_force_target_n"]-reading["norm_n"])
                    # Flexion joints only; do not drive abduction from scalar force.
                    for joint in ([4*i, 4*i+2, 4*i+3] if i < 3 else [14, 15]):
                        delta[joint] = correction
            selected = selected+delta
        selected = torch.clamp(selected, min=q-self.cfg["maximum_joint_residual_rad"], max=q+self.cfg["maximum_joint_residual_rad"])
        selected = torch.clamp(selected, min=self.hand.ranges[:, 0], max=self.hand.ranges[:, 1])
        final_local = (self.hand.forward(selected, wrist)[:, :3, 3]-pose[:3, 3])@pose[:3, :3]
        final_phi = ((final_local-vertices[indices])*normals[indices]).sum(-1)
        if (final_phi-baseline_phi < -self.cfg["maximum_proxy_penetration_m"]).any():
            selected = q
            diagnostic["force_proposal_rejected_by_proxy"] = True
        diagnostic.update(candidates=len(candidates), candidate_rejections=int((~torch.isfinite(scores)).sum()),
                          contact_indices=indices.tolist(), joint_residual_max_rad=float((selected-q).abs().max()))
        return {"joint_position": selected.tolist(), "T_world_wrist": wrist.tolist(), "abort_episode": False, "diagnostic": diagnostic}
