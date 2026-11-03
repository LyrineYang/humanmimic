#!/usr/bin/env python3
"""Batched CUDA reference-grasp proposals from public RGB-D, never object truth.

Only the known LEAP model is imported. Collision/physical evaluation is a later,
independent step. Proposal success is not grasp success and may not open gates.
"""
import argparse
import itertools
import json
import os
from pathlib import Path
import time
import xml.etree.ElementTree as ET
import mujoco
import numpy as np
import torch
from r4_contract import JOINT_NAMES, validate_contract, sha256, write_json
from r4_cuda import require_cuda
from r4_hand_model import HandModel, export_hand, rotation
from r4_sensor_bridge import instrument


def hand_model(asset, sensor):
    root=ET.parse(asset/'right_hand.xml').getroot()
    root.find('compiler').set('meshdir',str((asset/'assets').resolve()))
    instrument(root,sensor)
    return mujoco.MjModel.from_xml_string(ET.tostring(root,encoding='unicode'))


class HandCollision:
    def __init__(self, model, device):
        self.device=device
        t=lambda x:torch.as_tensor(x,device=device,dtype=torch.float64)
        self.palm=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,'palm')
        joint_index={mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_JOINT,n):i for i,n in enumerate(JOINT_NAMES)}
        self.bodies=[]
        for body in range(self.palm+1,model.nbody):
            joints=[]
            for j in range(model.body_jntadr[body],model.body_jntadr[body]+model.body_jntnum[body]):
                if j not in joint_index: continue
                axis=t(model.jnt_axis[j]); x,y,z=axis.unbind();zero=x*0
                k=torch.stack([zero,-z,y,z,zero,-x,-y,x,zero]).reshape(3,3)
                joints.append((joint_index[j],k,k@k,t(model.jnt_pos[j])))
            self.bodies.append((body,int(model.body_parentid[body]),t(model.body_pos[body]),rotation(t(model.body_quat[body])),joints))
        self.geoms=[]
        self.pad_contacts=[]
        for g in range(model.ngeom):
            if not (model.geom_contype[g] or model.geom_conaffinity[g]): continue
            body=int(model.geom_bodyid[g]);name=mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_GEOM,g) or ''
            if body<self.palm: continue
            if model.geom_type[g]==mujoco.mjtGeom.mjGEOM_BOX:
                # Corners alone miss an object intersecting the middle of a box.
                face=[]
                for axis in range(3):
                    other=[k for k in range(3) if k!=axis]
                    for sign in [-1,1]:
                        for u,v in itertools.product([-1,-.5,0,.5,1],repeat=2):
                            point=[0,0,0];point[axis]=sign;point[other[0]]=u;point[other[1]]=v;face.append(point)
                vertices=t(face)*t(model.geom_size[g])
            elif model.geom_type[g]==mujoco.mjtGeom.mjGEOM_MESH:
                mesh=model.geom_dataid[g]; start,count=model.mesh_vertadr[mesh],model.mesh_vertnum[mesh]
                vertices=t(model.mesh_vert[start:start+count])
                indices=torch.linspace(0,len(vertices)-1,min(128 if name.endswith('_tip') else 32,len(vertices)),device=device).long()
                vertices=vertices[indices]
            else: raise ValueError('Unknown hand collision shape')
            vertices=vertices@rotation(t(model.geom_quat[g])).T+t(model.geom_pos[g])
            finger=['if','mf','rf','th'].index(name[:2]) if name.endswith('_tip') else -1
            self.geoms.append((body,vertices,finger))
            if finger>=0:
                weights=torch.softmax(-(vertices[:,1]-vertices[:,1].min())/.0005,dim=0)
                point=(vertices*weights[:,None]).sum(0)
                self.pad_contacts.append((finger,body,point,t([0,-1,0])))
        self.eye=torch.eye(3,device=device,dtype=torch.float64)

    def forward(self,q,wrist):
        transforms={self.palm:(wrist[:,:3,:3],wrist[:,:3,3])}
        for body,parent,pos,rot,joints in self.bodies:
            r,p=transforms[parent]; p=p+(r@pos);r=r@rot
            for index,k,k2,pivot in joints:
                a=q[:,index,None,None];turn=self.eye+a.sin()*k+(1-a.cos())*k2
                p=p+(r@(pivot-turn@pivot)[...,None]).squeeze(-1);r=r@turn
            transforms[body]=(r,p)
        points=[];tip=[]
        for body,vertices,finger in self.geoms:
            r,p=transforms[body];points.append(vertices@r.transpose(-1,-2)+p[:,None,:]);tip.extend([finger]*len(vertices))
        contacts=[None]*4;normals=[None]*4
        for finger,body,point,normal in self.pad_contacts:
            r,p=transforms[body];contacts[finger]=(r@point)+p;normals[finger]=r@normal
        return torch.cat(points,dim=1),torch.tensor(tip,device=q.device),torch.stack(contacts,1),torch.stack(normals,1)


