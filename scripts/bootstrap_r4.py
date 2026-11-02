"""Build the supported Linux target from distributable archives, never an env copy."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(4*1024**2), b''): h.update(block)
    return h.hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2)+'\n')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prefix', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--cache', type=Path, required=True)
    p.add_argument('--installer', type=Path, help='Optional already-downloaded, hash-verified Miniforge archive')
    p.add_argument('--wheelhouse', type=Path, help='Optional directory of original wheels; never installed site-packages')
    p.add_argument('--proxy', help='Optional proxy for this install only; not persisted')
    args = p.parse_args(argv)
    prefix, output = args.prefix.expanduser().resolve(), args.output.resolve()
    config_path = ROOT/'configs/r4-bootstrap.json'
    config = json.loads(config_path.read_text())
    lock = ROOT/config['pip_lock']
    identity = {'bootstrap_sha256':sha(config_path), 'pip_lock_sha256':sha(lock)}
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        p.error('This pinned target supports Linux x86_64 only')
    probe = prefix.parent
    while not probe.exists(): probe = probe.parent
    if shutil.disk_usage(str(probe)).free < 20*1024**3: p.error('Need 20 GiB free on destination filesystem')
    # Remove caller package/library contamination for both installer and pip.
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(('PYTHON','CONDA_','_CONDA_','PIP_')) or key in ['LD_LIBRARY_PATH','LD_PRELOAD','VIRTUAL_ENV']:
            env.pop(key, None)
    env.update(PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1', PIP_CONFIG_FILE='/dev/null',
               PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
               CONDA_REGISTER_ENVS='false', PIP_DISABLE_PIP_VERSION_CHECK='1')
    cache = args.cache.expanduser().resolve()
    (cache/'pip').mkdir(parents=True, exist_ok=True)
    (cache/'tmp').mkdir(exist_ok=True)
    env.update(PIP_CACHE_DIR=str(cache/'pip'), TMPDIR=str(cache/'tmp'))
    marker = prefix/'humanmimic-install.json'
    output.mkdir(parents=True, exist_ok=True)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    with (prefix.parent/('.'+prefix.name+'.humanmimic-install.lock')).open('a') as prefix_guard, (output/'install.lock').open('a') as guard:
        fcntl.flock(prefix_guard, fcntl.LOCK_EX|fcntl.LOCK_NB)
        fcntl.flock(guard, fcntl.LOCK_EX|fcntl.LOCK_NB)
        def run(command, name):
            with (output/(name+'.log')).open('x') as log:
                subprocess.run([str(x) for x in command], env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        if prefix.exists():
            if not marker.exists(): p.error('Prefix already exists without a completed matching installation; preserve it and select a new prefix')
            previous = json.loads(marker.read_text())
            if previous.get('identity') != identity: p.error('Existing installation uses different locks; select a new prefix')
            # Repeated calls never reinstall/upgrade. Verify the actual package inventory.
            actual = subprocess.check_output([str(prefix/'bin/python'),'-I','-m','pip','freeze','--all'],env=env)
            if hashlib.sha256(actual).hexdigest() != previous['freeze_sha256']:
                p.error('Existing package inventory drifted from completed install')
            subprocess.run([str(prefix/'bin/python'),'-I','-m','pip','check'],env=env,check=True)
            print(json.dumps({'execution_status':'completed','installation_status':'passed','reused_verified_installation':True,'prefix':str(prefix)}))
            return 0
        manifest = dict(identity=identity, status='running', pid=os.getpid(), prefix=str(prefix),
                        started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        input_prefix_existed=False, environment_copied=False,
                        source_sha256=sha(__file__), heldout_used=False, paid_usd=0)
        save(output/'manifest.json',manifest)
        try:
            installer = args.installer.resolve() if args.installer else cache/'Miniforge3-24.3.0-0-Linux-x86_64.sh'
            if not installer.exists():
                command = ['curl','--fail','--location','--retry','2','--output',str(installer)+'.part']
                if args.proxy: command += ['--proxy',args.proxy]
                command += [config['installer']['url']]
                run(command,'download-installer')
                Path(str(installer)+'.part').rename(installer)
            if sha(installer) != config['installer']['sha256']: raise ValueError('Installer checksum mismatch')
            manifest['installer_sha256'] = sha(installer)
            if args.wheelhouse:
                for item in config['wheels']:
                    path = args.wheelhouse/item['file']
                    if not path.is_file() or sha(path) != item['sha256']: raise ValueError('Missing/mismatched wheel: '+item['file'])
            prefix.parent.mkdir(parents=True,exist_ok=True)
            run(['bash',installer,'-b','-p',prefix],'install-conda')
            py = prefix/'bin/python'
            command = [py,'-I','-m','pip','install','--no-deps','--only-binary=:all:','--require-hashes','-r',lock,'--report',output/'pip-install-report.json']
            if args.wheelhouse: command += ['--no-index','--find-links',args.wheelhouse.resolve()]
            else:
                command += ['--index-url','https://pypi.org/simple','--extra-index-url','https://download.pytorch.org/whl/cu118']
                if args.proxy: command += ['--proxy',args.proxy]
            run(command,'install-wheels')
            run([py,'-I','-m','pip','check'],'pip-check')
            freeze = subprocess.check_output([str(py),'-I','-m','pip','freeze','--all'],env=env)
            (output/'installed-packages.txt').write_bytes(freeze)
            manifest.update(status='passed', freeze_sha256=hashlib.sha256(freeze).hexdigest(),
                            completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            gpu_verification='awaiting_verification', source='pinned installer plus original hashed wheels')
            save(marker,manifest)
            print(json.dumps({'execution_status':'completed','installation_status':'passed','prefix':str(prefix),'gpu_verification':'awaiting_verification'}))
        except BaseException as exc:
            manifest.update(status='failed',error=str(exc))
            raise
        finally:
            save(output/'manifest.json',manifest)
    return 0


if __name__ == '__main__':
    sys.exit(main())
