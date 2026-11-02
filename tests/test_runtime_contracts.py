"""Shell/input/status contracts only. No estimator or CPU numerical tests."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from execution_result import r2_result, result_exit_code
from runtime_target import load_target, execution_guard, diagnose


class RuntimeContracts(unittest.TestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_directory.cleanup)
        self.media_path = Path(self.media_directory.name)/'contract-media.bin'
        self.media_path.write_bytes(b'contract fixture, not an actual video')

    def recorded_media(self):
        return [{'path':str(self.media_path), 'sha256':hashlib.sha256(self.media_path.read_bytes()).hexdigest(),
                 'status':'passed', 'full_decode':True}]

    def shell(self, script, env=None):
        result=subprocess.run(['bash','--noprofile','--norc','-c',script],cwd=ROOT,env=env or dict(os.environ),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)

    def probe(self, prefix='source scripts/activate-r4.sh || exit;'):
        return prefix+''' python -c 'import importlib.util,json,os,site,sys; print(json.dumps({"executable":sys.executable,"user_site":site.ENABLE_USER_SITE,"sentinel":importlib.util.find_spec("hm_external_sentinel") is not None,"path":sys.path,"ld":os.environ.get("LD_LIBRARY_PATH"),"conda":os.environ.get("CONDA_PREFIX"),"env":os.environ.get("CONDA_DEFAULT_ENV"),"shell_path":os.environ["PATH"]}))' '''

    def test_clean_activation(self):
        info=self.shell(self.probe())
        self.assertFalse(info['user_site'])
        self.assertEqual(str(Path(info['executable']).parent.parent),info['conda'])
        self.assertFalse(info['sentinel'])

    def test_polluted_then_repeated_activation(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            (directory/'hm_external_sentinel.py').write_text('marker=True\n')
            user=directory/'lib/python3.10/site-packages'; user.mkdir(parents=True)
            (user/'hm_external_sentinel.py').write_text('marker=True\n')
            env=dict(os.environ,PYTHONPATH=temporary,PYTHONUSERBASE=temporary,LD_LIBRARY_PATH=temporary,CONDA_PREFIX='/old/environment',CONDA_DEFAULT_ENV='old',CONDA_SHLVL='9',VIRTUAL_ENV='/old/venv')
            info=self.shell(self.probe('source scripts/activate-r4.sh || exit; source scripts/activate-r4.sh || exit;'),env)
            self.assertFalse(info['sentinel'])
            self.assertFalse(info['user_site'])
            self.assertNotIn(temporary,info['ld'])
            self.assertNotIn(temporary,info['path'])
            self.assertNotEqual(info['env'],'old')
            self.assertEqual(info['shell_path'].split(':').count(info['conda']+'/bin'),1)

    def test_switch_from_actual_conda_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            other=Path(temporary)/'other-conda-environment'
            env=dict(os.environ,CONDA_REGISTER_ENVS='false',R4_TEST_OTHER_PREFIX=str(other))
            created=subprocess.run([str(Path(env['R4_ENV_PREFIX'])/'bin/conda'),'create','--offline','--no-default-packages','--yes','--prefix',str(other)],
                                   env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            self.assertEqual(created.returncode,0,created.stderr)
            script='source "$R4_ENV_PREFIX/etc/profile.d/conda.sh"; conda activate "$R4_TEST_OTHER_PREFIX" || exit; '
            script+='[[ "$CONDA_PREFIX" == "$R4_TEST_OTHER_PREFIX" ]] || exit 1; '
            script+='export PYTHONPATH=/old/environment LD_LIBRARY_PATH=/old/environment; '
            info=self.shell(self.probe(script+'source scripts/activate-r4.sh || exit;'),env)
            self.assertNotEqual(info['conda'],str(other))
            self.assertNotIn('/old/environment',info['ld'])
            self.assertNotIn('/old/environment',info['path'])

    def test_failed_activation_is_transactional(self):
        env=dict(os.environ,R4_ENV_PREFIX='/does-not-exist-humanmimic',PYTHONPATH='/keep/me',LD_LIBRARY_PATH='/keep/library')
        info=self.shell('before="$PATH"; source scripts/activate-r4.sh; code=$?; [[ "$code" != 0 && "$before" == "$PATH" && "$PYTHONPATH" == /keep/me && "$LD_LIBRARY_PATH" == /keep/library ]] || exit 1; printf \'{"unchanged":true}\\n\'',env)
        self.assertTrue(info['unchanged'])

    def test_original_guard_and_new_target_authorization(self):
        # This test runs on the migration server, never spoofs the boot identity.
        original=load_target('legacy-wsl')
        with self.assertRaisesRegex(RuntimeError,'paused after reboot'):
            execution_guard(original,'r2')
        server=load_target('r4-v100')
        with self.assertRaisesRegex(RuntimeError,'no r2 execution authorization'):
            execution_guard(server,'r2')
        execution_guard(server,'r4_example')

    def test_r2_real_readonly_cli(self):
        with tempfile.TemporaryDirectory() as temporary:
            source=Path(temporary)/'inspection-only.mp4'; source.write_bytes(b'input inspection does not decode a video')
            result=subprocess.run([sys.executable,str(ROOT/'scripts/run-r2-video.py'),'--input',str(source),'--run-id','readonly-contract','--target','r4-v100','--check-only'],
                                  env=dict(os.environ,R2_STORAGE_ROOT='/old-author-machine-data'),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            info=json.loads(result.stdout)
            self.assertEqual(info['execution_status'],'completed')
            self.assertEqual(info['authorization']['status'],'needs_input')
            self.assertTrue(info['missing_runtime_paths'])
            self.assertFalse(any('/mnt/c' in d['path'] for d in info['disk_reserves']))
            self.assertNotIn('/old-author-machine-data',info['output'])
            self.assertFalse(Path(info['output']).exists())

    def test_exploration_and_strict_statuses(self):
        audit={'extraction':{'status':'passed'},'media_status':'passed','physical_status':'passed','body_status':'awaiting_verification','visual_status':'awaiting_verification'}
        audit['videos'] = self.recorded_media()
        result=r2_result({'status':'awaiting_verification'},audit)
        self.assertEqual(result['execution_status'],'completed')
        self.assertEqual(result_exit_code(result),0)
        self.assertEqual(result_exit_code(result,True),3)
        bad=copy.deepcopy(audit); bad['physical_status']='failed'
        result=r2_result({'status':'failed'},bad)
        self.assertEqual(result['task_status'],'failed')
        self.assertEqual(result_exit_code(result,True),1)
        incomplete=copy.deepcopy(audit); incomplete.pop('media_status')
        self.assertEqual(result_exit_code(r2_result({'status':'awaiting_verification'},incomplete)),1)
        broken=copy.deepcopy(audit); broken['audit_error']='hash mismatch'
        self.assertEqual(result_exit_code(r2_result({'status':'failed'},broken)),1)

    def test_cached_audit_does_not_hide_missing_or_changed_media(self):
        audit={'extraction':{'status':'passed'}, 'media_status':'passed', 'videos':self.recorded_media()}
        self.assertEqual(r2_result({'status':'passed'},audit)['execution_status'],'completed')
        self.media_path.write_bytes(b'changed after audit')
        self.assertNotEqual(r2_result({'status':'passed'},audit)['execution_status'],'completed')
        self.media_path.unlink()
        self.assertNotEqual(r2_result({'status':'passed'},audit)['execution_status'],'completed')


if __name__=='__main__': unittest.main()
