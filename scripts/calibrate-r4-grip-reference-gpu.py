#!/usr/bin/env python3
"""Freeze per-finger closing phase from development public tactile evidence.

This prepares a new fixed reference, not an online oracle or a success claim.
It neither reads object state nor changes the common bounded force controller.
"""
import argparse
import copy
import json
from pathlib import Path
import torch
from r4_contract import read_contract, validate_contract, sha256, write_json
from r4_cuda import require_cuda


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--observations',type=Path,required=True)
    p.add_argument('--threshold',type=float,required=True)
    p.add_argument('--task',choices=['lift_hold','precision_place'],required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();device,gpu=require_cuda()
    if not .1<=args.threshold<=1.5:raise ValueError('Development target outside bounded range')
    ref=read_contract(args.reference)
    if ref['split']!='debug':raise ValueError('Only debug reference calibration is authorized')
    calibration=json.loads((args.observations/'calibration.json').read_text())
    limits={};records=[]
    with (args.observations/'observations.jsonl').open() as stream:
        for line in stream:
            frame=json.loads(line)
            for packet in frame['tactile']:
                finger=packet['sensor_id']
                if finger not in ['mf','th'] or not packet['valid'] or finger in limits:continue
                if not 1.0<=packet['time_s']<=3.0:continue
                force=torch.tensor(packet['force_sensor_n'],device=device,dtype=torch.float64).reshape(-1,3)
                load=force.norm(dim=-1);total=float(load[load>=calibration['threshold_n']].sum())
                if total>=args.threshold:
                    limits[finger]=float(packet['time_s']);records.append({'finger':finger,'acquisition_time_s':packet['time_s'],'load_n':total})
            if len(limits)==2:break
    if len(limits)!=2:raise ValueError('Both opposing fingers must show the preregistered load crossing')
    times=torch.tensor([f['time_s'] for f in ref['frames']],device=device,dtype=torch.float64)
    joints=torch.tensor([f['joint_position'] for f in ref['frames']],device=device,dtype=torch.float64)
    changed=joints.clone()
    for finger,columns in [('mf',slice(4,8)),('th',slice(12,16))]:
        cap=limits[finger]
        sample_time=times.clamp_max(cap)
        # Keep the original release time. Reverse only the traversed closing path.
        if args.task=='precision_place':
            sample_time=torch.where(times>=9.,1.+((9.75-times)/.75).clamp(0,1)*(cap-1.),sample_time)
        index=torch.searchsorted(times,sample_time).clamp(1,len(times)-1)
        weight=(sample_time-times[index-1])/(times[index]-times[index-1])
        values=joints[index-1]+weight[:,None]*(joints[index]-joints[index-1])
        changed[:,columns]=values[:,columns]
    output=copy.deepcopy(ref)
    for frame,value in zip(output['frames'],changed.tolist()):frame['joint_position']=value
    output['provenance']['public_grip_calibration']={'reference_sha256':sha256(args.reference),
        'observations_sha256':sha256(args.observations/'observations.jsonl'),'load_crossing_n':args.threshold,
        'finger_phase_caps_s':limits,'claim':'fixed development reference; physical verification required'}
    validate_contract(output);args.output.mkdir(parents=True,exist_ok=False)
    write_json(args.output/'reference.json',output)
    write_json(args.output/'result.json',{'status':'awaiting_verification','gpu':gpu,'threshold_n':args.threshold,
        'load_crossings':records,'reference_sha256':sha256(args.output/'reference.json'),'source_sha256':sha256(__file__)})


if __name__=='__main__':main()
