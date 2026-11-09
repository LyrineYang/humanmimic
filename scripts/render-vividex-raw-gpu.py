#!/usr/bin/env python3
"""Uncut, real-time replay of saved physical trajectories; never a showcase.

Every state comes from the actual experiment archive. No trajectory synthesis,
interpolation, re-simulation, success filtering, or multi-run composition.
Shared experimental prefixes are included in each independent raw rollout.
"""
import argparse
import csv
import json
import os
from pathlib import Path
import time

from r4_campaign import digest, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--trial', help='Optional exact trial ID for development rendering checks')
    parser.add_argument('--fps', type=int, default=40)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if not json.loads((root/'configs/budget.json').read_text())['local_demo_campaign'].get('video_generation_authorized', False):
        parser.error('Raw experiment video is not authorized')
    os.environ['MUJOCO_GL'] = 'egl'
    import imageio.v2 as imageio
    import mujoco
    import numpy as np
    import torch
    from PIL import Image, ImageDraw, ImageFont
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA/EGL target required; no CPU rendering fallback')
    result = json.loads((args.run/'result.json').read_text())
    trials = result['trials']
    if args.trial:
        trials = [t for t in trials if t['condition']['id'] == args.trial]
        if not trials: raise ValueError('Unknown trial')
    args.output.mkdir(parents=True, exist_ok=False)
    font = ImageFont.load_default()
    outputs = []
    for trial in trials:
        folder = args.run/trial['condition']['id']
        out = args.output/trial['condition']['id']; out.mkdir()
        model = mujoco.MjModel.from_binary_path(str(folder/'model.mjb'))
        data = mujoco.MjData(model)
        renderer = mujoco.Renderer(model, height=480, width=640)
        for arm, metrics in trial['variants'].items():
            timing = arm.split('-')[0]
            segments = ['common', timing+'-common', arm]
            loaded = [np.load(folder/(s+'-states.npz')) for s in segments]
            phase_lists = []
            for s in segments:
                with (folder/(s+'-public.csv')).open() as stream:
                    phase_lists.append([row['phase'] for row in csv.DictReader(stream)])
            times, index_map = [], []
            for segment_i, state in enumerate(loaded):
                for row, timestamp in enumerate(state['time']):
                    if times and float(timestamp) <= times[-1]: continue
                    times.append(float(timestamp)); index_map.append((segment_i, row))
            time_tensor = torch.tensor(times, device='cuda', dtype=torch.float64)
            assert torch.isfinite(time_tensor).all() and (torch.diff(time_tensor)>0).all()
            frame_times = torch.arange(int((times[-1]-times[0])*args.fps)+1, device='cuda', dtype=torch.float64)/args.fps+times[0]
            indices = (torch.searchsorted(time_tensor, frame_times+1e-9, right=True)-1).clamp_min(0).cpu().tolist()
            samples = frame_times.cpu().tolist()
            # Include terminal state; maximum padding is one frame period.
            if indices[-1] != len(times)-1:
                indices.append(len(times)-1); samples.append(times[0]+len(samples)/args.fps)
            video = out/(arm+'.mp4')
            start = time.monotonic()
            writer = imageio.get_writer(video, fps=args.fps, codec='libx264', quality=7, macro_block_size=1,
                                        ffmpeg_params=['-threads', '2'])
            mapping = []
            try:
                for frame_i, index in enumerate(indices):
                    segment_i, row = index_map[index]; state = loaded[segment_i]
                    for key in state.files:
                        if key == 'time': data.time = float(state[key][row])
                        else: getattr(data, key)[:] = state[key][row]
                    mujoco.mj_forward(model, data)
                    renderer.update_scene(data, camera='front')
                    frame = Image.fromarray(renderer.render())
                    draw = ImageDraw.Draw(frame)
                    phase = phase_lists[segment_i][row]
                    draw.rectangle([0, 0, 640, 32], fill=(15, 15, 15))
                    draw.text((5, 2), f"RAW PHYSICS REPLAY | {trial['condition']['id']} | {arm}", font=font, fill='white')
                    draw.text((5, 17), f"t={data.time:.3f}s | {phase} | trial valid={metrics['valid']}", font=font, fill='white')
                    writer.append_data(np.asarray(frame))
                    mapping.append({'frame': frame_i, 'video_time_s': frame_i/args.fps,
                                    'sample_time_s': samples[frame_i], 'state_time_s': float(data.time),
                                    'segment': segments[segment_i], 'row': row, 'phase': phase})
            finally:
                writer.close()
            with (out/(arm+'-frames.csv')).open('w') as stream:
                w = csv.DictWriter(stream, fieldnames=mapping[0].keys()); w.writeheader(); w.writerows(mapping)
            entry = {'trial': trial['condition']['id'], 'arm': arm, 'valid': metrics['valid'],
                     'video': str(video.relative_to(args.output)), 'sha256': digest(video),
                     'frames': len(mapping), 'fps': args.fps, 'duration_s': len(mapping)/args.fps,
                     'source_duration_s': times[-1]-times[0], 'render_wall_s': time.monotonic()-start,
                     'state_sources_sha256': {s: digest(folder/(s+'-states.npz')) for s in segments},
                     'model_sha256': digest(folder/'model.mjb'), 'synthetic_motion': False,
                     'full_original_timeline': True, 'speed': 1., 'scope': 'Saved actual simulation states, native camera, diagnostic text only; not live camera or showcase'}
            write(out/(arm+'.json'), entry)
            outputs.append(entry); print(json.dumps(entry), flush=True)
            write(args.output/'progress.json', {'videos': outputs})
        del renderer
    write(args.output/'result.json', {'status': 'passed', 'videos': outputs, 'video_count': len(outputs),
                                      'success_and_failure_preserved': True, 'new_experiment_samples': 0,
                                      'training': False, 'showcase': False, 'mujoco': mujoco.__version__,
                                      'gpu': torch.cuda.get_device_name()})


if __name__ == '__main__':
    main()
