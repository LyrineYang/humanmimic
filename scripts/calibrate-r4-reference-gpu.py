#!/usr/bin/env python3
"""Bounded development-only feedforward correction of a stable placement reference.

Uses a previous private evaluation as an OFFLINE reference calibration. It is
not an observation/prior, never enters the estimator, and is not heldout evidence.
Every experimental strategy must share the subsequently frozen reference.
"""
import argparse
import copy
import json
from pathlib import Path
import numpy as np
import torch
from r4_belief import rotation_vector, so3
from r4_belief_evaluation import quaternion_matrix
from r4_contract import sha256,write_json,validate_contract
from r4_cuda import require_cuda

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',type=Path,required=True);p.add_argument('--previous-run',type=Path,required=True)
    p.add_argument('--goal-position',nargs=3,type=float,required=True);p.add_argument('--goal-quaternion',nargs=4,type=float,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();device,gpu=require_cuda();t=lambda x:torch.tensor(x,device=device,dtype=torch.float64)
    evaluation=args.previous_run/'private-evaluation';result=json.loads((evaluation/'result.json').read_text());metrics=result['metrics']
    if not (metrics['released_during_settle'] and metrics['lift_hold_seconds']>=2 and metrics['max_penetration_m']<=.002 and metrics['opposing_contact_fraction_when_lifted']>=.8):
        raise ValueError('Only stable, released development placement can be calibrated; do not mask failed grasp/collision')
    with np.load(evaluation/'actual-state.npz',allow_pickle=False) as raw:last=t(raw['samples'][-1])
    goal=t(args.goal_position);delta=goal-last[1:4];rot=rotation_vector(quaternion_matrix(t(args.goal_quaternion))@quaternion_matrix(last[4:8]).T)
    if float(delta.norm())>.02 or float(rot.norm())>torch.pi/9:raise ValueError('Reference calibration exceeds 20mm/20deg development bound')
    contract=json.loads(args.reference.read_text());validate_contract(contract)
    times=t([f['time_s'] for f in contract['frames']]);position=t([f['wrist_position'] for f in contract['frames']]);quaternion=t([f['wrist_quaternion'] for f in contract['frames']])
    fraction=((times-6.8)/1.2).clamp(0,1);r=so3(fraction[:,None]*rot)
    position=(r@(position-goal)[...,None]).squeeze(-1)+goal+fraction[:,None]*delta
    angle=rot.norm();axis=rot/angle.clamp_min(1e-12);dq=torch.cat([(fraction*angle/2).cos()[:,None],(fraction*angle/2).sin()[:,None]*axis],-1)
    w=dq[:,:1]*quaternion[:,:1]-(dq[:,1:]*quaternion[:,1:]).sum(-1,keepdim=True)
    xyz=dq[:,:1]*quaternion[:,1:]+quaternion[:,:1]*dq[:,1:]+torch.linalg.cross(dq[:,1:],quaternion[:,1:])
    qs=torch.cat([w,xyz],-1)
    for frame,point,q in zip(contract['frames'],position.tolist(),qs.tolist()):frame.update(wrist_position=point,wrist_quaternion=q)
    contract['provenance'].update(reference_calibration='offline development evaluation, shared fixed feedforward; not an estimator input',
        parent_sha256=sha256(args.reference),previous_result_sha256=sha256(evaluation/'result.json'))
    validate_contract(contract);args.output.mkdir(parents=True,exist_ok=False);write_json(args.output/'reference.json',contract)
    write_json(args.output/'manifest.json',{'status':'awaiting_verification','gpu':gpu,'translation_correction_m':delta.tolist(),
        'rotation_correction_rad':rot.tolist(),'source_sha256':sha256(__file__),'heldout_used':False,
        'scope':'development reference calibration only; independent rerun required'})

if __name__=='__main__':main()
