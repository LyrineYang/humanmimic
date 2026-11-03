#!/usr/bin/env python3
"""Build an isolated, hash-pinned MuJoCo 3.2.7 touch-grid sign correction.

Upstream source retains its Apache-2.0 notices. Installed MuJoCo is untouched.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

PIN = {'touch_grid.cc': '0c8935a61272d3e5d268b7fb5df1e98db2e17a6400401701b15c78d9d2a06541',
       'touch_grid.h': 'c7a61f7a2f2959d35b5abd487e3f63e959d7b5641ea5ef2d991257a291efe547'}
BASE = 'https://raw.githubusercontent.com/google-deepmind/mujoco/3.2.7/plugin/sensor/'

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    import mujoco
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--source-directory', type=Path)
    args=p.parse_args()
    if mujoco.__version__ != '3.2.7': raise ValueError('Patch requires MuJoCo 3.2.7')
    args.output.mkdir(parents=True,exist_ok=False)
    for name, expected in PIN.items():
        raw=(args.source_directory/name).read_bytes() if args.source_directory else urllib.request.urlopen(BASE+name,timeout=30).read()
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Upstream source hash mismatch')
        text=raw.decode().replace('mujoco::plugin::sensor', 'humanmimic::plugin::sensor')
        if name.endswith('.cc'):
            old='if (parent_body < mjMAX(body1, body2))'
            if text.count(old)!=1:raise ValueError('Unexpected upstream sign branch')
            text=text.replace(old,'if (weld1 == parent_weld)')
            text=text.replace('// Forces point from the smaller to larger body, so flip sign if\n      // parent body has smaller id.',
                              '// Contact force acts on geom2; negate when measuring geom1.\n      // Geometry collision ordering need not follow body ID ordering.')
            text=text.replace('"mujoco.sensor.touch_grid"','"humanmimic.sensor.touch_grid"')
            text+='\nmjPLUGIN_LIB_INIT { humanmimic::plugin::sensor::TouchGrid::RegisterPlugin(); }\n'
        (args.output/name).write_text(text)
    package=Path(mujoco.__file__).parent
    library=(args.output/'libhumanmimic_touch_grid.so').resolve()
    command=['g++','-std=c++17','-O2','-shared','-fPIC','-fvisibility=hidden',str(args.output/'touch_grid.cc'),
             '-I'+str(package/'include'),str(package/'libmujoco.so.3.2.7'),'-Wl,-rpath,'+str(package),'-o',str(library)]
    subprocess.run(command,check=True)
    (args.output/'manifest.json').write_text(json.dumps({'schema_version':1,'mujoco_version':'3.2.7',
        'plugin':'humanmimic.sensor.touch_grid','upstream':BASE,'upstream_sha256':PIN,'license':'Apache-2.0',
        'correction':'Negate contact force iff measured welded body is contact geom1; never use body ID ordering',
        'source_sha256':{n:digest(args.output/n) for n in PIN},'library_sha256':digest(library),
        'build_command':command},indent=2)+'\n')
    print(library)

if __name__=='__main__':main()
