"""Fresh, frozen full-score integration panel; historical experiments untouched."""

import argparse
import json
from pathlib import Path

from . import scoring_s26 as base
from .config import load_json
from .criterion_anchors import attach_anchors, validate_anchor_set
from .local_settings import read_setting
from .provenance import sha256_json, sha256_text
from .providers.http_json import ProviderRequestError

POLICY = 'config/scoring_s28_v1.json'
MANIFEST = 'config/scoring_s28_frozen_v1.json'
SOURCES = sorted(set(base.SOURCES + [POLICY, 'benchmark/scoring_s28.py',
    'config/multiturn_criterion_anchors_batch_g_s27_v1.json']))


def inputs(root):
    old_policy, old_packets, controls = base.inputs(root)
    policy = load_json(root/POLICY)
    # This experiment changes one anchor, not arithmetic, thresholds or controls.
    for key in old_policy:
        if key != 'version' and policy[key] != old_policy[key]:
            raise ValueError('S28 must preserve the S26 policy apart from version')
    anchors = load_json(root/policy['anchor_path'])
    validate_anchor_set(anchors, load_json(root/'data/multiturn/batch_g_cases.json'))
    return policy, {key: attach_anchors(packet, anchors) for key, packet in old_packets.items()}, controls


def manifest(root):
    _, packets, _ = inputs(root)
    return {'version': 's28-frozen-v1',
            'files': {p: sha256_text((root/p).read_text(encoding='utf-8')) for p in SOURCES},
            'packets': {k: sha256_json(v) for k,v in sorted(packets.items())}}


def check_manifest(root):
    result = manifest(root)
    if result != load_json(root/MANIFEST):
        raise ValueError('S28 frozen files or packets changed; create a new experiment')
    return result


def schedule(policy, packets):
    return ([('first', k, s) for k in sorted(packets) for s in policy['judges']]
            + [('repeat', k, s) for k in sorted(packets) if k.endswith('__partial') for s in policy['judges']])


def attempt(phase, key, spec, packet):
    return {'phase': phase, 'packet_key': key, 'provider': spec['provider'],
            'model_requested': spec['model'], 'packet_sha256': sha256_json(packet)}


def run(root, output, env_file, max_calls):
    frozen = check_manifest(root)
    policy, packets, _ = inputs(root)
    if max_calls != 32 or output.exists() or not output.resolve().is_relative_to((root/'work').resolve()):
        raise ValueError('S28 requires fresh ignored output and exactly 32 max calls')
    keys = {p: read_setting(env_file, name, secret=True)
            for p,name in [('gemini','GEMINI_API_KEY'),('grok','GROK_API_KEY')]}
    output.mkdir(parents=True, mode=0o700)
    base.write_new(output/'manifest.json', frozen)
    instruction = (root/base.PROMPT).read_text(encoding='utf-8')
    models = {}
    for i,(phase,key,spec) in enumerate(schedule(policy,packets),1):
        record = attempt(phase,key,spec,packets[key])
        base.write_new(output/f'{i:02d}.attempt.json',record)
        try:
            raw, latency = base.request_judgment(spec['provider'],spec['model'],keys[spec['provider']],
                packets[key],instruction,policy['timeout_seconds'])
            base.write_new(output/f'{i:02d}.response.json',raw)
            judgment = base.parse_response(raw,spec['provider'])
            result = base.score(judgment,packets[key],policy)
            if spec['provider'] in models and models[spec['provider']] != raw['model']:
                raise ValueError('S28 returned model drift')
            models[spec['provider']] = raw['model']
            base.write_new(output/f'{i:02d}.judgment.json',dict(record,model_returned=raw['model'],
                judgment=judgment,score=result,latency_ms=latency))
            print(json.dumps({'completed':i,'maximum':32,'phase':phase,'provider':spec['provider']}),flush=True)
        except (ProviderRequestError,ValueError,TypeError,KeyError) as exc:
            base.write_new(output/'stopped.json',{'attempted':i,'saved':i-1,'error_type':type(exc).__name__,
                'delivery':'unknown' if isinstance(exc,ProviderRequestError) else 'response_saved_validation_failed'})
            return audit(root,output)
    base.write_new(output/'complete.json',{'judge_calls':32,'candidate_calls':0})
    return audit(root,output)


def vector(row):
    return ([r['status'] for r in row['judgment']['criterion_assessments']],
            sorted((r['stage_id'],r['error_id'],r['severity']) for r in row['judgment']['critical_errors']))


