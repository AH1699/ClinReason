"""Fresh two-call transport diagnostic; no resumption of historical panels."""

import argparse
import json
from pathlib import Path

from . import scoring_s26 as base, scoring_s28 as previous
from .config import load_json
from .local_settings import read_setting
from .provenance import sha256_json, sha256_text
from .providers.observed_http import DiagnosticRequestError, post_json_observed

POLICY = 'config/transport_s29_v1.json'
MANIFEST = 'config/transport_s29_frozen_v1.json'
SOURCES = sorted(set(previous.SOURCES + [previous.MANIFEST, POLICY,
    'benchmark/transport_s29.py', 'benchmark/providers/observed_http.py']))


def inputs(root):
    previous.check_manifest(root)
    policy = load_json(root/POLICY)
    scoring, packets, _ = previous.inputs(root)
    if (policy['maximum_calls'] != 2 or policy['automatic_retries'] != 0
            or policy['candidate_calls'] != 0 or policy['timeout_seconds'] != 240
            or policy['judges'] != list(reversed(scoring['judges']))):
        raise ValueError('Unexpected S29 policy')
    return policy, scoring, packets[policy['packet_key']]


def manifest(root):
    _, _, packet = inputs(root)
    return {'version':'s29-frozen-v1',
            'files':{p:sha256_text((root/p).read_text(encoding='utf-8')) for p in SOURCES},
            'packet_sha256':sha256_json(packet)}


def check_manifest(root):
    actual = manifest(root)
    if actual != load_json(root/MANIFEST):
        raise ValueError('S29 frozen input changed; create a new protocol')
    return actual


def attempt(policy, packet, spec):
    return {'packet_key':policy['packet_key'], 'packet_sha256':sha256_json(packet),
            'provider':spec['provider'], 'model_requested':spec['model'],
            'timeout_seconds':policy['timeout_seconds'], 'automatic_retries':0}


def run(root, output, env_file, max_calls):
    frozen = check_manifest(root)
    policy, scoring, packet = inputs(root)
    if max_calls != 2 or output.exists() or not output.resolve().is_relative_to((root/'work').resolve()):
        raise ValueError('Use fresh ignored output and exactly 2 max calls')
    keys = {p:read_setting(env_file,k,secret=True) for p,k in
            [('grok','GROK_API_KEY'),('gemini','GEMINI_API_KEY')]}
    output.mkdir(parents=True,mode=0o700)
    base.write_new(output/'manifest.json',frozen)
    instruction = (root/base.PROMPT).read_text(encoding='utf-8')
    for i,spec in enumerate(policy['judges'],1):
        record = attempt(policy,packet,spec)
        base.write_new(output/f'{i:02d}.attempt.json',record)
        try:
            raw,latency = base.request_judgment(spec['provider'],spec['model'],keys[spec['provider']],
                packet,instruction,policy['timeout_seconds'],transport=post_json_observed)
            base.write_new(output/f'{i:02d}.response.json',raw)
            judgment = base.parse_response(raw,spec['provider'])
            if raw['model'] != spec['model']:
                raise ValueError('Unexpected returned model')
            score = base.score(judgment,packet,scoring)
            base.write_new(output/f'{i:02d}.judgment.json',dict(record,model_returned=raw['model'],
                judgment=judgment,score=score,latency_ms=latency))
            print(json.dumps({'completed':i,'maximum':2,'provider':spec['provider'],
                              'latency_ms':latency}),flush=True)
        except DiagnosticRequestError as exc:
            base.write_new(output/'stopped.json',{'attempted':i,'saved':i-1,
                'kind':'transport_failure','diagnostic':exc.diagnostic})
            return audit(root,output)
        except (ValueError,TypeError,KeyError) as exc:
            base.write_new(output/'stopped.json',{'attempted':i,'saved':i-1,
                'kind':'response_validation_failure','error_type':type(exc).__name__,
                'delivery':'response_saved_validation_failed'})
            return audit(root,output)
    base.write_new(output/'complete.json',{'judge_calls':2,'candidate_calls':0})
    return audit(root,output)


