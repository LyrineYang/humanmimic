#!/usr/bin/env python3
"""Stable developer entry: diagnose, rebuild, run an example, inspect its result."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from runtime_target import PROJECT, load_target, diagnose, execution_guard


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command')
    doctor = sub.add_parser('doctor', help='Read-only target diagnosis; no scientific packages needed')
    doctor.add_argument('--target',default='r4-v100')
    doctor.add_argument('--stage',choices=['r2','r4_example','r4_research'],default='r4_example')
    bootstrap = sub.add_parser('bootstrap',help='Rebuild an empty Linux prefix from pinned archives', add_help=False)
    bootstrap.add_argument('arguments',nargs=argparse.REMAINDER)
    example = sub.add_parser('example',help='Generate an analytic observation bundle and fit it on one GPU')
    example.add_argument('--target',default='r4-v100')
    example.add_argument('--prefix',type=Path)
    example.add_argument('--gpu',required=True,help='One GPU UUID selected after checking occupancy')
    example.add_argument('--output',type=Path,required=True)
    example.add_argument('--require-acceptance',action='store_true')
    inspect = sub.add_parser('inspect',help='Read preserved result without GPU packages')
    inspect.add_argument('result',type=Path)
    inspect.add_argument('--require-acceptance',action='store_true',help='Return nonzero unless the saved result proves acceptance')
    # Bootstrap owns its detailed parser, including --help.
    if len(sys.argv)>1 and sys.argv[1]=='bootstrap':
        from bootstrap_r4 import main as bootstrap_main
        return bootstrap_main(sys.argv[2:])
    args=p.parse_args()
    if args.command=='doctor':
        print(json.dumps(diagnose(load_target(args.target),args.stage),indent=2)); return 0
    if args.command=='inspect':
        path=args.result/'result.json' if args.result.is_dir() else args.result
        result=json.loads(path.read_text())
        print(json.dumps(result,indent=2))
        if args.require_acceptance:
            from execution_result import result_exit_code
            return result_exit_code(result,True)
        return 0
    if args.command=='example':
        target=load_target(args.target)
        execution_guard(target,'r4_example')
        if not args.gpu.startswith('GPU-') or ',' in args.gpu: p.error('Select one explicit GPU UUID')
        env=dict(os.environ)
        env.update(R4_ENV_PREFIX=str(args.prefix.resolve()) if args.prefix else target['r4_prefix'],
                   R4_DATA_ROOT=target['data_root'],CUDA_VISIBLE_DEVICES=args.gpu,WANDB_MODE='offline')
        command=['bash','--noprofile','--norc','-c','source "$1" || exit; shift; exec python "$@"','humanmimic',
                 str(PROJECT/'scripts/activate-r4-research.sh'),str(PROJECT/'scripts/run-r4-example.py'),'--output',str(args.output.resolve())]
        if args.require_acceptance: command.append('--require-acceptance')
        return subprocess.call(command,env=env,cwd=str(PROJECT))
    p.print_help(); return 2


if __name__=='__main__':
    try:
        sys.exit(main())
    except (ValueError,RuntimeError,OSError) as exc:
        print(json.dumps({'execution_status':'failed','error':str(exc)}),file=sys.stderr)
        sys.exit(1)