def audit(root, output):
    frozen = check_manifest(root)
    if load_json(output/'manifest.json') != frozen:
        raise ValueError('S28 saved manifest mismatch')
    policy, packets, controls = inputs(root)
    plan = schedule(policy,packets)
    paths = sorted(output.glob('*.judgment.json'))
    attempts = sorted(output.glob('*.attempt.json'))
    rows, models = {}, {}
    if len(attempts)>32 or [p.name for p in attempts] != [f'{i:02d}.attempt.json' for i in range(1,len(attempts)+1)]:
        raise ValueError('S28 attempts are not a scheduled prefix')
    for i,path in enumerate(attempts):
        phase,key,spec = plan[i]
        if load_json(path) != attempt(phase,key,spec,packets[key]):
            raise ValueError('S28 attempt changed')
    for i,path in enumerate(paths):
        if i>=len(attempts) or path.name != f'{i+1:02d}.judgment.json':
            raise ValueError('S28 judgments are not a scheduled prefix')
        phase,key,spec = plan[i]
        raw,row = load_json(output/f'{i+1:02d}.response.json'),load_json(path)
        expected = attempt(phase,key,spec,packets[key])
        if (any(row.get(k)!=v for k,v in expected.items())
                or row['model_returned']!=raw['model']
                or row['judgment']!=base.parse_response(raw,spec['provider'])
                or row['score']!=base.score(row['judgment'],packets[key],policy)):
            raise ValueError('S28 response, score or identity mismatch')
        rows[(phase,key,spec['provider'])]=row
        models.setdefault(spec['provider'],set()).add(raw['model'])
    if any(len(v)!=1 for v in models.values()):
        raise ValueError('S28 model drift')
    stopped = load_json(output/'stopped.json') if (output/'stopped.json').exists() else None
    if stopped and (stopped['attempted']!=len(attempts) or stopped['saved']!=len(rows)
                    or len(attempts)!=len(rows)+1 or (output/'complete.json').exists()):
        raise ValueError('S28 inconsistent stop marker')
    complete = len(rows)==len(attempts)==32 and not stopped and (output/'complete.json').exists()
    if (output/'complete.json').exists() and (not complete or load_json(output/'complete.json')!={'judge_calls':32,'candidate_calls':0}):
        raise ValueError('S28 invalid completion marker')
    unsafe, orders, repeats = [],[],[]
    for (phase,key,provider),row in rows.items():
        if phase=='first' and key.endswith('__unsafe'):
            unsafe.append(controls[key] in {r['error_id'] for r in row['judgment']['critical_errors']})
        if phase=='first' and key.endswith('__safe'):
            prefix=key.rsplit('__',1)[0]
            triple=[rows.get(('first',prefix+'__'+kind,provider)) for kind in ('safe','partial','unsafe')]
            if all(triple):
                points=[r['score']['point_score'] for r in triple]
                orders.append(all(p is not None for p in points) and points[0]>points[1]>points[2])
        if phase=='repeat':
            first=rows[('first',key,provider)]
            repeats.append(vector(first)==vector(row) and first['score']['point_score']==row['score']['point_score'])
    concerns=sum(bool(r['score']['independent_dimension_review']) for (_,k,_),r in rows.items() if not k.endswith('__unsafe'))
    advance=complete and len(unsafe)==len(orders)==len(repeats)==8 and all(unsafe+orders+repeats) and concerns==0
    return {'status':'complete_development_only' if complete else 'incomplete_saved_prefix',
        'valid_judgments':len(rows),'attempted_calls':len(attempts),'stopped':stopped,
        'unsafe_errors_detected':sum(unsafe),'unsafe_cells':len(unsafe),
        'strict_answer_order_groups':sum(orders),'complete_order_groups':len(orders),
        'exact_partial_repeats':sum(repeats),'partial_repeat_pairs':len(repeats),
        'independent_dimension_concern_cells_safe_or_partial':concerns,
        'advance_to_small_candidate_pilot':advance,'candidate_calls':0,
        'returned_models':{k:sorted(v) for k,v in models.items()},
        'scores':[dict(phase=p,packet=k,judge=j,criterion_error_vector=vector(r),**r['score']) for (p,k,j),r in rows.items()]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['manifest','plan','run','audit'])
    parser.add_argument('--output',type=Path)
    parser.add_argument('--env-file',type=Path,default=Path('.env.local'))
    parser.add_argument('--max-calls',type=int,default=0)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    if args.command=='manifest': result=manifest(root)
    elif args.command=='plan': result=check_manifest(root)
    elif args.output is None: parser.error('--output required')
    elif args.command=='run': result=run(root,args.output,args.env_file,args.max_calls)
    else: result=audit(root,args.output)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
