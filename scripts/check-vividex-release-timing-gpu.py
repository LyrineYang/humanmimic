#!/usr/bin/env python3
"""Audit paired timing archives and compute predeclared CUDA statistics."""
import argparse
import csv
import json
from pathlib import Path

from r4_campaign import digest, write
from r4_contact_offset import ContactObservation, ContactOffsetMemory


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--reference', type=Path, help='Optional developer run before post-policy workspace extension')
    args = p.parse_args()
    import numpy as np
    import torch
    import mujoco
    if not torch.cuda.is_available(): raise RuntimeError('CUDA required')
    T = lambda value: torch.as_tensor(value, device='cuda', dtype=torch.float64)
    result = json.loads((args.run/'result.json').read_text())
    spec = json.loads((args.run/'protocol.json').read_text())
    trials = result['trials']; checks = []; peaks = []
    unchanged_policy_prefixes=0
    def read_csv(path):
        with path.open() as f: return list(csv.DictReader(f))
    for trial in trials:
        folder = args.run/trial['condition']['id']
        common = np.load(folder/'common-states.npz')
        if args.reference and (args.reference/trial['condition']['id']).exists():
            prior=args.reference/trial['condition']['id']
            left=np.load(prior/'policy-input-actions.npz');right=np.load(folder/'policy-input-actions.npz')
            for key in left.files: assert torch.equal(T(left[key]),T(right[key])),('Changed pretrained policy',folder,key)
            old_state=np.load(prior/'common-states.npz')
            for key in ['qpos','qvel','ctrl']:
                assert torch.equal(T(old_state[key][:61]),T(common[key][:61])),('Changed pretrained dynamics',folder,key)
            unchanged_policy_prefixes+=1
        model = mujoco.MjModel.from_binary_path(str(folder/'model.mjb'))
        data = mujoco.MjData(model)
        gid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, '004_sugar_box/entity_contact0')
        bid = int(model.geom_bodyid[gid])
        assert model.body_jntnum[bid] == 6
        for i in range(model.neq):
            if model.eq_type[i] in (mujoco.mjtEq.mjEQ_WELD, mujoco.mjtEq.mjEQ_CONNECT):
                assert bid not in (model.eq_obj1id[i], model.eq_obj2id[i])
        assert abs(float(model.geom_size[gid, 0])-(.021748+trial['condition']['halfwidth_delta_mm']/1000)) < 1e-10
        for timing in spec['probe_timings']:
            prefix = np.load(folder/(timing+'-common-states.npz'))
            baseline = np.load(folder/(timing+'-baseline-states.npz'))
            contact = np.load(folder/(timing+'-contact-states.npz'))
            for key in common.files:
                assert torch.equal(T(prefix[key][0]), T(common[key][-1])), ('timing fork differs', folder, key)
                assert torch.equal(T(baseline[key][0]), T(contact[key][0])), ('unpaired arm', folder, key)
                assert torch.equal(T(baseline[key][0]), T(prefix[key][-1])), ('unpaired probe prefix', folder, key)
            public = read_csv(folder/(timing+'-common-public.csv'))
            force_rows = [row for row in public if row['phase'] in ['probe','probe-retract']]
            forces = T([[float(row[key]) for key in ['force_x_n','force_y_n','force_z_n']] for row in force_rows])
            peak = torch.linalg.vector_norm(forces,dim=1).max().item(); peaks.append(peak)
            assert abs(peak-trial['probe'][timing]['peak_n']) < 1e-9
            event = json.loads((folder/(timing+'-contact-memory.json')).read_text())
            if event['accepted']:
                obs = ContactObservation(**event['event'])
                memory = ContactOffsetMemory(obs.grasp_id, prior_m=event['prior_m'])
                assert memory.update(obs)
                assert abs(memory.snapshot()['mean_m']-event['posterior']['mean_m']) < 1e-12
                assert len(event['posterior']['events']) == 1
            for arm, state in [('baseline',baseline),('contact',contact)]:
                name = timing+'-'+arm
                for key in state.files:
                    assert torch.isfinite(T(state[key])).all()
                assert (torch.diff(T(state['time']))>0).all()
                for key in state.files:
                    if key == 'time': data.time=float(state[key][-1])
                    else: getattr(data,key)[:] = state[key][-1]
                mujoco.mj_forward(model,data)
                R=T(data.geom_xmat[gid].reshape(3,3))
                edge=float(data.geom_xpos[gid,0])+(R[0].abs()*T(model.geom_size[gid])).sum().item()
                error=abs(edge-trial['goal_edge_x_m'])
                assert abs(error-trial['variants'][name]['edge_error_m'])<1e-10
                metrics=trial['variants'][name]
                expected=error if metrics['valid'] else max(.05,error)
                assert abs(expected-metrics['penalized_error_m'])<1e-10
                checks.append({'trial':trial['condition']['id'],'arm':name,'status':'passed','edge_error_m':error})
    def ci_by_seed(rows, values):
        seeds=sorted({r['condition']['seed'] for r in rows})
        cluster=torch.stack([values[[i for i,r in enumerate(rows) if r['condition']['seed']==seed]].mean() for seed in seeds])
        gen=torch.Generator(device='cuda').manual_seed(314159)
        indices=torch.randint(len(seeds),(10000,len(seeds)),generator=gen,device='cuda')
        return torch.quantile(cluster[indices].mean(dim=1),T([.025,.975])).tolist()
    # Corrupting a coarse prior must not change the underlying physical skill.
    prefix_groups={}
    for trial in trials:
        key=(trial['condition']['seed'],trial['condition']['halfwidth_delta_mm'])
        prefix_groups.setdefault(key,[]).append(trial)
    prior_prefix_pairs=0
    for rows in prefix_groups.values():
        reference=args.run/rows[0]['condition']['id']
        for row in rows[1:]:
            folder=args.run/row['condition']['id']
            for name in ['common-states.npz','policy-input-actions.npz']:
                left=np.load(reference/name);right=np.load(folder/name)
                for key in left.files: assert torch.equal(T(left[key]),T(right[key])),('Prior changed skill prefix',folder,key)
            assert abs(row['goal_edge_x_m']-rows[0]['goal_edge_x_m'])<1e-12
            prior_prefix_pairs+=1
    groups={}
    for study in sorted({t['condition'].get('study','development') for t in trials}):
        rows=[t for t in trials if t['condition'].get('study','development')==study]
        arm_stats={}; contrasts={}
        for name in rows[0]['variants']:
            metrics=[r['variants'][name] for r in rows]
            arm_stats[name]={key:T([v[key] for v in metrics]).mean().item() for key in ['edge_error_m','penalized_error_m','prerelease_edge_error_m','orientation_error_deg']}
            arm_stats[name]['valid']=sum(m['valid'] for m in metrics)
            arm_stats[name]['failures_nonexclusive']={key:sum(not m[key] for m in metrics) for key in ['probe_valid','airborne_grasp_ok','reachable','lower_reachable','detached','table_supported']}
            arm_stats[name]['failures_nonexclusive']['orientation']=sum(m['orientation_error_deg']>10 for m in metrics)
        for timing in spec['probe_timings']:
            error=T([[r['variants'][timing+'-'+v]['penalized_error_m'] for v in ['baseline','contact']] for r in rows])
            improvement=(1-error[:,1].mean()/error[:,0].mean()).item()
            ci=ci_by_seed(rows,error[:,0]-error[:,1])
            nbase=arm_stats[timing+'-baseline']['valid']; ncorr=arm_stats[timing+'-contact']['valid']
            gate=improvement>=.25 and ncorr/len(rows)>=.8 and ncorr>=nbase and ci[0]>0
            contrasts[timing]={'relative_improvement':improvement,'paired_reduction_95ci_m':ci,'research_status':'passed' if gate else 'failed'}
        late_early=T([r['variants']['supported-contact']['penalized_error_m']-r['variants']['early-contact']['penalized_error_m'] for r in rows])
        groups[study]={'n':len(rows),'arms':arm_stats,'comparisons':contrasts,
                       'supported_minus_early_m':late_early.mean().item(),'timing_difference_95ci_m':ci_by_seed(rows,late_early)}
    write(args.output,{'status':'passed','trials':len(trials),'arm_checks':checks,'groups':groups,'identical_prior_corruption_prefix_pairs':prior_prefix_pairs,
                       'unchanged_policy_prefixes_vs_reference':unchanged_policy_prefixes,
                       'max_probe_3d_force_n':max(peaks),'training':False,'heldout':False,'rendered':False,
                       'scope':'CUDA archive equality, free object, one-event posterior, final metric reconstruction and seed-cluster bootstrap; not task success by itself'})


if __name__=='__main__': main()
