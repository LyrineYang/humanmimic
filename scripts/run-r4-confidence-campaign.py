#!/usr/bin/env python3
"""Freeze a development confidence fit before reading separate verification cases.

Run under the bounded prerequisite coordinator. Physical collection is separate;
this driver never grants E3 readiness or substitutes object compliance labels.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from r4_contract import sha256, write_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fit-cases',type=Path,required=True)
    p.add_argument('--verify-cases',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    fit=json.loads(args.fit_cases.read_text());verify=json.loads(args.verify_cases.read_text())
    if set(x['seed'] for x in fit['cases']) & set(x['seed'] for x in verify['cases']):
        raise ValueError('Independent fitting and verification required')
    if fit.get('window_s')!=verify.get('window_s'):raise ValueError('Freeze the same sampling window')
    args.output.mkdir(parents=True,exist_ok=False)
    manifest={'status':'running','fit_cases_sha256':sha256(args.fit_cases),
              'verify_cases_sha256':sha256(args.verify_cases),'source_sha256':sha256(__file__),
              'training':False,'heldout_used':False,'joint_E3_gate_passed':False}
    write_json(args.output/'manifest.json',manifest)
    deadline=time.monotonic()+900
    # Only inspect completion metadata here; no verification measurements.
    for case in fit['cases']+verify['cases']:
        path=Path(case['observations']).parent/'manifest.json'
        while not path.exists() or json.loads(path.read_text()).get('status')=='running':
            if time.monotonic()>deadline:raise TimeoutError('Physical prerequisite did not complete')
            time.sleep(1)
    entry=Path(__file__).parent/'calibrate-r4-confidence-gpu.py'
    def execute(phase,cases):
        command=[sys.executable,'-B',str(entry),'--cases',str(cases),'--phase',phase,'--output',str(args.output/phase)]
        if phase=='verify':command+=['--fit-report',str(args.output/'fit/result.json')]
        with (args.output/(phase+'.log')).open('x') as log:
            subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
        return json.loads((args.output/phase/'result.json').read_text())
    fitted=execute('fit',args.fit_cases)
    frozen=sha256(args.output/'fit/result.json')
    if fitted['pose_status']=='passed':
        verified=execute('verify',args.verify_cases)
        if sha256(args.output/'fit/result.json')!=frozen:raise RuntimeError('Fit report changed during verification')
        result={'status':verified['pose_status'],'coverage_fraction':verified['coverage_fraction'],
                'verification_used':True,'fit_report_sha256':frozen}
    else:
        result={'status':'failed','reason':'Fit lacked a valid interval; verification withheld, no tuning on it',
                'verification_used':False,'fit_report_sha256':frozen}
    result.update(scope='Conditional development translation intervals only',training=False,
                  heldout_used=False,joint_E3_gate_passed=False)
    write_json(args.output/'result.json',result)
    manifest['status']='complete';manifest['result_sha256']=sha256(args.output/'result.json')
    write_json(args.output/'manifest.json',manifest)


if __name__=='__main__':main()
