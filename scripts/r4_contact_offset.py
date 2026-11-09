"""CUDA belief for one task-normal support offset, not full object geometry.

Only calibrated plane position, hand encoders and a contact-event force enter.
Object pose/size, simulator contacts and evaluation truth are not inputs.
"""
from dataclasses import dataclass
import math
import torch


@dataclass(frozen=True)
class ContactObservation:
    grasp_id: str
    event_id: str
    hand_coordinate_m: float
    plane_coordinate_m: float
    normal: tuple
    force_n: float


class ContactOffsetMemory:
    def __init__(self, grasp_id, prior_m=.025, sigma_m=.01, normal=(1., 0., 0.)):
        if not torch.cuda.is_available():
            raise RuntimeError('Contact estimation requires CUDA; no CPU fallback')
        self.grasp_id, self.normal = grasp_id, tuple(normal)
        self.mean = torch.tensor(prior_m, device='cuda', dtype=torch.float64)
        self.variance = torch.tensor(sigma_m**2, device='cuda', dtype=torch.float64)
        self.events = []
        self.valid = False

    def update(self, observation):
        if not isinstance(observation, ContactObservation):
            raise TypeError('Only public ContactObservation is accepted')
        if observation.grasp_id != self.grasp_id:
            raise ValueError('Grasp changed; construct a new prior before probing')
        if tuple(observation.normal) != self.normal:
            return False  # A different normal cannot identify this scalar.
        if observation.event_id in self.events:
            return False  # Correlated frames are one event, never new evidence.
        values = (observation.hand_coordinate_m, observation.plane_coordinate_m, observation.force_n)
        if not all(math.isfinite(x) for x in values) or not .2 <= observation.force_n <= 2.:
            return False
        measurement = self.mean.new_tensor(observation.plane_coordinate_m - observation.hand_coordinate_m)
        noise = self.mean.new_tensor(.0003**2)
        gain = self.variance / (self.variance + noise)
        self.mean = self.mean + gain * (measurement - self.mean)
        self.variance = ((1 - gain) * self.variance).clamp_min(noise)
        self.events.append(observation.event_id)
        self.valid = True
        return True

    def target(self, object_edge_goal_m, grasp_id):
        if grasp_id != self.grasp_id or not self.valid:
            raise ValueError('No valid contact memory for this grasp')
        return self.mean.new_tensor(object_edge_goal_m) - self.mean

    def snapshot(self):
        return {'grasp_id': self.grasp_id, 'normal': list(self.normal),
                'mean_m': self.mean.item(), 'sigma_m': self.variance.sqrt().item(),
                'events': list(self.events), 'valid': self.valid,
                'scope': 'Local support offset along one normal; fixed grasp and orientation'}
