#!/usr/bin/env python3
"""Fit and independently verify LEAP pose confidence on CUDA.

Private trajectory truth is opened only AFTER the isolated estimator exits.
Missing/unobservable trials remain failures in the denominator. This cannot
certify material compliance: MuJoCo soft contact has no known scalar label.
"""
import argparse
import json
import math
from pathlib import Path
import numpy as np
import torch
from r4_belief_evaluation import quaternion_matrix
from r4_contract import sha256, write_json
from r4_cuda import require_cuda
from r4_public import read_public
from r4_replay import launch

def score(belief,prior,actual,device):
    if not belief['state_updated']:return {'observable':False,'reason':'state_not_updated'}
    t=lambda x:torch.as_tensor(x,device=device,dtype=torch.float64)
    records=t(actual);initial=int((records[:,0]-prior['initial_time_s']).abs().argmin())
    last=int((records[:,0]-belief['time_s']).abs().argmin())
    if max(abs(float(records[initial,0])-prior['initial_time_s']),abs(float(records[last,0])-belief['time_s']))>.0021:
        raise ValueError('Private trajectory and public observation times disagree')
    def pose(row):
        out=torch.eye(4,device=device,dtype=torch.float64);out[:3,:3]=quaternion_matrix(row[4:8]);out[:3,3]=row[1:4];return out
    # A scan model has an arbitrary object coordinate frame. Freeze its alignment
    # at acquisition time; never align the final estimate to its answer.
    truth=pose(records[last])@torch.linalg.inv(pose(records[initial]))@t(prior['T_world_object_initial'])
    estimated=t(belief['T_world_object'][-1]);offset=6*(len(belief['T_world_object'])-1)
    null=t(belief['null_projector']).diag()[offset:offset+3]
    covariance=t(belief['covariance']);std=covariance.diag()[offset:offset+3].clamp_min(0).sqrt()*belief['parameter_scales']['translation_m']
    error=(estimated[:3,3]-truth[:3,3]).abs();observable=bool((null<.05).all() & (std>0).all())
    return {'observable':observable,'reason':'ok' if observable else 'translation_null_direction',
        'translation_error_xyz_m':error.tolist(),'translation_std_xyz_m':std.tolist(),
        'normalized_max_error':float((error/std.clamp_min(1e-15)).max()) if observable else None,
        'compliance_observable':belief['compliance_observable'],'compliance_coverage':'awaiting_verification',
        'accepted_contact_taxels':belief['accepted_contact_taxels'],'force_excited':belief['force_excited']}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--phase',choices=['fit','verify','pilot'],required=True);p.add_argument('--fit-report',type=Path)
    p.add_argument('--config',type=Path,default=Path(__file__).resolve().parents[1]/'configs/r4-p1p2.json')
    args=p.parse_args();device,gpu=require_cuda();document=json.loads(args.cases.read_text());cases=document['cases']
    if document.get('split')!='debug':raise ValueError('Development calibration only')
    if len({c['seed'] for c in cases})!=len(cases):raise ValueError('Calibration seeds must be unique')
    if len({str(Path(c['observations']).resolve()) for c in cases})!=len(cases):raise ValueError('Independent physical observation bundles required')
    window=document.get('window_s',[1.3,2.0])
    if len(window)!=2 or abs(window[1]-window[0]-.7)>1e-8:raise ValueError('Freeze an eight-frame 10Hz window')
    implementation={f.name:sha256(f) for f in Path(__file__).parent.glob('*r4*.py')}
    if args.phase!='pilot' and len(cases)<20:raise ValueError('At least twenty trials per frozen partition')
    config=json.loads(args.config.read_text())['estimator'];factor=None
    if args.phase=='verify':
        if not args.fit_report:raise ValueError('Freeze fit report before verification')
        fit=json.loads(args.fit_report.read_text())
        if fit['phase']!='fit' or fit['pose_status']!='passed':raise ValueError('Invalid fit calibration')
        if set(fit['seeds']) & {c['seed'] for c in cases}:raise ValueError('Fit and verification seeds overlap')
        if fit['estimator_config_sha256']!=sha256(args.config):raise ValueError('Estimator changed after fitting')
        if fit['implementation_sha256']!=implementation or fit['window_s']!=window:raise ValueError('Implementation or sampling changed after fitting')
        factor=fit['simultaneous_translation_multiplier']
    args.output.mkdir(parents=True,exist_ok=False);metrics=[]
    write_json(args.output/'manifest.json',{'status':'running','gpu':gpu,'cases_sha256':sha256(args.cases),
        'estimator_config_sha256':sha256(args.config),'source_sha256':sha256(__file__),
        'fit_report_sha256':sha256(args.fit_report) if args.fit_report else None,'heldout_used':False})
    for case in cases:
        out=args.output/str(case['seed'])
        try:
            physical=json.loads((Path(case['observations']).parent/'manifest.json').read_text())
            if physical['sensor_seed']!=case['seed'] or physical['status']!='complete':raise ValueError('Independent sensor seed or completed physical trial missing')
            payload=read_public(Path(case['observations']),Path(case['prior']))
            payload['frames']=[f for f in payload['frames'] if f['vision'] is not None and window[0]-.01<=f['time_s']<=window[1]+.01]
            if len(payload['frames'])!=8:raise ValueError('Frozen eight-frame window absent, including early force abort')
            payload.update(config=config,modality='VF',ablation='joint',seed=case['seed'],occlusion=0)
            estimated=launch(payload,out,config['maximum_wall_s']+120)
            with np.load(case['actual_state'],allow_pickle=False) as raw:actual=raw['samples']
            item=score(estimated['beliefs'][-1],payload['prior'],actual,device)
            item['private_actual_sha256']=sha256(case['actual_state'])
        except (RuntimeError,ValueError,FileNotFoundError) as exc:
            item={'observable':False,'reason':str(exc),'normalized_max_error':None}
        item.update(seed=case['seed'],object_id=case['object_id']);metrics.append(item)
        write_json(args.output/'progress.json',{'status':'running','metrics':metrics})
    finite=[m['normalized_max_error'] for m in metrics if m['observable']]
    if args.phase=='fit' and len(finite)==len(cases):
        values=torch.tensor(finite,device=device,dtype=torch.float64).sort().values
        rank=math.ceil((len(values)+1)*.95)
        factor=max(2.498,float(values[rank-1])) if rank<=len(values) else None
    covered=[bool(m['observable'] and factor is not None and m['normalized_max_error']<=factor) for m in metrics]
    fraction=sum(covered)/len(cases)
    pose_status=('passed' if factor is not None else 'failed') if args.phase=='fit' else ('passed' if args.phase=='verify' and fraction>=.8 else 'awaiting_verification' if args.phase=='pilot' else 'failed')
    write_json(args.output/'result.json',{'status':'awaiting_verification','pose_status':pose_status,'phase':args.phase,
        'scope':'Development contact-onset translation intervals conditional on observed initial scan alignment; not full-episode/material calibration',
        'simultaneous_translation_multiplier':factor,'coverage_fraction':fraction if args.phase=='verify' else None,
        'coverage_trials':len(cases),'seeds':[c['seed'] for c in cases],'metrics':metrics,'gpu':gpu,'heldout_used':False,
        'estimator_config_sha256':sha256(args.config),'implementation_sha256':implementation,'window_s':window,'compliance_coverage':'awaiting_verification',
        'compliance_reason':'Rigid-body soft contact is not a known constant material compliance; do not substitute actuator loading labels',
        'joint_E3_gate_passed':False})
    manifest=json.loads((args.output/'manifest.json').read_text())
    manifest.update(status='complete',result_sha256=sha256(args.output/'result.json'))
    write_json(args.output/'manifest.json',manifest)

if __name__=='__main__':main()
