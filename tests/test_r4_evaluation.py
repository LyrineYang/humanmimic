"""Evaluate adversarial state histories; these are not physical success evidence."""
import copy
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from r4_evaluation import evaluate


def example():
    config = json.loads((Path(__file__).resolve().parents[1] / "configs/r4-stage1.json").read_text())
    task = {"task": "precision_place", "initial_position": [0, 0, .025],
            "target_position": [.08, 0, .025], "target_quaternion": [1, 0, 0, 0]}
    actual = np.zeros((201, 8))
    actual[:, 0] = np.arange(201) / 50
    actual[:, 1:4] = task["target_position"]
    actual[:, 4] = 1
    lifted = (actual[:, 0] >= .2) & (actual[:, 0] <= 2.4)
    actual[lifted, 3] = .11
    return actual, lifted.copy(), lifted.copy(), task, config


def test_released_stable_placement_is_evaluable():
    inputs = example()
    passed, metrics = evaluate(*inputs, penetration=0.)
    assert passed and metrics["released_during_settle"]


def test_held_at_target_is_not_placed():
    actual, opposition, contact, task, config = example()
    contact[:] = True
    passed, metrics = evaluate(actual, opposition, contact, task, config, 0.)
    assert not passed and not metrics["released_during_settle"]


def test_lift_without_opposition_cannot_pass():
    actual, opposition, contact, task, config = example()
    assert not evaluate(actual, np.zeros_like(opposition), contact, task, config, 0.)[0]


def test_final_frame_cannot_hide_settle_drift():
    actual, opposition, contact, task, config = example()
    actual[-5, 1] += .006
    assert not evaluate(actual, opposition, contact, task, config, 0.)[0]


def test_penetration_failure_is_not_hidden_by_precision():
    assert not evaluate(*example(), penetration=.0021)[0]
