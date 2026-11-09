#!/usr/bin/env python3
"""Bounded CUDA inference of the official ViViDex state policy, never training.

This policy consumes privileged simulation state. It is not the visual BC
policy and does not ingest a new video. Keep that distinction on the demo.
"""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys

from r4_campaign import digest, write


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--checkpoint-dir',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--episodes',type=int,default=3)
    p.add_argument('--seed',type=int,default=5101)
    p.add_argument('--camera',choices=['front','left','right'],default='front')
    p.add_argument('--scripted-release',action='store_true',help='Explicit post-policy finger opening and withdrawal; not learned')
    p.add_argument('--record-video',action='store_true',help='Opt-in only; default saves states/metrics without rendering')
    args=p.parse_args()
    if args.record_video and not json.loads((Path(__file__).resolve().parents[1]/'configs/budget.json').read_text())['local_demo_campaign'].get('video_generation_authorized',False):
        p.error('Current user instruction disables video generation; save state bundles instead')
    if not 1<=args.episodes<=10:p.error('At most 10 development episodes per invocation')
    source=args.source.resolve(); ckpt=args.checkpoint_dir.resolve()
    sys.path.insert(0,str(source))
    os.environ['MUJOCO_GL']='egl'
    os.environ['WANDB_MODE']='offline'
    import imageio.v2 as imageio
    import numpy as np
    import torch
    import yaml
    from omegaconf import OmegaConf
    from stable_baselines3 import PPO
    from hand_imitation.env.environments.create_env import create_env
    from hand_imitation.env.environments.gym_wrapper import GymWrapper
    if not torch.cuda.is_available():raise RuntimeError('CUDA required; no CPU policy fallback')
    args.output.mkdir(parents=True,exist_ok=False)
    params=OmegaConf.create(yaml.safe_load((ckpt/'exp_config.yaml').read_text())['params'])
    task_kwargs=OmegaConf.to_container(params.env.task_kwargs,resolve=True)
    env_kwargs=OmegaConf.to_container(params.env.env_kwargs,resolve=True)
    identity={'source_commit':subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip(),
              'source_diff':subprocess.check_output(['git','-C',str(source),'diff'],text=True),
              'checkpoint_sha256':digest(ckpt/'restore_checkpoint.zip'),
              'config_sha256':digest(ckpt/'exp_config.yaml'), 'entry_sha256':digest(Path(__file__)),
              'task_kwargs':task_kwargs,'env_name':params.env.name,'seed':args.seed,'camera':args.camera,
              'scripted_release':args.scripted_release,'record_video':args.record_video,
              'scope':'Official pretrained state policy with privileged simulator observations; no new-video learning',
              'gpu':torch.cuda.get_device_name(),'torch':torch.__version__,'training':False,'heldout':False}
    write(args.output/'identity.json',identity)
    policy=PPO.load(str(ckpt/'restore_checkpoint.zip'),device='cuda')
    assert next(policy.policy.parameters()).device.type=='cuda'
    policy.policy.eval()
    env=GymWrapper(create_env(name=params.env.name,robot_name='adroit',task_kwargs=task_kwargs,environment_kwargs=env_kwargs))
    env._base_env._stage=2  # Match the upstream pretrained evaluation entry.
    dt=env.wrapped.control_timestep()
    rows=[]
    def contact_counts():
        hand, target = 0, 0
        object_geoms=set(env.wrapped.task.object_geom_names)
        for c in env.wrapped.physics.data.contact:
            a=env.wrapped.physics.model.id2name(c.geom1,'geom') or ''
            b=env.wrapped.physics.model.id2name(c.geom2,'geom') or ''
            if a not in object_geoms and b not in object_geoms:continue
            other=b if a in object_geoms else a
            hand+=int(other.startswith('adroit/'))
            target+=int(other.startswith('big_mug/'))
        return hand,target
    for ep in range(args.episodes):
        seed=args.seed+ep
        np.random.seed(seed);torch.manual_seed(seed)
        env.wrapped.task._random=np.random.RandomState(seed)
        obs=env.reset()
        if tuple(obs['state'].shape)!=tuple(policy.observation_space.shape):
            raise ValueError(f'Checkpoint/environment observation mismatch: {obs["state"].shape} != {policy.observation_space.shape}')
        video=args.output/f'episode-{ep:02d}.mp4'
        writer=imageio.get_writer(video,fps=1/dt,codec='libx264',quality=8,macro_block_size=1,ffmpeg_params=['-threads','2']) if args.record_video else None
        log=[]; wrist_targets=[]; done=False; total=0.; step=0
        physics=env.wrapped.physics
        import mujoco
        model_file=args.output/f'episode-{ep:02d}-model.mjb'
        mujoco.mj_saveModel(physics.model.ptr,str(model_file),None)
        saved={'time':[float(physics.data.time)],'qpos':[physics.data.qpos.copy()],
               'qvel':[physics.data.qvel.copy()],'ctrl':[physics.data.ctrl.copy()]}
        def save_state():
            saved['time'].append(float(physics.data.time))
            for name in ['qpos','qvel','ctrl']:saved[name].append(getattr(physics.data,name).copy())
        try:
            if writer:writer.append_data(env.render(height=480,width=640,camera_id=args.camera))
            initial_z=float(obs['obj_pos'][2])
            with torch.inference_mode():
                while not done and step<600:
                    action,_=policy.predict(obs['state'],deterministic=True)
                    obs,reward,done,info=env.step(action)
                    save_state()
                    wrist_targets.append(env.wrapped.physics.data.ctrl.copy())
                    step+=1;total+=float(reward)
                    if not np.isfinite(obs['state']).all():raise RuntimeError('Nonfinite observation')
                    hand_contacts,target_contacts=contact_counts()
                    log.append({'step':step,'time_s':step*dt,'phase':'pretrained','object_x':float(obs['obj_pos'][0]),
                                'object_y':float(obs['obj_pos'][1]),'object_z':float(obs['obj_pos'][2]),
                                'goal_x':float(obs['final_goal'][0]),'goal_y':float(obs['final_goal'][1]),
                                'goal_z':float(obs['final_goal'][2]),'reward':float(reward),
                                'hand_object_contacts':hand_contacts,'target_object_contacts':target_contacts})
                    if writer:writer.append_data(env.render(height=480,width=640,camera_id=args.camera))
            if not done:raise RuntimeError('Episode step cap reached')
            policy_endpoint=obs['obj_pos'].copy()
            policy_steps=step
            if args.scripted_release:
                physics=env.wrapped.physics
                start=physics.data.ctrl.copy()
                opened=start.copy();opened[8:]=0.  # Preserve wrist and six root targets.
                # Upward translation is already at its limit in this policy.
                # Reverse the recorded wrist/root targets with fingers open;
                # these are known robot commands, never object truth or a weld.
                retreat=[]
                for previous in reversed(wrist_targets):
                    target=opened.copy();target[:8]=previous[:8]
                    retreat.append(('script-withdraw',target,dt))
                schedule=[('script-open',opened,.6),*retreat,('settle',retreat[-1][1],1.)]
                write(args.output/f'withdrawal-{ep:02d}.json',{'method':'Reverse recorded root/wrist target sequence with fingers open',
                      'policy_control_targets':[x.tolist() for x in wrist_targets], 'no_private_object_input':True})
                for phase,target,seconds in schedule:
                    initial=physics.data.ctrl.copy();count=round(seconds/dt)
                    for j in range(count):
                        u=(j+1)/count;u=u*u*(3-2*u)
                        physics.set_control(initial+(target-initial)*u)
                        for _ in range(round(dt/physics.timestep())):physics.step()
                        save_state()
                        obs=env.wrapped.task.get_observation(physics)
                        if not np.isfinite(obs['state']).all():raise RuntimeError('Nonfinite scripted release')
                        step+=1
                        hand_contacts,target_contacts=contact_counts()
                        log.append({'step':step,'time_s':step*dt,'phase':phase,'object_x':float(obs['obj_pos'][0]),
                                    'object_y':float(obs['obj_pos'][1]),'object_z':float(obs['obj_pos'][2]),
                                    'goal_x':float(obs['final_goal'][0]),'goal_y':float(obs['final_goal'][1]),
                                    'goal_z':float(obs['final_goal'][2]),'reward':0.,
                                    'hand_object_contacts':hand_contacts,'target_object_contacts':target_contacts})
                        if writer:writer.append_data(env.render(height=480,width=640,camera_id=args.camera))
        finally:
            if writer:writer.close()
            np.savez_compressed(args.output/f'episode-{ep:02d}-states.npz',**{k:np.asarray(v) for k,v in saved.items()})
        error=torch.linalg.vector_norm(torch.as_tensor(obs['obj_pos']-obs['final_goal'],device='cuda')).item()
        tail=log[-max(1,round(.25/dt)):]
        release_evidence=(len(tail)*dt>=.249 and all(r['hand_object_contacts']==0 and r['target_object_contacts']>0 for r in tail))
        stable_tail=log[-max(1,round(.5/dt)):]
        positions=torch.tensor([[r['object_x'],r['object_y'],r['object_z']] for r in stable_tail],device='cuda')
        settling_drift=torch.linalg.vector_norm(positions-positions[-1],dim=1).max().item()
        support_release=bool(args.scripted_release and release_evidence and settling_drift<=.002)
        with (args.output/f'episode-{ep:02d}.csv').open('w') as stream:
            w=csv.DictWriter(stream,fieldnames=log[0].keys());w.writeheader();w.writerows(log)
        row={'episode':ep,'seed':seed,'steps':step,'sim_time_s':step*dt,'final_position_error_m':error,
             'upstream_success_at_3cm':error<.03 if task_kwargs['action']=='relocate' else None,
             'maximum_height_gain_m':max(r['object_z'] for r in log)-initial_z,
             'total_reward':total,'video':video.name if writer else None,'video_sha256':digest(video) if writer else None,
             'state_file':f'episode-{ep:02d}-states.npz','state_sha256':digest(args.output/f'episode-{ep:02d}-states.npz'),
             'model_file':model_file.name,'model_sha256':digest(model_file),'mujoco':mujoco.__version__,
             'release_verified':support_release,'release_scope':'No hand contact, cup contact, <=2mm drift over last0.5s; not full volume containment',
             'scripted_release':args.scripted_release,'policy_steps':policy_steps,
             'policy_endpoint_error_m':torch.linalg.vector_norm(torch.as_tensor(policy_endpoint-obs['final_goal'],device='cuda')).item(),
             'settling_drift_m':settling_drift,'action':task_kwargs['action'],
             'last_250ms_detached_and_target_contact':release_evidence,
             'note':'Only relocation uses the 3cm upstream endpoint metric; detachment/contact is a diagnostic, full containment and stable release remain separate'}
        rows.append(row);print(json.dumps(row),flush=True)
        write(args.output/'progress.json',{'episodes':rows})
    write(args.output/'result.json',{'execution_status':'passed','episodes':rows,
          'success_at_3cm':sum(r['upstream_success_at_3cm'] is True for r in rows) if task_kwargs['action']=='relocate' else None,'episode_count':len(rows),
          'mean_final_error_mm':sum(r['final_position_error_m'] for r in rows)/len(rows)*1000,
          'scope':identity['scope'],'release_verified':all(r['release_verified'] for r in rows),'policy_device':'cuda',
          'task_status':('passed' if all(r['upstream_success_at_3cm'] for r in rows) else 'failed') if task_kwargs['action']=='relocate' else 'awaiting_verification'})


if __name__=='__main__':main()
