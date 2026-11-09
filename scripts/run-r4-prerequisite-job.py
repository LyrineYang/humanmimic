#!/usr/bin/env python3
"""Bounded prerequisite cohort on an explicitly authorized shared GPU.

The whole cohort occupies one GPU slot and charges its complete elapsed time.
Immutable command manifests, a private process group watchdog and the existing
campaign ledger survive loss of SSH; no foreign process is ever signalled.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from r4_campaign import ROOT, Ledger, digest, exclusive, inventory, read, write, stop_group


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--timeout', type=float, default=1800)
    p.add_argument('--gpu', required=True)
    p.add_argument('--parallel', type=int, default=2)
    p.add_argument('--budget-section', choices=['local_r4_campaign', 'local_demo_campaign'], default='local_r4_campaign')
    p.add_argument('--stage', default='prerequisites')
    p.add_argument('--requests',type=Path,help='Optional immutable request spool; STOP file drains and ends the session')
    args = p.parse_args()
    cfg = read(ROOT/'configs/budget.json')[args.budget_section]
    auth = cfg.get('shared_gpu_authorization', {})
    if args.gpu not in auth.get('gpu_uuids', []) or not 1 <= args.parallel <= auth['maximum_parallel_children']:
        raise ValueError('Shared GPU/cohort size not authorized')
    manifest = read(args.manifest)
    if not cfg.get('video_generation_authorized', True):
        if any(flag in argv for argv in manifest['commands'] for flag in ('--video','--record-video')):
            raise ValueError('Video generation is disabled by the current user instruction')
    for path, sha in manifest['source_sha256'].items():
        if digest(path) != sha: raise ValueError('Frozen source changed: '+path)
    root = Path(os.environ.get('R4_DATA_ROOT', str(ROOT.parent/'humanmimic-data/r4')))
    account = root/'runs'/cfg['campaign_id']
    lock = exclusive(account/'coordinator.lock')
    gpu_lock = exclusive(root/'runs'/(args.gpu+'.lock'))
    ledger = Ledger(account/'ledger.json', cfg)
    args.output.mkdir(parents=True, exist_ok=False)
    key = 'prerequisite-cohort:'+digest(args.manifest)
    device = inventory()[args.gpu]
    if device['free_mib'] < auth['minimum_free_headroom_mib']+4096:
        raise RuntimeError('Insufficient free memory for shared pilot; do not disturb foreign workload')
    ledger.reserve(key, args.stage, args.gpu, args.timeout+10, digest(args.manifest))
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=args.gpu, MUJOCO_GL='egl', MUJOCO_EGL_DEVICE_ID=str(device['index']),
               OMP_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4', MKL_NUM_THREADS='4', R4_CAMPAIGN_PROCESS_GROUP='1', PYTHONNOUSERSITE='1')
    active, outcomes = [], []
    pending = list(enumerate(manifest['commands']))
    submitted=len(pending);seen={}
    started = time.monotonic()
    telemetry = []
    def interrupted(signum, frame): raise KeyboardInterrupt('Stopping owned cohort only')
    signal.signal(signal.SIGTERM, interrupted)
    try:
        while pending or active or (args.requests and not (args.requests/'STOP').exists()):
            if time.monotonic()-started >= args.timeout:
                raise TimeoutError('Cohort budget exhausted')
            if args.requests:
                for path in sorted(args.requests.glob('request-*.json')):
                    sha=digest(path)
                    if path.name in seen:
                        if seen[path.name]!=sha: raise ValueError('Submitted request mutated')
                        continue
                    request=read(path)
                    for source,value in request['source_sha256'].items():
                        if digest(source)!=value:raise ValueError('Request source changed: '+source)
                    for argv in request['commands']:
                        pending.append((submitted,argv));submitted+=1
                    seen[path.name]=sha
                    write(args.output/'accepted-requests.json',seen)
            parallel=args.parallel
            if args.requests and (args.requests/'settings.json').exists():
                parallel=int(read(args.requests/'settings.json')['parallel'])
                if not 1<=parallel<=auth['maximum_parallel_children']:raise ValueError('Parallelism outside authorization')
            for item in list(active):
                index, process, log, launch = item
                if process.poll() is not None:
                    stop_group(process); log.close()
                    outcomes.append({'index':index, 'returncode':process.returncode, 'wall_s':time.monotonic()-launch})
                    active.remove(item)
            while pending and len(active) < parallel:
                index, argv = pending.pop(0)
                log = (args.output/('job-'+str(index)+'.log')).open('x')
                remaining = max(.1, args.timeout-(time.monotonic()-started))
                process = subprocess.Popen(['timeout','--signal=KILL',str(remaining)+'s',sys.executable,'-B',*argv],
                    env=env, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                active.append((index,process,log,time.monotonic()))
                write(args.output/'progress.json', {'status':'running','gpu':device,'foreign_pids_at_start':device['compute_pids'],
                    'children':[{'index':x[0],'pid':x[1].pid} for x in active], 'outcomes':outcomes})
            if not telemetry or time.monotonic()-telemetry[-1]['monotonic'] >= 5:
                current=inventory()[args.gpu]
                telemetry.append({'monotonic':time.monotonic(),'elapsed_s':time.monotonic()-started, **current})
                write(args.output/'telemetry.json', telemetry)
                write(args.output/'progress.json', {'status':'running','elapsed_s':time.monotonic()-started,
                    'children':[{'index':x[0],'pid':x[1].pid} for x in active], 'outcomes':outcomes,
                    'pending_count':len(pending),'submitted':submitted,'parallel':parallel})
                if current['free_mib'] < auth['minimum_free_headroom_mib']:
                    raise RuntimeError('Shared memory headroom crossed; terminate only owned cohort')
            time.sleep(.2)
    finally:
        for index, process, log, launch in active:
            stop_group(process); log.close()
            outcomes.append({'index':index,'returncode':process.returncode,'interrupted':True})
        status='passed' if len(outcomes)==submitted and all(x['returncode']==0 for x in outcomes) else 'failed'
        result={'status':status,'outcomes':outcomes,'wall_s':time.monotonic()-started,'gpu':device,
                'manifest_sha256':digest(args.manifest),'training':False,'heldout_used':False}
        write(args.output/'result.json',result)
        ledger.finish(key,result)
        gpu_lock.close();lock.close()
    if status != 'passed': raise SystemExit(1)


if __name__ == '__main__': main()