def cube_rotations(device):
    values=[]
    for permutation in itertools.permutations(range(3)):
        for signs in itertools.product([-1,1],repeat=3):
            r=torch.zeros((3,3),device=device,dtype=torch.float64)
            for i,j in enumerate(permutation): r[i,j]=signs[i]
            if float(torch.linalg.det(r))>.5: values.append(r)
    return torch.stack(values)


def reference(q_open,q_close,wrist,center,task,dt=.02,closing_path=None):
    device=q_open.device
    from r4_grasp_quaternion import matrix_quaternion
    t=torch.arange(601,device=device,dtype=q_open.dtype)*dt
    close=((t-1.0)/1.5).clamp(0,1)
    release=((t-9)/.75).clamp(0,1) if task=='precision_place' else t*0
    phase=close*(1-release)
    if closing_path is None:
        joints=q_open+(q_close-q_open)*phase[:,None]
    else:
        where=phase*(len(closing_path)-1);index=where.floor().long().clamp_max(len(closing_path)-2)
        joints=closing_path[index]+(closing_path[index+1]-closing_path[index])*(where-index)[:,None]
    lift=((t-3.0)/1.5).clamp(0,1)*.11
    approach=(1-t.clamp(0,1))*.06
    transport=((t-6.8)/1.2).clamp(0,1) if task=='precision_place' else t*0
    lower=((t-8.0)/1.0).clamp(0,1) if task=='precision_place' else t*0
    angle=transport*torch.pi/6;c=angle.cos();sn=angle.sin()
    offset=wrist[:3,3]-center
    positions=center+torch.stack([c*offset[0]-sn*offset[1],sn*offset[0]+c*offset[1],t*0+offset[2]],-1)
    positions+=torch.stack([.08*transport,t*0,approach+lift*(1-lower)+.12*release],-1)
    q0=matrix_quaternion(wrist[:3,:3]);c=(angle/2).cos();sn=(angle/2).sin()
    quaternions=torch.stack([c*q0[0]-sn*q0[3],c*q0[1]-sn*q0[2],c*q0[2]+sn*q0[1],c*q0[3]+sn*q0[0]],-1)
    frames=[{'time_s':time,'source_index':i,'joint_position':j,'wrist_position':p,'wrist_quaternion':q}
            for i,(time,j,p,q) in enumerate(zip(t.tolist(),joints.tolist(),positions.tolist(),quaternions.tolist()))]
    return {'schema_version':1,'kind':'synthetic_fixture','split':'debug','hand':'leap_right','joint_names':JOINT_NAMES,
            'units':{'length':'m','angle':'rad','time':'s'},'frame':'world_z_up','quaternion_order':'wxyz','frames':frames,
            'provenance':{'generator':'prepare-r4-grasps-gpu.py','source':'public multiview RGB-D plus known hand geometry; not video reconstruction'}}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--observations',type=Path,required=True);p.add_argument('--object-id',required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--batch',type=int,default=96)
    p.add_argument('--steps',type=int,default=250);p.add_argument('--keep',type=int,default=12)
    p.add_argument('--fingers',choices=['all','middle_thumb'],default='all')
    p.add_argument('--contact-mode',choices=['nearest_surface','opposing_pad','support_plane'],default='support_plane')
    p.add_argument('--preload',type=float,default=.0002)
    p.add_argument('--opening-distance',type=float,default=.008)
    args=p.parse_args();device,gpu=require_cuda();start=time.monotonic()
    if not 0 <= args.preload <= .001 or not .002 <= args.opening_distance <= .03:raise ValueError('Reference search preload/opening outside declared bounds')
    root=Path(__file__).resolve().parents[1]
    sensor=json.loads((root/'configs/r4-p1p2.json').read_text())['sensor']
    asset=Path(os.environ['R4_DATA_ROOT'])/'assets/leap_hand'
    model=hand_model(asset,sensor);hand=HandModel(export_hand(model),device);collision=HandCollision(model,device)
    raw=np.load(args.observations,allow_pickle=False)
    points=torch.as_tensor(raw['points'],device=device,dtype=torch.float64)
    # The published mechanism scan was acquired in a centred scan rig, not the
    # tabletop world. Locate it using the observed bottom and known support plane;
    # do not read the private simulator initial_position to repair this mismatch.
    scan_to_table_z=-torch.quantile(points[:,2],.001)+.001
    points=points.clone();points[:,2]+=scan_to_table_z
    low,high=torch.quantile(points,torch.tensor([.005,.995],device=device,dtype=points.dtype),dim=0)
    center=(low+high)/2;half=(high-low)/2
    rotations=cube_rotations(device);n=args.batch
    gen=torch.Generator(device=device).manual_seed(51101)
    q0=hand.tensor([.8,0,.8,.5]*3+[.6,.6,.8,.4]).expand(n,16).clone()
    if args.fingers=='middle_thumb':
        q0[:,0:4]=0;q0[:,8:12]=0
    q=torch.nn.Parameter((q0+torch.randn((n,16),generator=gen,device=device,dtype=q0.dtype)*.25).clamp(hand.ranges[:,0],hand.ranges[:,1]))
    if args.fingers=='middle_thumb':
        with torch.no_grad():q[:,0:4]=0;q[:,8:12]=0
    rot=rotations[torch.arange(n,device=device)%len(rotations)]
    ident=torch.eye(4,device=device,dtype=torch.float64)
    initial_sites=hand.forward(q.detach(),ident)[:,:,:3,3]
    position=torch.nn.Parameter(center-(rot@initial_sites.mean(1)[...,None]).squeeze(-1))
    target=center.expand(n,4,3).clone()
    # Aim known pad surfaces slightly inside the observed surface to generate
    # preload via the unchanged joint servo; physics separately rejects >2mm.
    target[:,0:3,0]+=half[0]-args.preload; target[:,3,0]-=half[0]-args.preload
    target[:,0,1]-=half[1]*.65;target[:,2,1]+=half[1]*.65
    target[:,:,2]-=half[2]*.25
    # Bounding-box side targets may lie in empty space for stepped/necked shapes.
    # Snap each desired contact to an actually observed, oppositely facing side.
    scan_normals=torch.as_tensor(raw['normals'],device=device,dtype=torch.float64)
    for finger in range(4):
        sign=1 if finger<3 else -1
        valid=scan_normals[:,0]*sign>.8
        if not bool(valid.any()):raise ValueError('No observed opposing side for this grasp')
        candidates=points[valid]
        score=(candidates-target[0,finger]).square().sum(-1)
        contact=candidates[score.argmin()].clone();contact[0]-=sign*args.preload
        target[:,finger]=contact
    optimizer=torch.optim.Adam([q,position],lr=.015)
    def optimize(target,steps):
        for step in range(steps):
            optimizer.zero_grad(set_to_none=True)
            wrist=ident.expand(n,4,4).clone();wrist[:,:3,:3]=rot;wrist[:,:3,3]=position
            vertices,tip,contacts,pad_normals=collision.forward(q,wrist)
            if args.contact_mode in ['nearest_surface','support_plane']:
                contact_list=[]
                for finger in range(4):
                    pad=vertices[:,tip==finger]
                    if args.contact_mode=='nearest_surface':
                        dist=(pad-target[:,finger,None,:]).square().sum(-1)
                        weights=torch.softmax(-dist/(.003**2),dim=1)
                    else:
                        # The innermost support surface must meet the object.
                        # Nearest-point fitting alone permits the rest of a pad
                        # to pass through the object and eject it during physics.
                        weights=torch.softmax(pad[:,:,0]*(-1 if finger<3 else 1)/.0003,dim=1)
                    contact_list.append((pad*weights[...,None]).sum(1))
                contacts=torch.stack(contact_list,dim=1)
            d=(vertices-center).abs()-half
            inside=torch.relu(-d.amax(-1))
            active_fingers=[0,1,2,3] if args.fingers=='all' else [1,3]
            loss=(contacts[:,active_fingers]-target[:,active_fingers]).square().sum(-1).mean(-1)
            if args.contact_mode=='opposing_pad':
                desired_normals=torch.zeros_like(pad_normals);desired_normals[:,:3,0]=-1;desired_normals[:,3,0]=1
                loss+=.0001*(pad_normals[:,active_fingers]-desired_normals[:,active_fingers]).square().sum(-1).mean(-1)
            loss+=10*torch.relu(.003-vertices[:,:,2]).square().amax(-1)
            loss+=10*inside[:,tip<0].square().amax(-1)
            loss+=.00001*(q-q0).square().mean(-1)
            loss.sum().backward()
            if args.fingers=='middle_thumb':q.grad[:,0:4]=0;q.grad[:,8:12]=0
            optimizer.step()
            with torch.no_grad():q.clamp_(hand.ranges[:,0],hand.ranges[:,1])
        return loss.detach(),wrist.detach(),q.detach().clone()
    loss,wrist,q_close=optimize(target,args.steps)
    wrist[:,:3,3]=position.detach()
    selected=torch.argsort(loss)[:args.keep]
    selected_scores=loss[selected].clone();batch_ids=selected.tolist()
    # Solve a continuous Cartesian opening path, then reverse it for closing.
    # Interpolating unrelated endpoint IK joint solutions can sweep the object away.
    q_close=q_close[selected];wrist=wrist[selected];rot=rot[selected];q0=q0[selected]
    target=target[selected];closed_targets=target.clone();n=len(selected)
    q=torch.nn.Parameter(q_close.clone());position=wrist[:,:3,3].clone()
    optimizer=torch.optim.Adam([q],lr=.015)
    opening=[q_close.clone()]
    for step in range(1,16):
        target=closed_targets.clone();target[:,:3,0]+=args.opening_distance*step/15;target[:,3,0]-=args.opening_distance*step/15
        _,_,q_open=optimize(target,30);opening.append(q_open.clone())
    paths=torch.stack(opening).flip(0)
    args.output.mkdir(parents=True,exist_ok=False)
    proposals=[]
    for rank,index in enumerate(range(n)):
        for task in ['lift_hold','precision_place']:
            contract=reference(q_open[index],q_close[index],wrist[index],center,task,closing_path=paths[:,index])
            validate_contract(contract)
            write_json(args.output/f'candidate-{rank:02d}-{task}.json',contract)
        proposals.append({'candidate':rank,'batch_index':batch_ids[index],'score_m2':float(selected_scores[index]),'wrist':wrist[index].tolist(),
                          'q_open':q_open[index].tolist(),'q_close':q_close[index].tolist()})
    write_json(args.output/'result.json',{'status':'awaiting_verification','execution_status':'completed','gpu':gpu,'object_id':args.object_id,
        'proposals':proposals,'observed_center':center.tolist(),'observed_half_extent':half.tolist(),'wall_s':time.monotonic()-start,
        'peak_cuda_bytes':torch.cuda.max_memory_allocated(),'observation_sha256':sha256(args.observations),
        'contact_mode':args.contact_mode,'preload_m':args.preload,'opening_distance_m':args.opening_distance,
        'scan_to_table_translation_z':float(scan_to_table_z),'localization_assumption':'scan upright; observed lower envelope on known z=0 support plane plus 1mm clearance',
        'source_sha256':sha256(__file__),'claim':'Geometric proposals only; independent physics must establish success'})


if __name__=='__main__': main()
