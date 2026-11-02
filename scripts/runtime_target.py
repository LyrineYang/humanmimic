"""Portable, standard-library-only target diagnostics; never import a model."""
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

PROJECT = Path(__file__).resolve().parents[1]


def load_target(selection=None):
    selected = selection or os.environ.get('HUMANMIMIC_TARGET', 'legacy-wsl')
    path = Path(selected)
    if path.suffix != '.json':
        if '/' in selected or '\\' in selected:
            raise ValueError('Use a target name or explicit JSON profile')
        path = PROJECT / 'configs/targets' / (selected + '.json')
    config = json.loads(path.read_text())
    if config.get('schema_version') != 1 or config.get('kind') not in {'linux', 'legacy_wsl'}:
        raise ValueError('Unsupported target schema/kind')
    context = {'project': str(PROJECT)}
    context['data_root'] = str(Path(config['data_root'].format(**context)).expanduser().resolve())
    # Legacy callers retain their documented storage override. A newly selected
    # target must not inherit the previous machine/environment's paths.
    context['r2_storage'] = (os.environ.get('R2_STORAGE_ROOT') if config['kind'] == 'legacy_wsl' else None) or config['r2_storage'].format(**context)
    for key in ['r1_prefix', 'r2_prefix', 'r4_prefix']:
        config[key] = str(Path(config[key].format(**context)).expanduser().resolve())
    config.update(data_root=context['data_root'], r2_storage=str(Path(context['r2_storage']).resolve()), profile_path=str(path.resolve()))
    config['disk_reserves'] = [{'path': str(Path(item['path'].format(**context)).resolve()), 'minimum_free_gib': item['minimum_free_gib']} for item in config['disk_reserves']]
    return config


def execution_guard(config, stage):
    # The original WSL pause must survive selecting a different profile there.
    is_wsl = 'microsoft' in platform.release().lower()
    if stage in {'r1', 'r2'} and (config['kind'] == 'legacy_wsl' or is_wsl):
        policy = json.loads((PROJECT / 'configs/r2-execution-policy.json').read_text())
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        if boot != policy['local_boot_id_authorized']:
            raise RuntimeError('Original WSL execution paused after reboot; server handoff required')
    if stage not in config['execution_authorized']:
        raise RuntimeError('Target {} has no {} execution authorization; diagnostics remain available'.format(config['id'], stage))


def disk_report(config):
    report = []
    for item in config['disk_reserves']:
        path = Path(item['path'])
        probe = path
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        free = shutil.disk_usage(str(probe)).free / 1024**3
        report.append(dict(item, existing_ancestor=str(probe), path_exists=path.exists(), free_gib=free,
                           status='passed' if free >= item['minimum_free_gib'] else 'failed'))
    return report


def diagnose(config, stage='r4_example'):
    issues = []
    try:
        execution_guard(config, stage)
        authorization = {'status': 'passed'}
    except (OSError, ValueError, RuntimeError) as exc:
        authorization = {'status': 'needs_input', 'reason': str(exc)}
        issues.append(str(exc))
    environment = 'r2' if stage == 'r2' else 'r4'
    required = [config[environment+'_prefix'] + '/bin/python']
    if stage == 'r2':
        required += [config['r1_prefix']+'/bin/python', str(PROJECT/'vendor/GR00T-WholeBodyControl/gear_sonic_deploy/target/release/g1_deploy_onnx_ref')]
    missing = [p for p in required if not Path(p).is_file()]
    issues += ['Missing runtime: '+p for p in missing]
    if stage == 'r2':
        issues.append('R2 perception/body/policy assets and full target execution require separate validation')
    disks = disk_report(config)
    issues += ['Insufficient disk reserve: '+i['path'] for i in disks if i['status'] != 'passed']
    compatible = platform.system() == 'Linux' and platform.machine() == 'x86_64'
    if not compatible: issues.append('Supported target requires Linux x86_64')
    dependencies = {'status': 'needs_input', 'versions': {}}
    if stage != 'r2' and not missing:
        expected = json.loads((PROJECT/'configs/r4-runtime.json').read_text())
        probe = 'import importlib.metadata as m,json,sys; print(json.dumps(dict(python=".".join(map(str,sys.version_info[:3])), **{n:m.version(n) for n in ["torch","mujoco"]})))'
        try:
            versions = json.loads(subprocess.check_output([required[0], '-I', '-c', probe], stderr=subprocess.PIPE, timeout=20, universal_newlines=True))
            dependencies = {'status': 'passed' if all(versions[n] == expected[n] for n in versions) else 'failed', 'versions': versions}
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            dependencies = {'status': 'failed', 'reason': str(exc), 'versions': {}}
        if dependencies['status'] != 'passed': issues.append('Missing or incompatible target dependencies')
    if stage == 'r4_research' and not (Path(config['data_root'])/'assets/leap_hand/provenance.json').is_file():
        issues.append('LEAP research assets are not prepared; analytic example does not require them')
    return {'execution_status': 'completed', 'diagnostic_status': 'passed', 'target': config['id'], 'profile': config['profile_path'],
            'stage': stage, 'authorization': authorization, 'ready_to_attempt': not issues, 'dependencies': dependencies,
            'readiness_status': 'awaiting_verification', 'missing_runtime_paths': missing,
            'disk_reserves': disks, 'issues': issues, 'gpu_validation': 'not_run', 'scope': 'Read-only standard-library diagnosis; no model or physics execution'}
