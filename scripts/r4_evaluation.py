"""Development task evaluation from actual physics samples, never references."""
import numpy as np
from scipy.spatial.transform import Rotation


def evaluate(actual, opposing, touching_hand, task, config, penetration):
    rules = config["tasks"]
    duration = actual[-1, 0]
    settle = rules["precision_place"]["settle_seconds"]
    tail_mask = actual[:, 0] >= max(0, duration - settle) - 1e-9
    tail = actual[tail_mask]
    errors = np.linalg.norm(tail[:, 1:4] - task["target_position"], axis=1)
    goal = Rotation.from_quat(np.asarray(task["target_quaternion"])[[1, 2, 3, 0]])
    angular = (goal * Rotation.from_quat(tail[:, 4:8][:, [1, 2, 3, 0]]).inv()).magnitude() * 180 / np.pi
    lifted = actual[:, 3] >= task["initial_position"][2] + rules["lift_hold"]["lift_height_m"]
    longest, start = 0., None
    for t, above in zip(actual[:, 0], lifted):
        if above:
            if start is None:
                start = t
            longest = max(longest, t - start)
        else:
            start = None
    opposition = float(np.mean(np.asarray(opposing)[lifted])) if np.any(lifted) else 0.
    stable_lift = longest >= rules["lift_hold"]["hold_seconds"] - 1e-9 and opposition >= rules["lift_hold"]["opposing_contact_fraction"]
    released = duration >= settle and not np.any(np.asarray(touching_hand)[tail_mask])
    precision = np.max(errors) <= rules["precision_place"]["position_tolerance_m"] and np.max(angular) <= rules["precision_place"]["rotation_tolerance_degrees"]
    valid = penetration <= rules["maximum_penetration_m"]
    passed = bool(stable_lift and valid and (task["task"] == "lift_hold" or (precision and released)))
    return passed, {"final_position_error_m": float(errors[-1]), "settle_max_position_error_m": float(np.max(errors)),
                    "final_rotation_error_degrees": float(angular[-1]), "settle_max_rotation_error_degrees": float(np.max(angular)),
                    "penalized_position_error_m": float(errors[-1]) if passed else rules["failure_position_penalty_m"],
                    "lift_hold_seconds": float(longest), "max_penetration_m": float(penetration),
                    "opposing_contact_fraction_when_lifted": opposition, "released_during_settle": bool(released)}
