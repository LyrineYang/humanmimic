"""CUDA task-sensitive touch selection from estimated geometry and information.

The task Jacobian is differentiated through an explicit grasp/support surrogate.
It is NOT hand-entered, a true simulator gradient, or demonstrated task value.
E3 must test whether its predicted value transfers to actual T1/T2 execution.
"""
import torch
from r4_belief import so3


class ProbeSelector:
    def __init__(self, device, config):
        if device.type != "cuda":
            raise RuntimeError("Probe scoring requires CUDA")
        self.device, self.cfg = device, config
        self.count, self.elapsed, self.used = 0, 0., set()
        self.generator = torch.Generator(device=device).manual_seed(config["seed"])

    def select(self, belief, contact_indices, fingertip_positions, task, strategy, calibrated_bound=False, current_forces_n=None):
        if strategy not in {"no_probe", "random", "uniform", "global_uncertainty", "task_risk_reduction"}:
            raise ValueError("Unknown probe strategy")
        if strategy == "no_probe":
            return {"selected": None, "reason": "no_probe_control"}
        if self.count >= self.cfg["maximum_contacts"] or self.elapsed+self.cfg["duration_s"] > self.cfg["maximum_time_s"]:
            return {"selected": None, "reason": "contact_or_time_budget"}
        if not calibrated_bound:
            return {"selected": None, "reason": "force_prediction_bound_requires_calibration"}
        if current_forces_n is None or len(current_forces_n) != len(fingertip_positions):
            return {"selected": None, "reason": "current_finger_loads_required"}
        tensor = lambda x: torch.tensor(x, device=self.device, dtype=torch.float64)
        vertices, normals = tensor(belief["vertices_object_m"]), tensor(belief["normals_object"])
        basis = tensor(belief["shape_basis"])
        pose = tensor(belief["T_world_object"][-1])
        covariance, null = tensor(belief["covariance"]), tensor(belief["null_projector"])
        size, modes = len(covariance), basis.shape[1]
        pose_index, shape_index = size-modes-7, size-modes-1
        scales = belief["parameter_scales"]
        # A bounded decision prior, explicitly separate from measured covariance.
        # Null uncertainty is still unbounded in the exported estimator belief.
        decision_covariance = covariance+null*self.cfg["null_decision_variance"]
        contacts = torch.tensor(contact_indices, device=self.device, dtype=torch.long)
        support = int((vertices@pose[:3, :3].T)[:, 2].argmin())

        def geometry(x):
            mesh = vertices+normals*(basis@x[shape_index:-1]*scales["shape_m"])[:, None]
            r = so3(x[pose_index+3:pose_index+6]*scales["rotation_rad"])@pose[:3, :3]
            t = pose[:3, 3]+x[pose_index:pose_index+3]*scales["translation_m"]
            return mesh@r.T+t

        def feature(x):
            mesh = geometry(x)
            grip = mesh[contacts].mean(0)
            span = (mesh[contacts[0]]-mesh[contacts[-1]]).norm().reshape(1)
            # T2 also depends on the support height. T1 retains grasp lever arms.
            height = mesh[support, 2].reshape(1) if task == "precision_place" else grip[2:3]
            return torch.cat([grip, span, height])

        zero = torch.zeros(size, device=self.device, dtype=vertices.dtype, requires_grad=True)
        task_jacobian = torch.autograd.functional.jacobian(feature, zero, vectorize=True).detach()
        candidate_ids = torch.linspace(0, len(vertices)-1, min(len(vertices), self.cfg["candidate_count"]), device=self.device).long().unique()
        world = geometry(zero).detach()
        tips = tensor(fingertip_positions)
        options = []
        for vertex in candidate_ids.tolist():
            distances = (tips-world[vertex]).norm(dim=-1)
            finger, distance = int(distances.argmin()), float(distances.min())
            if distance > self.cfg["maximum_reach_m"] or vertex in self.used:
                continue
            if current_forces_n[finger] is None:
                continue
            normal = normals[vertex]@pose[:3, :3].T
            measurement = lambda x: ((geometry(x)[vertex]-world[vertex])*normal).sum()
            h = torch.autograd.functional.jacobian(measurement, zero, vectorize=True).detach()
            sigma_surface = (h@decision_covariance@h).clamp_min(0).sqrt()
            predicted_force = current_forces_n[finger] + (self.cfg["maximum_step_m"]+2*float(sigma_surface))/self.cfg["minimum_compliance_m_per_n"]
            if predicted_force > self.cfg["maximum_force_n"]:
                continue
            cross = decision_covariance@h
            reduction = torch.outer(cross, cross)/(h@cross+self.cfg["measurement_sigma_m"]**2)
            task_gain = torch.trace(task_jacobian@reduction@task_jacobian.T)
            global_gain = torch.trace(reduction)
            # Common candidate pool uses physical feasibility and information.
            # Do not give random/global baselines the task-sensitive prefilter.
            if float(global_gain) <= 1e-15 or (strategy == "task_risk_reduction" and float(task_gain) <= 1e-15):
                continue
            if strategy == "random":
                score = float(torch.rand((), device=self.device, generator=self.generator))
            elif strategy == "uniform":
                score = float((world[vertex]-world[sorted(self.used)]).norm(dim=-1).min()) if self.used else 0.
            elif strategy == "global_uncertainty":
                score = float(global_gain)/self.cfg["duration_s"]
            else:
                score = float(task_gain)/self.cfg["duration_s"]
            options.append({"vertex": vertex, "finger": finger, "score": score,
                "task_variance_reduction": float(task_gain), "global_variance_reduction": float(global_gain),
                "predicted_force_upper_n": predicted_force, "position_world_m": world[vertex].tolist(),
                "normal_world": normal.tolist(), "duration_s": self.cfg["duration_s"],
                "step_m": self.cfg["maximum_step_m"]})
        selected = max(options, key=lambda value: value["score"]) if options else None
        return {"selected": selected, "feasible_candidates": len(options), "reason": "candidate" if selected else "no_safe_positive_gain_candidate",
                "task_jacobian": task_jacobian.tolist(), "surrogate": "grasp center/span and estimated support height",
                "null_decision_prior": self.cfg["null_decision_variance"], "predicted_gain_is_actual_gain": False}

    def consume(self, selection):
        if selection["selected"] is None:
            return
        item = selection["selected"]
        self.count += 1
        self.elapsed += item["duration_s"]
        self.used.add(item["vertex"])
