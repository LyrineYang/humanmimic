#!/usr/bin/env python3
"""Verify saved dynamics states on CUDA without a renderer or video encoder."""
import argparse
import csv
import json
from pathlib import Path

import mujoco
import numpy as np
import torch

from r4_campaign import digest, write


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--kind',choices=['vividex','contact'],required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if not torch.cuda.is_available():raise RuntimeError('CUDA required')
    rows=[]
    patterns='episode-*-states.npz' if args.kind=='vividex' else '*/actual-states.npz'
    files=sorted(args.root.glob(patterns))
    if len(files)!=3:raise ValueError('Expected three complete archived executions')
    for path in files:
        if args.kind=='vividex':
            model_path=path.with_name(path.name.replace('-states.npz','-model.mjb'))
            model=mujoco.MjModel.from_binary_path(str(model_path))
            csv_path=path.with_name(path.name.replace('-states.npz','.csv'))
            names=('object_x','object_y','object_z')
            object_id=45
        else:
            model_path=path.with_name('scene.xml')
            model=mujoco.MjModel.from_xml_path(str(model_path))
            csv_path=path.with_name('private-evaluation.csv')
            names=('object_x_m','object_z_m')
            object_id=model.body('object').id
        with np.load(path,allow_pickle=False) as data:
            tensors={k:torch.as_tensor(data[k],device='cuda') for k in data.files}
            assert all(torch.isfinite(v).all().item() for v in tensors.values())
            n=tensors['time'].shape[0]
            assert tensors['qpos'].shape==(n,model.nq)
            assert tensors['qvel'].shape==(n,model.nv)
            assert tensors['ctrl'].shape==(n,model.nu)
            assert torch.all(tensors['time'][1:]>tensors['time'][:-1]).item()
            restored=mujoco.MjData(model)
            restored.qpos[:]=data['qpos'][-1]
            restored.qvel[:]=data['qvel'][-1]
            restored.ctrl[:]=data['ctrl'][-1]
            mujoco.mj_forward(model,restored)
        with csv_path.open() as stream:csv_rows=list(csv.DictReader(stream))
        assert len(csv_rows)+1==n
        expected=torch.tensor([float(csv_rows[-1][k]) for k in names],device='cuda',dtype=torch.float64)
        actual=restored.xpos[object_id].copy()
        if args.kind=='contact':actual=actual[[0,2]]
        error=torch.linalg.vector_norm(torch.as_tensor(actual,device='cuda')-expected).item()
        # mj_step-derived positions can lag the last integration by one substep.
        # The terminal settling state must reproduce within 10 micrometres.
        assert error<=1e-5,(str(path),error)
        rows.append({'state_file':str(path),'state_sha256':digest(path),'model_sha256':digest(model_path),
                     'samples':n,'final_position_restore_error_m':error})
    write(args.output,{'status':'passed','gpu':torch.cuda.get_device_name(),'mujoco':mujoco.__version__,
                       'rendering':False,'new_video':False,'rows':rows})
    print(json.dumps({'status':'passed','archives':len(rows),'new_video':False}))


if __name__=='__main__':main()
