"""Persistent, inspectable multimodal evidence memory; no learned WSM weights.

Keep unique measurements and an object-coordinate belief separately. Historical
evidence may be relinearized in a later solve, but its old posterior covariance
is NEVER multiplied into that solve as another independent observation.
"""
import copy
import hashlib
import json
import torch
from r4_public import validate_frame


class EvidenceMemory:
    def __init__(self, device, object_id, episode_id, capacity=32, window=8, force_threshold_n=.05, tactile_mode="force"):
        if device.type != "cuda":
            raise RuntimeError("Multimodal evidence selection requires CUDA")
        if not object_id or not episode_id or not 8 <= capacity <= 64 or window != 8:
            raise ValueError("Declare identity and bounded memory")
        self.device, self.capacity, self.window = device, capacity, window
        self.force_threshold_n = force_threshold_n
        self.tactile_mode = tactile_mode
        self.reset(object_id, episode_id)

    def reset(self, object_id, episode_id):
        self.object_id, self.episode_id = object_id, episode_id
        self.entries, self.seen, self.pose_cache = [], {}, {}
        self.last_time, self.belief_time, self.belief = -1., None, None
        self.rejected_duplicates, self.discarded = 0, 0

    def descriptor(self, frame):
        tensor = lambda x: torch.tensor(x, device=self.device, dtype=torch.float64)
        visual = frame["vision"]
        normal = torch.zeros(3, device=self.device, dtype=torch.float64)
        center = torch.zeros_like(normal)
        if visual and visual["points_world_m"]:
            normal = tensor(visual["normals_world"]).mean(0)
            center = tensor(visual["points_world_m"]).mean(0) / .1
        forces = torch.zeros(4, device=self.device, dtype=torch.float64)
        fingers = ["if", "mf", "rf", "th"]
        for packet in frame["tactile"]:
            if packet["valid"] and frame["time_s"]-packet["time_s"] <= .1+1e-9:
                if self.tactile_mode == "binary":
                    forces[fingers.index(packet["sensor_id"])] = tensor(packet["contact_bits"]).sum()
                else:
                    force = tensor(packet["force_sensor_n"]).reshape(-1, 3)
                    magnitude = force.norm(dim=-1)
                    forces[fingers.index(packet["sensor_id"])] = magnitude[magnitude >= self.force_threshold_n].sum()/2
        # Executed/commanded joint history is evidence, not an inferred object pose.
        return torch.cat([normal, center, forces, tensor(frame["joint_position_rad"])/3.14159,
                          tensor(frame["joint_target_rad"])/3.14159])

    def append(self, frame, object_id, episode_id):
        if (object_id, episode_id) != (self.object_id, self.episode_id):
            raise ValueError("Object/episode changed; explicit memory reset required")
        identity = float(frame["time_s"])
        digest = hashlib.sha256(json.dumps(frame, sort_keys=True, allow_nan=False).encode()).hexdigest()
        if identity in self.seen:
            if self.seen[identity] != digest:
                raise ValueError("Conflicting replacement of an already observed frame")
            self.rejected_duplicates += 1
            return False
        validate_frame(frame, self.last_time, tactile_mode=self.tactile_mode)
        self.seen[identity] = digest
        self.last_time = identity
        self.entries.append((copy.deepcopy(frame), self.descriptor(frame)))
        if len(self.entries) > self.capacity:
            # Keep initial calibration pair and recent eight. Remove the most
            # redundant interior evidence according to its adjacent descriptors.
            descriptors = torch.stack([entry[1] for entry in self.entries])
            candidates = torch.arange(2, len(self.entries)-8, device=self.device)
            redundancy = (descriptors[candidates]-descriptors[candidates-1]).norm(dim=-1) + (descriptors[candidates]-descriptors[candidates+1]).norm(dim=-1)
            remove = int(candidates[redundancy.argmin()])
            removed_time = self.entries[remove][0]["time_s"]
            del self.entries[remove]
            self.pose_cache.pop(removed_time, None)
            self.discarded += 1
        return True

    def select(self, mode="diverse"):
        if mode not in {"single", "recent", "diverse"}:
            raise ValueError("Unknown memory ablation")
        if mode == "single":
            return [copy.deepcopy(self.entries[-1][0])]
        if mode == "recent" or len(self.entries) <= self.window:
            return [copy.deepcopy(frame) for frame, _ in self.entries[-self.window:]]
        chosen = set(range(len(self.entries)-4, len(self.entries)))
        descriptor = torch.stack([entry[1] for entry in self.entries])
        while len(chosen) <= self.window-2:
            candidates = [i for i in range(len(self.entries)-1) if i not in chosen and i+1 not in chosen
                          and self.entries[i+1][0]["time_s"]-self.entries[i][0]["time_s"] <= .10000001]
            if not candidates:
                break
            indices = torch.tensor(candidates, device=self.device)
            selected = torch.tensor(sorted(chosen), device=self.device)
            novelty = torch.cdist(descriptor[indices], descriptor[selected]).min(-1).values
            index = candidates[int(novelty.argmax())]
            chosen.update([index, index+1])
        return [copy.deepcopy(self.entries[i][0]) for i in sorted(chosen)]

    def commit(self, belief):
        if not belief.get("state_updated"):
            return
        self.belief = copy.deepcopy(belief)
        self.belief_time = belief["time_s"]
        for timestamp, pose in zip(belief["window_times_s"], belief["T_world_object"]):
            self.pose_cache[timestamp] = pose

    def predict(self, now_s):
        """Constant-pose prediction with growing uncertainty, never fake depth."""
        if self.belief is None:
            return None
        if now_s < self.belief_time:
            raise ValueError("Cannot predict backward into an unseen evidence timeline")
        result = copy.deepcopy(self.belief)
        elapsed = now_s-self.belief_time
        covariance = torch.tensor(result["covariance"], device=self.device, dtype=torch.float64)
        # Normalized parameter units. This is a declared process prior to calibrate;
        # it does not turn a null direction into measured information.
        covariance += torch.eye(len(covariance), device=self.device, dtype=covariance.dtype)*elapsed*.1
        result["covariance"] = covariance.tolist()
        result["prediction_age_s"] = elapsed
        result["time_s"] = now_s
        result["state_updated"] = False
        result["inference_status"] = "predicted_only"
        result["actionable"] = elapsed <= .3
        return result

    def summary(self, selected):
        return {"kind": "explicit_evidence_and_belief_memory", "object_id": self.object_id,
                "episode_id": self.episode_id, "stored_frames": len(self.entries), "seen_frames": len(self.seen),
                "selected_times_s": [frame["time_s"] for frame in selected], "duplicate_frames_ignored": self.rejected_duplicates,
                "evicted_frames": self.discarded, "posterior_reused_as_measurement": False,
                "learned_latent": None, "pose_prior": "constant pose plus uncertainty growth; no learned dynamics claim"}
