#!/usr/bin/env python3
"""Articulated LEAP load/force-bound calibration, with disjoint verification seeds.

Uses the entire hand, unchanged collision geometries/joints/torque limits and
physical sliding force probes. Private contact forces are evaluator-only. This
is a local posture load calibration, NOT object-belief confidence calibration.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import time
import xml.etree.ElementTree as ET
import imageio.v2 as imageio
import mujoco
import numpy as np
import torch
from r4_contract import JOINT_NAMES, JOINT_LIMITS, sha256, write_json
from r4_cuda import require_cuda
from r4_sensor_bridge import instrument, SensorBridge
from r4_hand_gravity import HandGravity
from r4_native_sensor import load_sensor


def build(asset, config, physics, q, device):
    root=ET.parse(asset/'right_hand.xml').getroot()
    root.find('compiler').set('meshdir',str((asset/'assets').resolve()))
    root.find('option').set('timestep',str(physics['timestep_seconds']))
    root.find('option').set('gravity','0 0 -9.81')
    root.find('option').set('iterations',str(physics['iterations']))
    root.find('default/position').set('forcelimited','true')
    root.find('default/position').set('forcerange','-.95 .95')
    palm=root.find("worldbody/body[@name='palm']");palm.set('pos','0 0 .25');palm.set('quat','1 0 0 0')
    instrument(root,config)
    initial=mujoco.MjModel.from_xml_string(ET.tostring(root,encoding='unicode'));state=mujoco.MjData(initial)
    for i,name in enumerate(JOINT_NAMES):
        j=mujoco.mj_name2id(initial,mujoco.mjtObj.mjOBJ_JOINT,name);state.qpos[initial.jnt_qposadr[j]]=float(q[i])
    mujoco.mj_forward(initial,state)
    bridge=SensorBridge(initial,config)
    tensor=lambda x:torch.as_tensor(x,device=device,dtype=torch.float64)
    world=root.find('worldbody');actuators=root.find('actuator')
    surface=[]
    for i,f in enumerate(['if','mf','rf','th']):
        tri=tensor(bridge.calibration['pads'][f]['triangles_sensor_m']);centers=tri.mean(1)
        normals=torch.linalg.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);normals/=normals.norm(dim=-1,keepdim=True).clamp_min(1e-12)
        direction=tensor([0,0,-1]);valid=(normals@direction)>.8
        if not bool(valid.any()):raise ValueError('Known pad has no front-facing calibration surface')
        scores=torch.where(valid,centers@direction,torch.full_like(centers[:,0],-1e9));index=int(scores.argmax())
        site=bridge.bindings[f][0];r=tensor(state.site_xmat[site]).reshape(3,3);point=r@centers[index]+tensor(state.site_xpos[site])
        normal=r@normals[index];position=point+normal*.0035
        body=ET.SubElement(world,'body',name='probe_'+f,pos=' '.join(map(str,position.tolist())))
        ET.SubElement(body,'joint',name='slide_'+f,type='slide',axis=' '.join(map(str,(-normal).tolist())),damping='.2')
        ET.SubElement(body,'geom',name='ball_'+f,type='sphere',size='.003',mass='.005',rgba='.1 .4 .9 1',contype='2',conaffinity='1',friction='.8 .005 .0001')
        ET.SubElement(actuators,'motor',name='load_'+f,joint='slide_'+f,gear='1',ctrllimited='true',ctrlrange='0 2',forcelimited='true',forcerange='0 2')
        surface.append({'finger':f,'known_surface_sensor_m':centers[index].tolist(),'normal_world':normal.tolist()})
    ET.SubElement(world,'light',pos='0 -.3 .8')
    visual=ET.SubElement(root,'visual');ET.SubElement(visual,'global',offwidth='640',offheight='480')
    return mujoco.MjModel.from_xml_string(ET.tostring(root,encoding='unicode')),surface


def trial(asset,sensor,physics,q,seed,device,video=None):
    model,surfaces=build(asset,sensor,physics,q,device);data=mujoco.MjData(model)
    joints=[mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_JOINT,n) for n in JOINT_NAMES]
    qadr=model.jnt_qposadr[joints]
    data.qpos[qadr]=q.tolist()
    ids=[mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_ACTUATOR,n+'_act') for n in JOINT_NAMES]
    data.ctrl[ids]=q.tolist()
    gravity=HandGravity(asset)
    cfg=copy.deepcopy(sensor);cfg.update(noise_std_n=0,dropout_probability=0,seed=seed)
    bridge=SensorBridge(model,cfg)
    load=[mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_ACTUATOR,'load_'+f) for f in ['if','mf','rf','th']]
    probes=[model.jnt_qposadr[mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_JOINT,'slide_'+f)] for f in ['if','mf','rf','th']]
    bodies=[mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,sensor['sites'][f]['body']) for f in ['if','mf','rf','th']]
    renderer=mujoco.Renderer(model,height=480,width=640) if video else None
    writer=imageio.get_writer(video,fps=25,codec='libx264') if video else None
    camera=mujoco.MjvCamera();camera.lookat[:]=[.02,-.02,.18];camera.distance=.4;camera.azimuth=125;camera.elevation=-20
    tensor=lambda x:torch.as_tensor(x,device=device,dtype=torch.float64)
    gen=torch.Generator(device=device).manual_seed(seed)
    levels=torch.tensor([.2,.6,1.0,1.4],device=device,dtype=torch.float64)[:,None].expand(4,4).clone()
    levels+=torch.randn((4,4),device=device,dtype=torch.float64,generator=gen)*.025
    records=[];timestep=physics['timestep_seconds'];steps=round(2.4/timestep)
    try:
        for step in range(steps+1):
            data.ctrl[ids]=gravity.target(q.tolist(),data.qpos[qadr],np.eye(3))
            phase=min(3,int(data.time/.6));data.ctrl[load]=levels[phase].tolist()
            mujoco.mj_forward(model,data)
            if step%10==0 and data.time% .6>.40:
                measured=[];truth=[]
                for f,body in zip(['if','mf','rf','th'],bodies):
                    site,start,count=bridge.bindings[f]
                    raw=tensor(data.sensordata[start:start+count].copy()).reshape(3,-1).sum(-1)[[1,2,0]]
                    measured.append(tensor(data.site_xmat[site]).reshape(3,3)@raw)
                    total=torch.zeros(3,device=device,dtype=torch.float64)
                    for ci,c in enumerate(data.contact[:data.ncon]):
                        b1,b2=int(model.geom_bodyid[c.geom1]),int(model.geom_bodyid[c.geom2])
                        if body not in [b1,b2]:continue
                        force=np.zeros(6);mujoco.mj_contactForce(model,data,ci,force)
                        world=tensor(c.frame).reshape(3,3).T@tensor(force[:3])
                        total+=world if b2==body else -world
                    truth.append(total)
                records.append({'time_s':float(data.time),'phase':phase,'sensor_force_world_n':torch.stack(measured).tolist(),
                    'private_contact_force_world_n':torch.stack(truth).tolist(),'probe_displacement_m':data.qpos[probes].tolist(),
                    'joint_position_rad':data.qpos[qadr].tolist()})
            if writer and step%20==0:
                renderer.update_scene(data,camera=camera);writer.append_data(renderer.render())
            if step<steps:mujoco.mj_step(model,data)
    finally:
        if writer:writer.close();renderer.close()
    return records,surfaces


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--reference',type=Path);p.add_argument('--trials',type=int,default=40)
    args=p.parse_args();device,gpu=require_cuda();start=time.monotonic()
    if args.trials not in [4,40]:raise ValueError('Use four-trial pilot or frozen twenty-fit/twenty-verify design')
    root=Path(__file__).resolve().parents[1];cfg=json.loads((root/'configs/r4-p1p2.json').read_text())
    physics=json.loads((root/'configs/r4-stage1.json').read_text())['physics'];asset=Path(os.environ['R4_DATA_ROOT'])/'assets/leap_hand'
    q0=torch.tensor([.8,0,.8,.5]*3+[.6,.6,.8,.4],device=device,dtype=torch.float64)
    if args.reference:
        frames=json.loads(args.reference.read_text())['frames'];q0=torch.tensor(min(frames,key=lambda f:abs(f['time_s']-2))['joint_position'],device=device,dtype=torch.float64)
    args.output.mkdir(parents=True,exist_ok=False)
    results=[];slopes=[];force_errors=[]
    split=args.trials//2
    for i in range(args.trials):
        seed=(3101+i) if i<split else (4101+i-split)
        gen=torch.Generator(device=device).manual_seed(seed)
        q=q0+torch.randn((16,),device=device,dtype=torch.float64,generator=gen)*.02
        limits=torch.tensor(JOINT_LIMITS,device=device,dtype=q.dtype)
        q=q.clamp(limits[:,0]+.001,limits[:,1]-.001)
        records,surfaces=trial(asset,cfg['sensor'],physics,q,seed,device,args.output/'full-hand-load.mp4' if i==0 else None)
        write_json(args.output/f'trial-{seed}.json',{'role':'private_calibration_evaluation','seed':seed,'partition':'fit' if i<split else 'verify','records':records,'known_hand_surfaces':surfaces})
        measured=torch.tensor([r['sensor_force_world_n'] for r in records],device=device,dtype=torch.float64)
        truth=torch.tensor([r['private_contact_force_world_n'] for r in records],device=device,dtype=torch.float64)
        errors=(measured-truth).norm(dim=-1);force_errors.append(float(errors.max()))
        phases=torch.tensor([r['phase'] for r in records],device=device)
        displacements=torch.tensor([r['probe_displacement_m'] for r in records],device=device,dtype=torch.float64)
        force=torch.stack([measured[phases==p].norm(dim=-1).mean(0) for p in range(4)])
        distance=torch.stack([displacements[phases==p].mean(0) for p in range(4)])
        delta_f=force[1:]-force[:-1];delta_x=distance[1:]-distance[:-1]
        valid=(delta_f>.1)&(delta_x>0)
        local=torch.where(valid,delta_x/delta_f.clamp_min(1e-8),torch.full_like(delta_f,float('nan')))
        slopes.append(local)
        results.append({'seed':seed,'max_force_error_n':float(errors.max()),'loads_n':force.tolist(),'displacement_m':distance.tolist(),
                        'valid_positive_slopes':int(valid.sum()),'all_fingers_loaded':bool((force.max(0).values>.2).all())})
        write_json(args.output/'progress.json',{'status':'running','trials':results})
    fitted=torch.stack(slopes[:split]);finite=torch.isfinite(fitted)
    bound=float(fitted[finite].min())*.5 if bool(finite.any()) else None
    verification=torch.stack(slopes[split:]);valid=torch.isfinite(verification)
    bound_pass=bound is not None and bool(valid.all()) and bool((verification[valid]>=bound).all())
    checks={'full_hand_load':max(force_errors)<=cfg['acceptance']['force_tolerance_n'] and all(x['all_fingers_loaded'] for x in results),
            'conservative_force_bound':bound_pass,'disjoint_fit_verify_seeds':True}
    status='failed' if not all(checks.values()) else ('passed' if args.trials==40 else 'awaiting_verification')
    write_json(args.output/'result.json',{'status':status,
        'checks':checks,'scope':'Local articulated LEAP loading and actuator/probe compliance only; object-belief coverage remains separate',
        'minimum_empirical_probe_compliance_m_per_n':bound,'trials':results,'gpu':gpu,'wall_s':time.monotonic()-start,
        'pose_compliance_coverage':'awaiting_verification','reference_sha256':sha256(args.reference) if args.reference else None,
        'source_sha256':sha256(__file__),'heldout_used':False,'peak_cuda_bytes':torch.cuda.max_memory_allocated(),
        'native_sensor':load_sensor(),'gravity_compensation':'Separate hand-only gravity model',
        'sources_sha256':{str(Path(__file__).parent/n):sha256(Path(__file__).parent/n) for n in ['calibrate-r4-full-hand-gpu.py','r4_hand_gravity.py','r4_sensor_bridge.py','r4_native_sensor.py']},
        'artifacts_sha256':{str(p):sha256(p) for p in args.output.iterdir() if p.is_file() and p.name!='result.json'}})


if __name__=='__main__':main()
