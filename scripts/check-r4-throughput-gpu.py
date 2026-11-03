#!/usr/bin/env python3
"""GPU numerical equivalence checks before enabling throughput changes."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import torch
from r4_cuda import require_cuda
from r4_contract import sha256, write_json
from r4_hand_model import HandModel, export_hand, rotation
from r4_belief import so3,skew
from r4_grasp_quaternion import matrix_quaternion


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--before',type=Path,required=True)
    p.add_argument('--after',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();device,gpu=require_cuda();a=json.loads(args.before.read_text())['beliefs'][-1];b=json.loads(args.after.read_text())['beliefs'][-1]
    tensor=lambda x:torch.as_tensor(x,device=device,dtype=torch.float64)
    pose=(tensor(a['T_world_object'])-tensor(b['T_world_object'])).abs().max()
    shape=(tensor(a['vertices_object_m'])-tensor(b['vertices_object_m'])).abs().max()
    cov=(tensor(a['covariance'])-tensor(b['covariance'])).norm()/tensor(a['covariance']).norm().clamp_min(1e-12)
    compliance=(tensor(a['effective_compliance_m_per_n'])-tensor(b['effective_compliance_m_per_n'])).abs()
    checks={'pose_equivalent':float(pose)<=5e-6,'shape_equivalent':float(shape)<=5e-6,
            'covariance_equivalent':float(cov)<=1e-3,'compliance_equivalent':float(compliance)<=1e-6}
    root=Path(__file__).resolve().parents[1];source=Path(__file__).with_name('prepare-r4-grasps-gpu.py')
    spec=importlib.util.spec_from_file_location('r4_grasp_preparer',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    cfg=json.loads((root/'configs/r4-p1p2.json').read_text())['sensor']
    model=module.hand_model(Path(os.environ['R4_DATA_ROOT'])/'assets/leap_hand',cfg);hand=HandModel(export_hand(model),device)
    gen=torch.Generator(device=device).manual_seed(91101);q=torch.rand((24,16),generator=gen,device=device,dtype=torch.float64)*(hand.ranges[:,1]-hand.ranges[:,0])+hand.ranges[:,0]
    vectors=torch.cat([torch.zeros((1,3),device=device,dtype=torch.float64),tensor([[1e-9,0,0],[torch.pi,0,0]]),torch.randn((32,3),generator=gen,device=device,dtype=torch.float64)])
    vectors.requires_grad_(True);weight=torch.randn((len(vectors),3,3),generator=gen,device=device,dtype=torch.float64)
    closed=so3(vectors);exponential=torch.matrix_exp(skew(vectors))
    grad_closed=torch.autograd.grad((closed*weight).sum(),vectors,retain_graph=True)[0]
    grad_exp=torch.autograd.grad((exponential*weight).sum(),vectors)[0]
    checks['SO3_forward_matches_exponential']=bool(torch.allclose(closed,exponential,atol=1e-12,rtol=1e-12))
    checks['SO3_gradient_matches_exponential']=bool(torch.isfinite(grad_closed).all() and torch.allclose(grad_closed,grad_exp,atol=1e-10,rtol=1e-10))
    checks['SO3_native_vmap_equivalent']=bool(torch.allclose(torch.vmap(so3)(vectors),closed,atol=1e-12,rtol=1e-12))
    wrist=torch.eye(4,device=device,dtype=torch.float64).expand(24,4,4).clone();wrist[:,:3,:3]=module.cube_rotations(device)
    wrist[:,:3,3]=torch.randn((24,3),device=device,dtype=torch.float64,generator=gen)*.1
    batched=hand.forward(q,wrist);serial=torch.stack([hand.forward(q[i],wrist[i]) for i in range(len(q))])
    checks['batched_wrist_fk_equivalent']=bool(torch.allclose(batched,serial,atol=1e-12,rtol=1e-12))
    recovered=torch.stack([rotation(matrix_quaternion(r)) for r in wrist[:,:3,:3]])
    checks['quaternion_pi_branches']=bool(torch.allclose(recovered,wrist[:,:3,:3],atol=1e-12,rtol=1e-12))
    args.output.mkdir(parents=True,exist_ok=False)
    write_json(args.output/'result.json',{'status':'passed' if all(checks.values()) else 'failed','checks':checks,'gpu':gpu,
        'pose_max_difference':float(pose),'shape_max_difference_m':float(shape),'covariance_relative_difference':float(cov),
        'compliance_difference_m_per_n':float(compliance),'before_wall_s':a['wall_s'],'after_wall_s':b['wall_s'],
        'before_peak_cuda_bytes':a['peak_cuda_bytes'],'after_peak_cuda_bytes':b['peak_cuda_bytes'],
        'before_sha256':sha256(args.before),'after_sha256':sha256(args.after),'source_sha256':sha256(__file__),
        'timing_scope':'Different concurrent load; indicative timing, not a controlled speedup benchmark','heldout_used':False})
    if not all(checks.values()):raise SystemExit(1)


if __name__=='__main__':main()