def audit(root, output):
    frozen = check_manifest(root)
    if load_json(output/'manifest.json') != frozen:
        raise ValueError('Saved S29 manifest mismatch')
    policy, scoring, packet = inputs(root)
    attempts = sorted(output.glob('*.attempt.json'))
    paths = sorted(output.glob('*.judgment.json'))
    if not 0 <= len(paths) <= len(attempts) <= 2:
        raise ValueError('Invalid S29 call counts')
    rows=[]
    for i,path in enumerate(attempts,1):
        spec = policy['judges'][i-1]
        record = attempt(policy,packet,spec)
        if path.name != f'{i:02d}.attempt.json' or load_json(path) != record:
            raise ValueError('Attempts must be an exact scheduled prefix')
    for i,path in enumerate(paths,1):
        if path.name != f'{i:02d}.judgment.json':
            raise ValueError('Judgments must be a scheduled prefix')
        spec = policy['judges'][i-1]
        raw = load_json(output/f'{i:02d}.response.json')
        row = load_json(path)
        record = attempt(policy,packet,spec)
        if (any(row.get(k)!=v for k,v in record.items()) or raw['model']!=spec['model']
                or row['model_returned']!=raw['model']
                or row['judgment']!=base.parse_response(raw,spec['provider'])
                or row['score']!=base.score(row['judgment'],packet,scoring)
                or type(row['latency_ms']) is not int or row['latency_ms']<0):
            raise ValueError('Saved S29 response/identity/score mismatch')
        rows.append({'provider':spec['provider'],'model':raw['model'],
            'latency_ms':row['latency_ms'],'response_sha256':sha256_text((output/f'{i:02d}.response.json').read_text()),
            'score':row['score']})
    stopped = load_json(output/'stopped.json') if (output/'stopped.json').exists() else None
    if stopped:
        if (stopped['attempted']!=len(attempts) or stopped['saved']!=len(rows)
                or len(attempts)!=len(rows)+1 or (output/'complete.json').exists()):
            raise ValueError('Invalid S29 stop marker')
        if stopped['kind']=='transport_failure':
            d=stopped['diagnostic']
            if (set(d)!={'version','category','http_status','elapsed_ms','delivery','attempts','automatic_retries'}
                    or d['version']!='transport-diagnostic-v1' or d['attempts']!=1 or d['automatic_retries']!=0
                    or d['category'] not in {'http_error','timeout','tls_error','dns_error','network_error','unreadable_json','unclassified_error'}
                    or d['delivery'] not in {'unknown','response_received','error_response_received_execution_unknown'}
                    or type(d['elapsed_ms']) is not int or d['elapsed_ms']<0
                    or not (d['http_status'] is None or type(d['http_status']) is int and 100<=d['http_status']<=599)):
                raise ValueError('Invalid or unsafe diagnostic fields')
        elif stopped['kind']=='response_validation_failure':
            if not (output/f'{len(attempts):02d}.response.json').exists():
                raise ValueError('Missing failed raw response')
        else:
            raise ValueError('Unknown stop kind')
    complete = len(rows)==len(attempts)==2 and not stopped and (output/'complete.json').exists()
    if (output/'complete.json').exists() and (not complete or load_json(output/'complete.json')!={'judge_calls':2,'candidate_calls':0}):
        raise ValueError('Invalid S29 completion')
    return {'status':'complete_transport_diagnostic_only' if complete else 'incomplete_transport_diagnostic',
        'attempted_calls':len(attempts),'valid_judgments':len(rows),'candidate_calls':0,'automatic_retries':0,
        'timeout_seconds':policy['timeout_seconds'],'stopped':stopped,'rows':rows,
        'may_design_fresh_full_panel':complete,'calibration_complete':False,
        'limits':'Two calls cannot establish reliability or repeatability. No historical repair, pooling, score-based selection or model ranking.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['manifest','plan','run','audit'])
    parser.add_argument('--output',type=Path)
    parser.add_argument('--env-file',type=Path,default=Path('.env.local'))
    parser.add_argument('--max-calls',type=int,default=0)
    args=parser.parse_args(); root=Path(__file__).resolve().parents[1]
    if args.command=='manifest':result=manifest(root)
    elif args.command=='plan':result=check_manifest(root)
    elif args.output is None:parser.error('--output required')
    elif args.command=='run':result=run(root,args.output,args.env_file,args.max_calls)
    else:result=audit(root,args.output)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
