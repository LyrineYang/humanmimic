#!/usr/bin/env python3
"""Standard-library source/shell/CLI contracts, separate from CUDA validation."""
import argparse
import ast
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    checks={}
    try:
        for path in (ROOT/'scripts').glob('*.py'):
            ast.parse(path.read_text(),filename=str(path))
        checks['python_source_parsing']=True
        for path in (ROOT/'scripts').glob('*.sh'):
            subprocess.run(['bash','-n',str(path)],check=True)
        checks['shell_source_parsing']=True
        suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_runtime_contracts.py')
        with (args.output/'contracts.log').open('w') as log:
            result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
        checks['runtime_contracts']=result.wasSuccessful()
        summary={'status':'passed' if all(checks.values()) else 'failed','checks':checks,'test_count':result.testsRun,
                 'failures':len(result.failures),'errors':len(result.errors),'python':sys.version,'prefix':sys.prefix,
                 'scope':'Standard-library shell/CLI/status contracts and source parsing; no numerical estimator, GPU or physics acceptance',
                 'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    except Exception as exc:
        summary={'status':'failed','checks':checks,'error':str(exc)}
    (args.output/'result.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    return int(summary['status']!='passed')


if __name__=='__main__': sys.exit(main())
