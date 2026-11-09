#!/usr/bin/env python3
"""Contact correction on a bounded post-grasp test rig, CUDA belief + EGL.

The block starts rigidly clamped. This deliberately isolates placement from
grasp synthesis; no LEAP/learned-policy/shape-reconstruction claim is made.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import time

import imageio.v2 as imageio
import mujoco
import numpy as np
import torch

from r4_contact_offset import ContactObservation, ContactOffsetMemory
from r4_campaign import digest, write


def scene(offset, width_error, goal):
    half = .025 + width_error
    return f'''<mujoco model="contact_offset_rig">
      <option timestep="0.002" gravity="0 0 -9.81" iterations="100"/>
      <visual><global offwidth="960" offheight="720"/><headlight ambient=".4 .4 .4" diffuse=".7 .7 .7"/></visual>
      <asset><texture type="2d" name="grid" builtin="checker" rgb1=".15 .19 .25" rgb2=".19 .24 .30" width="128" height="128"/>
        <material name="floor_mat" texture="grid" texrepeat="8 8" reflectance=".1"/></asset>
      <default><geom friction=".8 .005 .0001" solref=".004 1" solimp=".98 .999 .001"/>
        <joint damping="2"/><position kp="500" kv="12" forcelimited="true" forcerange="-8 8"/></default>
      <worldbody>
        <light pos="0 -.3 .8" dir="0 0 -1" diffuse=".9 .9 .9"/>
        <geom name="table" type="plane" size=".5 .5 .01" material="floor_mat"/>
        <geom name="datum" type="box" pos=".15 -.14 .06" size=".01 .07 .06" rgba=".25 .65 .85 1"/>
        <geom name="target" type="box" pos="{goal-.025} .10 .0005" size=".025 .025 .0005" rgba=".2 .95 .6 .35" contype="0" conaffinity="0"/>
        <geom name="edge_goal" type="box" pos="{goal} .10 .001" size=".0006 .04 .001" rgba=".2 1 .7 1" contype="0" conaffinity="0"/>
        <body name="carriage" pos="0 0 0">
          <joint name="x" type="slide" axis="1 0 0"/>
          <joint name="y" type="slide" axis="0 1 0"/>
          <joint name="z" type="slide" axis="0 0 1"/>
          <inertial pos="0 0 .04" mass=".15" diaginertia=".001 .001 .001"/>
          <body name="clamp">
            <inertial pos="0 0 0" mass=".10" diaginertia=".001 .001 .001"/>
            <site name="wrist" size=".004" rgba="1 1 1 1"/>
            <geom type="box" pos="0 0 .025" size=".045 .035 .008" rgba=".55 .65 .76 1" contype="0" conaffinity="0"/>
            <geom type="box" pos="0 -.03 0" size=".04 .006 .022" rgba=".5 .6 .7 1" contype="0" conaffinity="0"/>
            <geom type="box" pos="0 .03 0" size=".04 .006 .022" rgba=".5 .6 .7 1" contype="0" conaffinity="0"/>
          </body>
        </body>
        <body name="object" pos="{.025+offset} -.14 .09">
          <freejoint name="object_free"/>
          <geom name="block" type="box" size="{half} .023 .025" mass=".06" rgba="1 .55 .16 1"/>
        </body>
      </worldbody>
      <actuator><position name="mx" joint="x"/><position name="my" joint="y"/><position name="mz" joint="z"/></actuator>
      <equality><weld name="stable_clamp" body1="clamp" body2="object" relpose="{offset} 0 -.02 1 0 0 0" solref=".004 1"/></equality>
      <sensor><force name="wrist_force" site="wrist"/></sensor>
    </mujoco>'''


def episode(out, offset, width_error, correction, video, seed, goal=.075, memory=None):
    out.mkdir(parents=True, exist_ok=False)
    xml = scene(offset, width_error, goal)
    (out/'scene.xml').write_text(xml)
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    data.qpos[:3] = [.025, -.14, .11]
    data.ctrl[:] = data.qpos[:3]
    mujoco.mj_forward(model, data)
    belief = memory or ContactOffsetMemory('fixed-clamp-1')
    renderer = mujoco.Renderer(model, 720, 960) if video else None
    camera = mujoco.MjvCamera()
    camera.lookat[:] = [.07, -.025, .035]
    camera.distance, camera.azimuth, camera.elevation = .62, 135, -48
    writer = imageio.get_writer(out/'execution.mp4', fps=25, codec='libx264',
                                quality=8, macro_block_size=1, ffmpeg_params=['-threads','2']) if video else None
    public, truth = [], []
    saved={'time':[float(data.time)],'qpos':[data.qpos.copy()],
           'qvel':[data.qvel.copy()],'ctrl':[data.ctrl.copy()]}
    last_frame, peak_force = -1, 0.
    rng = torch.Generator(device='cuda').manual_seed(seed)
    # All measurement noise is pre-generated on CUDA, never from private truth.
    encoder_noise = torch.randn(30000, generator=rng, device='cuda', dtype=torch.float64)*.00005
    sample_index = 0
    phase = 'settle'

    def step(target):
        nonlocal last_frame, peak_force, sample_index
        data.ctrl[:] = target
        mujoco.mj_step(model, data)
        saved['time'].append(float(data.time))
        for name in ['qpos','qvel','ctrl']:saved[name].append(getattr(data,name).copy())
        force = abs(float(data.sensordata[0]))
        if phase == 'probe': peak_force = max(peak_force, force)
        hand = float(data.qpos[0]) + encoder_noise[sample_index].item()
        sample_index += 1
        public.append({'time_s':data.time, 'phase':phase, 'hand_x_m':hand,
                       'wrist_force_x_n':force, 'target_x_m':float(target[0]),
                       'estimate_m':belief.mean.item(), 'estimate_valid':belief.valid})
        # Evaluation-only values never enter ContactObservation or target().
        gid = model.geom('block').id
        extent_x = float(np.abs(data.geom_xmat[gid].reshape(3, 3)[0]) @ model.geom_size[gid])
        truth.append({'time_s':data.time,'object_x_m':float(data.xpos[model.body('object').id,0]),
                      'object_z_m':float(data.xpos[model.body('object').id,2]),
                      'edge_x_m':float(data.geom_xpos[gid,0])+extent_x})
        if writer and int(data.time*25+1e-8)>last_frame:
            renderer.update_scene(data, camera=camera)
            writer.append_data(renderer.render())
            last_frame = int(data.time*25+1e-8)
        if not np.isfinite(data.qpos).all(): raise RuntimeError('Nonfinite physics')
        return hand, force

    def move(target, seconds):
        start = data.ctrl.copy()
        count = round(seconds/model.opt.timestep)
        for i in range(count):
            u=(i+1)/count; smooth=u*u*(3-2*u)
            step(start+(np.asarray(target)-start)*smooth)

    detected = False
    try:
        move([.025,-.14,.11],.5)
        if memory is None:
            phase = 'probe'
            target = data.ctrl.copy()
            for i in range(3000):
                target[0] += .00004  # 20 mm/s, same action in both arms.
                hand, force = step(target)
                if force >= .35:
                    detected = belief.update(ContactObservation('fixed-clamp-1','plane-touch-1',hand,.14,(1.,0.,0.),force))
                    break
                if target[0] > .145: break
            if not detected: raise RuntimeError('No valid low-force contact; refuse correction')
            phase = 'withdraw'
            move([data.qpos[0]-.018,-.14,.11],.5)
        else:
            detected = memory.valid
        phase = 'transport'
        xgoal = belief.target(goal,'fixed-clamp-1').item() if correction else goal-.025
        move([xgoal,.10,.11],1.5)
        phase = 'place'
        move([xgoal,.10,.047],1.5)
        move([xgoal,.10,.047],.4)
        phase = 'release'
        data.eq_active[0] = 0
        move([xgoal,.10,.13],1.)
        phase = 'settle'
        move([xgoal,.10,.13],.5)
        final = truth[-1]
        err = abs(final['edge_x_m']-goal)
        result={'execution_status':'passed','correction':correction,'seed':seed,
                'scope':'Post-grasp simplified rigid clamp, one task-normal offset; not LEAP or pretrained policy',
                'offset_truth_m':offset,'width_error_truth_m':width_error,
                'final_edge_error_mm':err*1000, 'peak_probe_force_n':peak_force,
                'probe_count':0 if memory else 1, 'sim_time_s':data.time,
                'object_final_height_m':final['object_z_m'], 'memory':belief.snapshot(),
                'task_status':'passed' if err<=.002 and peak_force<=2 and abs(final['object_z_m']-.025)<.002 else 'failed'}
        write(out/'result.json',result)
        for name,rows in [('public-observations.csv',public),('private-evaluation.csv',truth)]:
            with (out/name).open('w') as stream:
                w=csv.DictWriter(stream,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
        return result,belief
    finally:
        if writer:writer.close()
        if renderer:renderer.close()
        np.savez_compressed(out/'actual-states.npz',**{k:np.asarray(v) for k,v in saved.items()})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--offset-mm',type=float,default=8)
    p.add_argument('--width-error-mm',type=float,default=0)
    p.add_argument('--seed',type=int,default=3101)
    p.add_argument('--video',action='store_true')
    args=p.parse_args()
    if args.video and not json.loads((Path(__file__).resolve().parents[1]/'configs/budget.json').read_text())['local_demo_campaign'].get('video_generation_authorized',False):
        p.error('Current user instruction disables video generation; save state bundles instead')
    if not -12 <= args.offset_mm <= 12 or not 0 <= args.width_error_mm <= 4:
        p.error('Development rig supports offsets [-12,12] mm and extent errors [0,4] mm only')
    if not torch.cuda.is_available():raise RuntimeError('CUDA required')
    args.output.mkdir(parents=True,exist_ok=False)
    baseline,_=episode(args.output/'force-only',args.offset_mm/1000,args.width_error_mm/1000,False,args.video,args.seed)
    corrected,memory=episode(args.output/'contact-corrected',args.offset_mm/1000,args.width_error_mm/1000,True,args.video,args.seed)
    reused,_=episode(args.output/'memory-reused',args.offset_mm/1000,args.width_error_mm/1000,True,args.video,args.seed,goal=.105,memory=memory)
    # Independent executions initialize the same fixed clamp transform. No
    # regrasp-generalization claim is made for this controlled reuse condition.
    check=ContactOffsetMemory('test')
    assert not check.update(ContactObservation('test','none',0,.14,(1.,0.,0.),0))
    assert not check.update(ContactObservation('test','wrong-normal',0,.14,(0.,1.,0.),.5))
    try:memory.target(.1,'changed-grasp')
    except ValueError:pass
    else:raise AssertionError('Stale grasp accepted')
    before=memory.snapshot()
    assert not memory.update(ContactObservation('fixed-clamp-1','plane-touch-1',0,.14,(1.,0.,0.),.5))
    assert memory.snapshot()==before
    result={'gpu':torch.cuda.get_device_name(),'torch':torch.__version__,'mujoco':mujoco.__version__,
            'source_sha256':{str(Path(__file__).resolve()):digest(Path(__file__).resolve()),
                             str(Path(__file__).with_name('r4_contact_offset.py').resolve()):digest(Path(__file__).with_name('r4_contact_offset.py'))},
            'baseline':baseline,'corrected':corrected,'reused':reused,
            'observation_contract_checks':4,'training':False,'heldout':False,
            'status':'passed' if corrected['task_status']=='passed' and reused['task_status']=='passed' and corrected['final_edge_error_mm']<=baseline['final_edge_error_mm']*.5 else 'failed'}
    write(args.output/'result.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
