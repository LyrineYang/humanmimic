#!/usr/bin/env python3
"""Use a development replay's public hand encoders as a fixed nominal reference."""
import argparse
import copy
import json
from pathlib import Path
import torch
from r4_contract import JOINT_LIMITS,read_contract,validate_contract,sha256,write_json
from r4_cuda import require_cuda
from r4_grasp_quaternion import matrix_quaternion
from r4_hand_model import rotation


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--observations',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--lift-delay',type=float,choices=[0.,2.],default=0.)
    args=p.parse_args();device,gpu=require_cuda();ref=read_contract(args.reference)
    if ref['split']!='debug':raise ValueError('Only development hand trajectory calibration')
    # Deliberately retain only publicly observed hand fields.
    rows=[]
    with (args.observations/'observations.jsonl').open() as stream:
        for line in stream:
            f=json.loads(line);rows.append([f['time_s'],f['joint_position_rad'],f['T_world_wrist']])
    tensor=lambda x:torch.tensor(x,device=device,dtype=torch.float64)
    time=tensor([r[0] for r in rows]);target=tensor([f['time_s'] for f in ref['frames']])
    gap,index=(target[:,None]-time[None,:]).abs().min(-1)
    if float(gap.max())>1e-6:raise ValueError('Require complete matching public hand samples')
    q=tensor([r[1] for r in rows])[index];limits=tensor(JOINT_LIMITS)
    bounded=q.clamp(limits[:,0],limits[:,1]);transforms=tensor([r[2] for r in rows])[index]
    if args.lift_delay:
        if ref['provenance'].get('generator')!='prepare-r4-grasps-gpu.py':raise ValueError('Retiming requires the known generated lift schedule')
        transforms[:,2,3]+=((target-3.-args.lift_delay)/1.5).clamp(0,1)*.11-((target-3.)/1.5).clamp(0,1)*.11
    quaternions=torch.stack([matrix_quaternion(t[:3,:3]) for t in transforms])
    roundtrip=torch.stack([rotation(q) for q in quaternions])
    error=float((roundtrip-transforms[:,:3,:3]).abs().max())
    if error>1e-9:raise ValueError('Quaternion conversion changed hand orientation')
    output=copy.deepcopy(ref)
    for f,j,x,qw in zip(output['frames'],bounded.tolist(),transforms[:,:3,3].tolist(),quaternions.tolist()):
        f.update(joint_position=j,wrist_position=x,wrist_quaternion=qw)
    output['provenance']['public_hand_trajectory_calibration']={
        'reference_sha256':sha256(args.reference),'public_observations_sha256':sha256(args.observations/'observations.jsonl'),
        'lift_delay_s':args.lift_delay,
        'claim':'Observed hand states become nominal targets; physical success requires independent replay'}
    validate_contract(output);args.output.mkdir(parents=True,exist_ok=False)
    write_json(args.output/'reference.json',output)
    write_json(args.output/'result.json',{'status':'awaiting_verification','execution_status':'passed','gpu':gpu,
        'maximum_joint_limit_clip_rad':float((bounded-q).abs().max()),'quaternion_roundtrip_max_error':error,
        'source_sha256':sha256(__file__),'reference_sha256':sha256(args.output/'reference.json')})


if __name__=='__main__':main()
