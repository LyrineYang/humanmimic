#!/usr/bin/env python3
"""Frozen ViViDex grasp + paired, one-contact placement residual (CUDA only).

Native Adroit and free rigid object. A calibrated external probe measures a
support coordinate. The estimator never sees collision geometry or contacts.
The evaluator does; public and private logs are deliberately separate.
"""
import argparse
import csv
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

from r4_campaign import digest, write
from r4_contact_offset import ContactObservation, ContactOffsetMemory


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--checkpoint-dir', type=Path, required=True)
    ap.add_argument('--protocol', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    spec = json.loads(args.protocol.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.source.resolve()))
    os.environ['MUJOCO_GL'] = 'egl'
    os.environ['WANDB_MODE'] = 'offline'
    import numpy as np
    import torch
    import mujoco
    import yaml
    from omegaconf import OmegaConf
    from stable_baselines3 import PPO
    from hand_imitation.env.environments.gym_wrapper import GymWrapper
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required; no CPU inference or estimator fallback')
    torch.set_num_threads(4)
    T = lambda v: torch.as_tensor(v, dtype=torch.float64, device='cuda')
    policy = PPO.load(str(args.checkpoint_dir/'restore_checkpoint.zip'), device='cuda')
    policy.policy.eval()
    assert next(policy.policy.parameters()).is_cuda
    params = OmegaConf.create(yaml.safe_load((args.checkpoint_dir/'exp_config.yaml').read_text())['params'])
    envmod = importlib.import_module('hand_imitation.env.environments.create_env')
    original_builder = envmod.physics_from_mjcf
    nominal = T([.021748, .047081, .0880075])
    identity = {'entry_sha256': digest(__file__), 'protocol_sha256': digest(args.protocol),
                'checkpoint_sha256': digest(args.checkpoint_dir/'restore_checkpoint.zip'),
                'config_sha256': digest(args.checkpoint_dir/'exp_config.yaml'),
                'source_commit': subprocess.check_output(['git', '-C', str(args.source), 'rev-parse', 'HEAD'], text=True).strip(),
                'source_diff': subprocess.check_output(['git', '-C', str(args.source), 'diff'], text=True),
                'torch': torch.__version__, 'mujoco': mujoco.__version__, 'gpu': torch.cuda.get_device_name(),
                'training': False, 'heldout': False, 'video': False,
                'scope': 'Privileged-state pretrained grasp; nominal pose prior shared; unknown local box extent; scripted residual/lower/release; external calibrated probe'}
    write(args.output/'identity.json', identity)
    write(args.output/'protocol.json', spec)
    results = []

    for condition in spec['conditions']:
        seed = int(condition['seed'])
        delta = float(condition['halfwidth_delta_mm'])/1000
        trial = args.output / condition['id']
        trial.mkdir()
        # Only scene construction and evaluator know the changed shape.
        def instrument_scene(scene):
            model = scene.mjcf_model
            matches = [g for g in model.find_all('geom') if g.full_identifier == '004_sugar_box/entity_contact0']
            if len(matches) != 1:
                raise ValueError('Unexpected collision geometry: '+str([g.full_identifier for g in model.find_all('geom') if 'entity_contact' in g.full_identifier]))
            shape = matches[0]
            size = np.array(shape.size, copy=True)
            if not np.allclose(size, nominal.cpu().numpy(), atol=1e-7):
                raise ValueError('Nominal sugar-box geometry changed')
            size[0] += delta
            shape.size = size
            # Keep rendered shape honest even though no image is a policy input.
            for mesh in model.find_all('mesh'):
                if mesh.full_identifier == '004_sugar_box/004_sugar_box':
                    scale = np.ones(3) if mesh.scale is None else np.array(mesh.scale, copy=True)
                    scale[0] *= size[0]/.021748
                    mesh.scale = scale
            stage = model.worldbody.add('body', name='probe_stage', mocap=True, pos=[2, 2, 2])
            plate = stage.add('body', name='probe_plate')
            probe_geom = plate.add('geom', name='probe_contact', type='box', size=[.001, .015, .015], mass=.01,
                      rgba=[.1, .6, .9, 1], friction=[.05, .005, .0001])
            site = plate.add('site', name='probe_site', size=[.002], pos=[0, 0, 0])
            model.sensor.add('force', name='probe_force', site=site)
            # Calibrated measurement fixture and support plane. Explicit pairs
            # avoid inheriting the object's 3mm / negative-solref collision law.
            # Native hand-object contact parameters and pretrained weights stay.
            for name, other in [('probe_pair', probe_geom), ('support_pair', model.find('geom', 'table_contact'))]:
                model.contact.add('pair', name=name, geom1=shape, geom2=other,
                                  condim=3, solref=[.02, 1.] if name == 'probe_pair' else [.05, 1.5], solimp=[.9, .95, .001],
                                  margin=.0005, friction=[.6, .6, .005, .0001, .0001])
            return original_builder(scene)
        envmod.physics_from_mjcf = instrument_scene
        try:
            env = GymWrapper(envmod.create_env(name=params.env.name, robot_name='adroit',
                    task_kwargs=OmegaConf.to_container(params.env.task_kwargs, resolve=True),
                    environment_kwargs=OmegaConf.to_container(params.env.env_kwargs, resolve=True)))
        finally:
            envmod.physics_from_mjcf = original_builder
        env._base_env._stage = 2
        np.random.seed(seed); torch.manual_seed(seed)
        env.wrapped.task._random = np.random.RandomState(seed)
        obs = env.reset()
        physics = env.wrapped.physics
        model, data = physics.model, physics.data
        if model.id2name(45, 'body') != '004_sugar_box/object_entity':
            raise ValueError('Instrument insertion changed upstream observation body order')
        if tuple(obs['state'].shape) != tuple(policy.observation_space.shape):
            raise ValueError('Pretrained observation shape mismatch')
        object_id = model.name2id('004_sugar_box/entity_contact0', 'geom')
        probe_id = model.name2id('probe_contact', 'geom')
        table_id = model.name2id('table_contact', 'geom')
        stage_id = int(model.body_mocapid[model.name2id('probe_stage', 'body')])
        sensor_id = model.name2id('probe_force', 'sensor')
        sensor_adr = int(model.sensor_adr[sensor_id])
        joint_ids = model.actuator_trnid[:3, 0]
        dt = float(env.wrapped.control_timestep())
        simdt = float(physics.timestep())
        mujoco.mj_saveModel(model.ptr, str(trial/'model.mjb'), None)
        archives = {}; logs = {}; private = {}; actions = []; inputs = []; wrist_path = []
        arm = 'common'
        root_bias = None
        passive_fingers = False

        def public_hand():
            return data.site_xpos[1].copy()  # calibrated robot FK, same as upstream palm

        def counts():
            hand = table = probe = probe_other = 0
            for c in data.contact:
                a, b = int(c.geom1), int(c.geom2)
                if probe_id in (a, b) and object_id not in (a, b):
                    probe_other += 1
                if object_id not in (a, b): continue
                other = b if a == object_id else a
                hand += int((model.id2name(other, 'geom') or '').startswith('adroit/'))
                table += int(other == table_id); probe += int(other == probe_id)
            return hand, table, probe, probe_other

        def record(phase):
            # dm_control's split Euler step refreshes positions with mj_step1
            # but leaves force sensors at the preceding constraint solve.
            # Synchronize sensor forces, contacts and coordinates before use.
            physics.forward()
            state = archives.setdefault(arm, {k: [] for k in ['time', 'qpos', 'qvel', 'ctrl', 'mocap_pos', 'mocap_quat', 'qfrc_applied']})
            state['time'].append(float(data.time))
            for k in state:
                if k != 'time': state[k].append(getattr(data, k).copy())
            h = public_hand()
            force = np.array(data.sensordata[sensor_adr:sensor_adr+3], copy=True)
            logs.setdefault(arm, []).append({'time_s': float(data.time), 'phase': phase,
                'hand_x': float(h[0]), 'hand_y': float(h[1]), 'hand_z': float(h[2]),
                'probe_surface_x': float(data.mocap_pos[stage_id, 0]-.001),
                'force_x_n': float(force[0]), 'force_y_n': float(force[1]), 'force_z_n': float(force[2])})
            xyz = data.geom_xpos[object_id].copy()
            R = T(data.geom_xmat[object_id].copy().reshape(3, 3))
            true_extent = (R[0].abs()*T(model.geom_size[object_id].copy())).sum().item()
            hc, tc, pc, po = counts()
            private.setdefault(arm, []).append({'time_s': float(data.time), 'phase': phase,
                'object_x': float(xyz[0]), 'object_y': float(xyz[1]), 'object_z': float(xyz[2]),
                'edge_x': float(xyz[0]+true_extent), 'hand_contacts': hc,
                'table_contacts': tc, 'probe_object_contacts': pc, 'probe_other_contacts': po})

        desired_control = None

        def command(target):
            """Same proprioceptive wrist servo for both residual variants."""
            u = target.copy()
            if root_bias is not None:
                u[:3] += root_bias + spec['root_tracking_kp']*(target[:3]-data.qpos[:3])-spec['root_tracking_kd']*data.qvel[:3]
                u[:3] = np.clip(u[:3], model.actuator_ctrlrange[:3, 0], model.actuator_ctrlrange[:3, 1])
            if passive_fingers:
                u[8:] = data.qpos[8:30]  # zero finger position error, no rigid opening sweep
            physics.set_control(u)

        def step(target, phase, duration, ramp=True):
            nonlocal desired_control
            start = target.copy() if desired_control is None else desired_control.copy()
            n = max(1, round(duration/dt))
            for i in range(n):
                alpha = (i+1)/n if ramp else 1.
                alpha = alpha*alpha*(3-2*alpha)
                desired_control = start+(target-start)*alpha
                for _ in range(round(dt/simdt)):
                    command(desired_control); physics.step()
                record(phase)

        def translated(base, world_delta):
            # Known robot axes and encoder targets only; CUDA solve, no object truth.
            axes = T(data.xaxis[joint_ids].copy().T)
            shift = torch.linalg.solve(axes, T(world_delta)).cpu().numpy()
            target = base.copy(); target[:3] += shift
            if np.any(target[:3] < model.actuator_ctrlrange[:3, 0]) or np.any(target[:3] > model.actuator_ctrlrange[:3, 1]):
                return None
            return target

        def flush():
            for key, state in archives.items():
                np.savez_compressed(trial/(key+'-states.npz'), **{k: np.asarray(v) for k, v in state.items()})
                for suffix, rows in [('public', logs[key]), ('private', private[key])]:
                    with (trial/(key+'-'+suffix+'.csv')).open('w') as f:
                        w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
            np.savez_compressed(trial/'policy-input-actions.npz', observation=np.asarray(inputs), action=np.asarray(actions))

        trial_result = {'condition': condition, 'variants': {}, 'scope': identity['scope']}
        try:
            record('reset')
            done = False
            with torch.inference_mode():
                while not done and len(actions) < 100:
                    inputs.append(obs['state'].copy())
                    action, _ = policy.predict(obs['state'], deterministic=True)
                    actions.append(action.copy())
                    obs, _, done, _ = env.step(action)
                    wrist_path.append(data.ctrl.copy())
                    record('pretrained')
            if not done: raise RuntimeError('Pretrained step cap')
            # Freeze six root and two wrist encoders, keep learned finger closure.
            hold = data.ctrl.copy(); hold[:8] = data.qpos[:8]
            root_bias = data.ctrl[:3].copy()-data.qpos[:3].copy()
            desired_control = hold.copy()
            step(hold, 'stabilize', spec['stabilize_s'])
            alignment_observations = []
            for _ in range(spec.get('upright_updates', 0)):
                current = env.wrapped.task.get_observation(physics)
                R = T(current['obj_mat'].reshape(3, 3))
                yaw = torch.atan2(R[1, 0], R[0, 0])
                goal_R = torch.eye(3, device='cuda', dtype=torch.float64)
                goal_R[0, 0] = goal_R[1, 1] = yaw.cos()
                goal_R[1, 0] = yaw.sin(); goal_R[0, 1] = -yaw.sin()
                err = goal_R@R.T
                angle = torch.acos(((torch.trace(err)-1)/2).clamp(-1., 1.))
                vector = torch.stack([err[2, 1]-err[1, 2], err[0, 2]-err[2, 0], err[1, 0]-err[0, 1]])
                vector *= angle/(2*angle.sin().clamp_min(1e-8))
                shift = torch.linalg.solve(T(data.xaxis[model.actuator_trnid[3:6, 0]].copy().T), vector).cpu().numpy()
                hold[3:6] = np.clip(hold[3:6]+shift, model.actuator_ctrlrange[3:6, 0], model.actuator_ctrlrange[3:6, 1])
                alignment_observations.append({'rotation': R.tolist(), 'command': hold.tolist()})
                step(hold, 'shared-upright', 1.)
            write(trial/'shared-alignment.json', alignment_observations)
            shared_obs = env.wrapped.task.get_observation(physics)
            pose = T(shared_obs['obj_pos']); rotation = T(shared_obs['obj_mat'].reshape(3, 3))
            hand = T(public_hand())
            corner = pose+rotation@(torch.sign(rotation[0])*nominal)
            extent = (rotation[0].abs()*nominal).sum().item()
            prior_b = float(pose[0].item()+extent-hand[0].item())
            # Goal is fixed from common coarse pose. Geometric refinement changes
            # the required wrist target, never the requested object-edge target.
            goal = float(pose[0].item()+extent+spec.get('placement_dx_m', 0.))
            lower_dz = float(spec['support_clearance_m']-(pose[2]-(rotation[2].abs()*nominal).sum()).item())
            prior = {'object_pose': pose.tolist(), 'object_rotation': rotation.tolist(),
                     'nominal_halfsize': nominal.tolist(), 'hand': hand.tolist(), 'offset_m': prior_b,
                     'goal_edge_x_m': goal, 'lower_dz_m': lower_dz,
                     'source': 'Shared privileged native pose + fixed nominal shape; actual extent excluded'}
            write(trial/'shared-prior.json', prior)
            grasp_id = condition['id']+'-native-grasp'
            memory = ContactOffsetMemory(grasp_id, prior_m=prior_b)
            probe_pos = corner.cpu().numpy(); probe_pos[0] += .001+spec['probe_start_gap_m']
            data.mocap_pos[stage_id] = probe_pos
            physics.forward()
            accepted = False; event = None; peak = 0.; event_private = None
            max_steps = round(spec['probe_max_travel_m']/spec['probe_speed_m_s']/simdt)
            for i in range(max_steps):
                probe_pos[0] -= spec['probe_speed_m_s']*simdt
                data.mocap_pos[stage_id] = probe_pos
                command(hold); physics.step(); record('probe')
                force = abs(float(data.sensordata[sensor_adr]))
                peak = max(peak, torch.linalg.vector_norm(T(data.sensordata[sensor_adr:sensor_adr+3].copy())).item())
                if force >= .2:
                    event = ContactObservation(grasp_id, 'one-probe', float(public_hand()[0]),
                                               float(probe_pos[0]-.001), (1., 0., 0.), force)
                    accepted = peak <= 2. and memory.update(event)
                    event_private = dict(private[arm][-1])
                    break
            # Retract along the known probe axis before parking the instrument.
            for i in range(round(.04/spec['probe_retract_m_s']/simdt)):
                probe_pos[0] += spec['probe_retract_m_s']*simdt
                data.mocap_pos[stage_id] = probe_pos
                command(hold); physics.step(); record('probe-retract')
                peak = max(peak, torch.linalg.vector_norm(T(data.sensordata[sensor_adr:sensor_adr+3].copy())).item())
            data.mocap_pos[stage_id] = [2, 2, 2]
            physics.forward(); step(hold, 'post-probe-hold', .2)
            accepted = bool(accepted and peak <= 2.)
            probe_ok = bool(accepted and event_private['probe_object_contacts'] > 0 and event_private['probe_other_contacts'] == 0
                            and event_private['hand_contacts'] >= 2 and private[arm][-1]['hand_contacts'] >= 2)
            write(trial/'contact-memory.json', {'prior_m': prior_b, 'event': event.__dict__ if event else None,
                'posterior': memory.snapshot(), 'accepted': accepted, 'peak_n': peak,
                'evaluator_probe_valid': probe_ok, 'evaluator_event': event_private})
            fields = ['qpos', 'qvel', 'act', 'ctrl', 'qacc_warmstart', 'qfrc_applied', 'xfrc_applied', 'mocap_pos', 'mocap_quat', 'userdata']
            snapshot = {k: getattr(data, k).copy() for k in fields}
            snap_time = float(data.time)
            np.savez_compressed(trial/'fork-state.npz', time=snap_time, **snapshot)
            for arm in ['baseline', 'contact']:
                passive_fingers = False
                for k, value in snapshot.items(): getattr(data, k)[:] = value
                data.time = snap_time; physics.forward()
                # Preserve warmstart after forward; same deterministic restart.
                data.qacc_warmstart[:] = snapshot['qacc_warmstart']
                desired_control = hold.copy()
                record('fork')
                offset = prior_b if arm == 'baseline' or not accepted else memory.snapshot()['mean_m']
                dx = goal-offset-float(public_hand()[0])
                target = translated(hold, [dx, 0., 0.])
                reachable = target is not None and abs(dx) <= spec['residual_limit_m']
                if not reachable: target = hold.copy()
                step(target, 'placement-residual', .8)
                prerelease_edge_error = abs(private[arm][-1]['edge_x']-goal)
                lower = translated(target, [0., 0., lower_dz])
                lower_reachable = lower is not None
                if lower is None: lower = target.copy()
                step(lower, 'lower', 2.)
                step(lower, 'support-hold', .5)
                if spec.get('passive_release', False):
                    passive_fingers = True
                    step(lower, 'release-relax', .5)
                    # Retreat along the known approach axis. A diagonal retreat
                    # wastes the native root-X travel limit for this checkpoint.
                    away = T([0., .12 if hand[1] > pose[1] else -.12, 0.])
                    withdraw = translated(lower, away.tolist())
                    if withdraw is None:
                        lower_reachable = False; withdraw = lower.copy()
                    step(withdraw, 'passive-withdraw', 2.)
                    passive_fingers = False
                    opened = withdraw.copy(); opened[8:] = 0.
                    step(opened, 'release-open', 1.)
                    withdraw = opened
                else:
                    relaxed = lower.copy(); relaxed[8:] = data.qpos[8:30]
                    step(relaxed, 'release-relax', .3)
                    opened = relaxed.copy(); opened[8:] = 0.
                    step(opened, 'release-open', 2.)
                    withdraw = opened.copy(); withdraw[:8] = target[:8]
                    step(withdraw, 'withdraw', 1.)
                step(withdraw, 'settle', spec['settle_s'])
                tail = private[arm][-round(.25/dt):]
                stable = private[arm][-round(.5/dt):]
                xyz = T([[r['object_x'], r['object_y'], r['object_z']] for r in stable])
                drift = torch.linalg.vector_norm(xyz-xyz[-1], dim=1).max().item()
                Rfinal = T(data.geom_xmat[object_id].copy().reshape(3, 3))
                angle = torch.rad2deg(torch.acos(((torch.trace(rotation.T@Rfinal)-1)/2).clamp(-1, 1))).item()
                detached = all(r['hand_contacts'] == 0 for r in tail)
                supported = all(r['table_contacts'] > 0 for r in tail)
                valid = bool(probe_ok and reachable and lower_reachable and detached and supported and drift <= .002 and angle <= 10.)
                error = abs(private[arm][-1]['edge_x']-goal)
                trial_result['variants'][arm] = {'edge_error_m': error,
                    'penalized_error_m': error if valid else max(.05, error), 'valid': valid,
                    'prerelease_edge_error_m': prerelease_edge_error, 'residual_dx_m': dx,
                    'offset_m': offset, 'reachable': bool(reachable), 'lower_reachable': lower_reachable,
                    'detached': detached, 'table_supported': supported, 'drift_m': drift, 'orientation_error_deg': angle}
            trial_result.update({'probe_valid': probe_ok, 'probe_peak_n': peak, 'memory': memory.snapshot(),
                                 'policy_steps': len(actions), 'goal_edge_x_m': goal})
        finally:
            flush()
        trial_result['common_states_sha256'] = digest(trial/'common-states.npz')
        trial_result['policy_input_actions_sha256'] = digest(trial/'policy-input-actions.npz')
        trial_result['fork_sha256'] = digest(trial/'fork-state.npz')
        write(trial/'result.json', trial_result)
        results.append(trial_result)
        write(args.output/'progress.json', {'trials': results})
        print(json.dumps(trial_result), flush=True)
        env.close()
    errors = T([[r['variants'][v]['penalized_error_m'] for v in ['baseline', 'contact']] for r in results])
    means = errors.mean(dim=0)
    improvement = (1-means[1]/means[0]).item()
    valid_counts = {v: sum(r['variants'][v]['valid'] for r in results) for v in ['baseline', 'contact']}
    # A large reduction among failed releases is not a task success.
    generator = torch.Generator(device='cuda').manual_seed(314159)
    differences = errors[:, 0]-errors[:, 1]
    # Width variants share a seed: bootstrap seed clusters, not individual rows.
    seeds = sorted({r['condition']['seed'] for r in results})
    cluster_differences = torch.stack([differences[[i for i, r in enumerate(results) if r['condition']['seed'] == seed]].mean() for seed in seeds])
    indices = torch.randint(len(seeds), (10000, len(seeds)), generator=generator, device='cuda')
    ci = torch.quantile(cluster_differences[indices].mean(dim=1), T([.025, .975])).tolist()
    gate = improvement >= .25 and valid_counts['contact']/len(results) >= .8 and valid_counts['contact'] >= valid_counts['baseline'] and ci[0] > 0.
    summary = {'execution_status': 'passed', 'research_status': 'passed' if gate else 'failed',
               'trial_count': len(results), 'penalized_mae_m': means.tolist(), 'relative_improvement': improvement,
               'valid_counts': valid_counts, 'paired_mean_reduction_m': differences.mean().item(),
               'paired_bootstrap_95ci_m': ci, 'bootstrap_scope': 'Seed-cluster bootstrap within frozen local development conditions; not object-generalization',
               'probe_valid_count': sum(r['probe_valid'] for r in results), 'trials': results,
               'scope': identity['scope'], 'protocol_sha256': digest(args.protocol)}
    write(args.output/'result.json', summary)


if __name__ == '__main__':
    main()
