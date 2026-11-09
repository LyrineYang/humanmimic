#!/usr/bin/env python3
"""CUDA archive audit; independently reconstruct final free-object task metric."""
import argparse
import csv
import json
from pathlib import Path

from r4_campaign import digest, write


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    import numpy as np
    import torch
    import mujoco
    if not torch.cuda.is_available():
        raise RuntimeError('GPU evidence required')
    T = lambda x: torch.as_tensor(x, device='cuda', dtype=torch.float64)
    summary = json.loads((args.run/'result.json').read_text())
    checks = []
    lateral = {'baseline': [], 'contact': []}
    probe_force_peaks = []
    for trial in summary['trials']:
        folder = args.run/trial['condition']['id']
        prior = json.loads((folder/'shared-prior.json').read_text())
        baseline = np.load(folder/'baseline-states.npz')
        contact = np.load(folder/'contact-states.npz')
        common = np.load(folder/'common-states.npz')
        fork = np.load(folder/'fork-state.npz')
        for key in common.files:
            assert torch.equal(T(baseline[key][0]), T(contact[key][0])), ('unpaired fork', folder, key)
            assert torch.equal(T(baseline[key][0]), T(common[key][-1])), ('prefix differs', folder, key)
        assert digest(folder/'common-states.npz') == trial['common_states_sha256']
        assert digest(folder/'policy-input-actions.npz') == trial['policy_input_actions_sha256']
        assert digest(folder/'fork-state.npz') == trial['fork_sha256']
        with (folder/'common-public.csv').open() as f:
            sensors = list(csv.DictReader(f))
        forces = T([[float(row[k]) for k in ['force_x_n', 'force_y_n', 'force_z_n']] for row in sensors if row['phase'] in ['probe', 'probe-retract']])
        peak = torch.linalg.vector_norm(forces, dim=1).max().item()
        assert abs(peak-trial['probe_peak_n']) < 1e-9
        probe_force_peaks.append(peak)
        model = mujoco.MjModel.from_binary_path(str(folder/'model.mjb'))
        data = mujoco.MjData(model)
        gid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, '004_sugar_box/entity_contact0')
        bid = int(model.geom_bodyid[gid])
        assert model.body_jntnum[bid] == 6, 'Object is not the original freely moving six-joint body'
        for i in range(model.neq):
            if model.eq_type[i] in (mujoco.mjtEq.mjEQ_WELD, mujoco.mjtEq.mjEQ_CONNECT):
                assert bid not in (model.eq_obj1id[i], model.eq_obj2id[i]), 'Rigid object coupling'
        assert abs(float(model.geom_size[gid, 0])-(.021748+trial['condition']['halfwidth_delta_mm']/1000)) < 1e-10
        for name, state in [('common', common), ('baseline', baseline), ('contact', contact)]:
            for key in state.files:
                assert torch.isfinite(T(state[key])).all(), (folder, name, key)
            assert (torch.diff(T(state['time'])) > 0).all(), (folder, name, 'time')
        for name, state in [('baseline', baseline), ('contact', contact)]:
            for key in state.files:
                if key == 'time': data.time = float(state[key][-1])
                else: getattr(data, key)[:] = state[key][-1]
            mujoco.mj_forward(model, data)
            R = T(data.geom_xmat[gid].reshape(3, 3))
            edge = float(data.geom_xpos[gid, 0])+(R[0].abs()*T(model.geom_size[gid])).sum().item()
            error = abs(edge-trial['goal_edge_x_m'])
            lateral[name].append(abs(float(data.geom_xpos[gid, 1])-prior['object_pose'][1]))
            assert abs(error-trial['variants'][name]['edge_error_m']) < 1e-10, ('metric mismatch', folder, name)
            with (folder/(name+'-public.csv')).open() as f:
                public = list(csv.DictReader(f))
            assert len(public) == len(state['time'])
            assert not any('object' in k or 'true' in k or 'contact_count' in k for k in public[0]), 'Evaluator truth in adapter sensor log'
            checks.append({'condition': trial['condition']['id'], 'arm': name,
                           'status': 'passed', 'restored_edge_error_m': error, 'steps': len(public)})
    trials = summary['trials']
    metrics = {}
    both_valid = [r for r in trials if all(v['valid'] for v in r['variants'].values())]
    for arm in ['baseline', 'contact']:
        metrics[arm] = {key: T([r['variants'][arm][key] for r in trials]).mean().item()
                        for key in ['edge_error_m', 'penalized_error_m', 'prerelease_edge_error_m', 'orientation_error_deg', 'drift_m']}
        metrics[arm]['y_error_m'] = T(lateral[arm]).mean().item()
        metrics[arm]['both_valid_edge_mae_m'] = T([r['variants'][arm]['edge_error_m'] for r in both_valid]).mean().item() if both_valid else None
        metrics[arm]['failure_counts_nonexclusive'] = {key: sum(not r['variants'][arm][key] for r in trials) for key in ['reachable', 'lower_reachable', 'detached', 'table_supported']}
        metrics[arm]['failure_counts_nonexclusive']['orientation'] = sum(r['variants'][arm]['orientation_error_deg'] > 10 for r in trials)
        metrics[arm]['failure_counts_nonexclusive']['drift'] = sum(r['variants'][arm]['drift_m'] > .002 for r in trials)
    by_width = {}
    for width in sorted({r['condition']['halfwidth_delta_mm'] for r in trials}):
        rows = [r for r in trials if r['condition']['halfwidth_delta_mm'] == width]
        by_width[str(width)] = {arm: {'raw_mae_m': T([r['variants'][arm]['edge_error_m'] for r in rows]).mean().item(),
                                     'penalized_mae_m': T([r['variants'][arm]['penalized_error_m'] for r in rows]).mean().item(),
                                     'valid': sum(r['variants'][arm]['valid'] for r in rows)} for arm in ['baseline', 'contact']}
    write(args.output, {'status': 'passed', 'checks': checks, 'paired_forks': len(trials),
                        'metrics': metrics, 'both_valid_pairs': len(both_valid), 'by_width': by_width,
                        'maximum_probe_3d_force_n': max(probe_force_peaks),
                        'cuda': torch.cuda.get_device_name(), 'rendered': False, 'new_experiment_samples': 0,
                        'scope': 'Archive equality, finite states, monotonic time, free object, no rigid coupling, final metric reconstruction; not a replacement for task success'})


if __name__ == '__main__':
    main()
