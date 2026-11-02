#!/usr/bin/env python3
"""No-private-asset CUDA example: generate -> isolate -> fit -> explain."""
import argparse
import datetime
import json
import os
from pathlib import Path
import sys
from r4_contract import write_json, sha256
from r4_cuda import require_cuda
from r4_gpu_fixtures import fixture
from r4_fixture_evaluation import evaluate
from r4_replay import launch
from execution_result import result_exit_code


def mesh_svg(prior, belief, output):
    # Illustration of returned object-local estimates, not a physical rollout.
    panels=[]
    for offset, title, vertices, color in [(0,'Coarse input',prior['vertices_object_m'],'#9ca3af'),(340,'Estimated surface',belief['vertices_object_m'],'#197f98')]:
        paths=[]
        for a,b,c in prior['faces']:
            xy=['{:.2f},{:.2f}'.format(offset+170+v[0]*3400,160-v[2]*3400) for v in [vertices[a],vertices[b],vertices[c]]]
            paths.append('<polygon points="{}" fill="none" stroke="{}" stroke-width="0.45"/>'.format(' '.join(xy),color))
        panels.append('<text x="{}" y="35" font-size="19">{}</text>'.format(offset+30,title)+''.join(paths))
    output.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="680" height="320" viewBox="0 0 680 320"><rect width="680" height="320" fill="white"/><g font-family="sans-serif" fill="#253446">'+''.join(panels)+'<text x="30" y="300" font-size="13">Synthetic CUDA reconstruction · object-local x/z projection · no robot execution</text></g></svg>')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--require-acceptance',action='store_true')
    args=parser.parse_args()
    # Admission before creating an output; no CPU fallback.
    device,gpu=require_cuda()
    args.output.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1]
    config_path=root/'configs/r4-p1p2.json'
    config=json.loads(config_path.read_text())
    manifest={'execution_status':'running','started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'pid':os.getpid(),'gpu':gpu,'python':sys.version,'prefix':sys.prefix,
              'config_sha256':sha256(config_path),'source_sha256':{p.name:sha256(p) for p in Path(__file__).parent.glob('*r4*.py')},
              'input_kind':'generated_analytic_fixture','private_assets':[],'heldout_used':False,'training':False,'paid_usd':0}
    write_json(args.output/'manifest.json',manifest)
    try:
        payload,truth=fixture(device,config['estimator'])
        public=args.output/'public-observations'; public.mkdir()
        private=args.output/'private-evaluation'; private.mkdir(mode=0o700)
        write_json(public/'calibration.json',payload['calibration'])
        write_json(public/'prior.json',payload['prior'])
        (public/'observations.jsonl').write_text(''.join(json.dumps(frame,allow_nan=False)+'\n' for frame in payload['frames']))
        write_json(private/'truth.json',truth)
        estimates=launch(payload,args.output/'estimation',config['estimator']['maximum_wall_s']+120)
        metrics=evaluate(estimates,truth,device)
        write_json(private/'metrics.json',metrics)
        bounds=config['acceptance']
        passed=(metrics.get('state_updated',False) and metrics['position_rmse_m']<=bounds['pose_translation_tolerance_m']
                and metrics['shape_surface_rmse_m']<=bounds['shape_rmse_tolerance_m']
                and metrics['compliance_error_m_per_n']<=bounds['compliance_tolerance_m_per_n']
                and metrics['compliance_observable'] and estimates['read_guard_probe_denied'])
        result={'schema_version':2,'execution_status':'completed','task_status':'passed' if passed else 'failed',
                'task_scope':'Analytic joint-estimation engineering checks against fixed thresholds',
                'acceptance_status':'awaiting_verification','review_status':'awaiting_verification',
                'acceptance_scope':'R4 manipulation gains and uncertainty calibration are not established by this example',
                'metrics':metrics,'thresholds':bounds,'gpu':gpu,'private_assets_required':False,'heldout_used':False,
                'artifacts':{'report':'REPORT.md','illustration':'comparison.svg','observations':'public-observations/observations.jsonl',
                             'prior':'public-observations/prior.json','belief':'estimation/belief.json','private_metrics':'private-evaluation/metrics.json'}}
        write_json(args.output/'result.json',result)
        mesh_svg(payload['prior'],estimates['beliefs'][-1],args.output/'comparison.svg')
        (args.output/'REPORT.md').write_text('# HumanMimic CUDA example\n\n'
            'Execution: **completed**. Analytic task check: **'+result['task_status']+'**. Research acceptance: **awaiting_verification**.\n\n'
            'Eight generated visual/contact frames feed the same isolated CUDA estimator used by the research pipeline. '
            'No MANO, video, robot assets or learned weights are required. The private analytic truth is withheld from the worker.\n\n'
            '![Coarse and estimated surfaces](comparison.svg)\n\n'
            '| Quantity | Measured | Meaning |\n| --- | ---: | --- |\n'
            '| Translation RMSE | {:.4f} mm | Error against generated motion |\n'
            '| Shape RMSE | {:.4f} mm | Independent ellipsoid distance approximation |\n'
            '| Compliance error | {:.4f} mm/N | Effective linear fixture compliance |\n\n'.format(metrics['position_rmse_m']*1000,metrics['shape_surface_rmse_m']*1000,metrics['compliance_error_m_per_n']*1000)+
            'These are synthetic estimator metrics. There is no physical manipulation or camera test. '
            'A successful command does not certify calibrated uncertainty or useful grasping; the current pose interval covers the fixture error: **'+str(metrics['pose_covered'])+'**.\n\n'
            'Read [result.json](result.json), [immutable observations](public-observations/observations.jsonl), '
            '[estimated states and uncertainty](estimation/belief.json), and [independent metrics](private-evaluation/metrics.json). '
            'Default exit 0 means execution completed; inspect task_status. --require-acceptance returns 3 while research acceptance remains unverified.\n')
        manifest.update(execution_status='completed',result_sha256=sha256(args.output/'result.json'))
        print(json.dumps(result,indent=2))
        return result_exit_code(result,args.require_acceptance)
    except BaseException as exc:
        manifest.update(execution_status='failed',error=str(exc))
        write_json(args.output/'result.json',{'schema_version':2,'execution_status':'failed','task_status':'awaiting_verification','acceptance_status':'awaiting_verification','error':str(exc)})
        raise
    finally:
        write_json(args.output/'manifest.json',manifest)


if __name__=='__main__':
    sys.exit(main())
