import copy
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from r4_multimodal import (fit_contact_patch, score_touches, static_friction_lower_bound,
                           validate_measurement)


def packet():
    return {"schema_version": 1, "kind": "force", "source": "simulated_sensor",
            "sensor_id": "index_pad", "time_s": 1., "received_time_s": 1.01,
            "valid": True, "T_world_sensor": np.eye(4).tolist(),
            "units": {"length": "m", "force": "N", "time": "s"}, "force_sensor_n": [0., 0., 1.]}


def test_declared_measurement_is_accepted():
    assert validate_measurement(packet(), 1.02)


def test_privileged_object_state_cannot_enter_sensor_packet():
    p = packet(); p["object_pose_gt"] = [0]*7
    with pytest.raises(ValueError): validate_measurement(p, 1.02)


def test_future_packet_is_rejected():
    with pytest.raises(ValueError): validate_measurement(packet(), 1.)


def test_missing_and_delayed_packets_are_not_negative_contact():
    p = packet(); p["valid"] = False; p.pop("force_sensor_n")
    assert not validate_measurement(p, 1.02)
    assert not validate_measurement(packet(), 1.3)


def test_force_is_not_a_surface_measurement():
    p = packet(); p["surface_points_sensor_m"] = [[0, 0, 0]]
    with pytest.raises(ValueError): validate_measurement(p, 1.02)


def test_nonrigid_sensor_frame_is_rejected():
    p = packet(); p["T_world_sensor"][0][0] = -1
    with pytest.raises(ValueError): validate_measurement(p, 1.02)


def test_patch_identifies_shape_pose_and_compliance_with_excitation():
    force = np.linspace(.2, 1.5, 16)
    measured = .003 + .002 + .001*force
    result = fit_contact_patch(measured, force, .0001, pose_observation_m=.002, pose_sigma_m=.0001)
    assert result["status"] == "passed"
    assert result["estimate"]["shape_offset_m"] == pytest.approx(.003, abs=1e-6)
    assert result["estimate"]["effective_compliance_m_per_n"] == pytest.approx(.001, abs=1e-6)


def test_pose_shape_gauge_is_not_hidden_by_optimizer_success():
    force = np.linspace(.2, 1.5, 16)
    result = fit_contact_patch(.005+.001*force, force, .0001)
    assert result["status"] == "unobservable" and result["estimate"] is None


def test_constant_load_cannot_identify_compliance():
    result = fit_contact_patch(np.full(8, .006), np.ones(8), .0001, pose_observation_m=.002, pose_sigma_m=.0001)
    assert result["status"] == "unobservable"


def candidates():
    return [{"id": "critical_patch", "measurement_jacobian": [1, 0], "noise_variance": 1e-6,
             "cost_seconds": 1., "predicted_force_n": 1., "reachable": True},
            {"id": "uncertain_backside", "measurement_jacobian": [0, 1], "noise_variance": 1e-6,
             "cost_seconds": 1., "predicted_force_n": 1., "reachable": True}]


def test_task_information_differs_from_global_uncertainty():
    assert score_touches(np.diag([4e-6, 100e-6]), [[1, 0]], candidates())["selected"] == "critical_patch"


def test_force_bound_overrides_information_gain():
    c = candidates(); c[0]["predicted_force_n"] = 2.1; c[1]["reachable"] = False
    assert score_touches(np.diag([4e-6, 100e-6]), [[1, 0]], c)["selected"] is None


def test_zero_task_information_does_not_spend_contact_budget():
    assert score_touches(np.diag([4e-6, 100e-6]), [[1, 0]], candidates()[1:])["selected"] is None


def test_sticking_does_not_reveal_exact_friction():
    r = static_friction_lower_bound([1, 2], [.4, 1.])
    assert r["mu_lower"] == .5 and r["mu_upper"] is None
