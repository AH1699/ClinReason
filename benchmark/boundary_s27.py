"""Frozen focused boundary probe; no numeric scoring or default-anchor mutation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_json
from .criterion_anchors import attach_anchors, validate_anchor_set
from .local_settings import read_setting
from .multiturn_diagnostics import contrast_packet
from .provenance import sha256_json, sha256_text
from .providers.http_json import ProviderRequestError, post_json
from .scoring_s26 import GEMINI_ENDPOINT, GROK_ENDPOINT, parse_response, write_new


POLICY = 'config/s27_boundary_policy_v1.json'
FIXTURES = 'data/multiturn/s27_boundary_fixtures_v1.json'
ANCHORS = 'config/multiturn_criterion_anchors_batch_g_s27_v1.json'
PROMPT = 'config/s27_boundary_judge.txt'
MANIFEST = 'config/s27_boundary_frozen_v1.json'
SOURCES = [POLICY, FIXTURES, ANCHORS, PROMPT, 'benchmark/boundary_s27.py',
           'data/multiturn/batch_g_cases.json', 'data/multiturn/batch_g_contrasts_v1.json',
           'benchmark/scoring_s26.py', 'benchmark/criterion_anchors.py', 'benchmark/multiturn.py',
           'benchmark/multiturn_diagnostics.py', 'benchmark/provenance.py', 'benchmark/config.py',
           'benchmark/local_settings.py', 'benchmark/providers/http_json.py',
           'benchmark/providers/gemini.py', 'benchmark/providers/grok.py',
           'benchmark/multiturn_judging.py']
STATUSES = ['met', 'partial', 'missed', 'unclear']
SCHEMA = {'type': 'object', 'properties': {
    'status': {'type': 'string', 'enum': STATUSES},
    'response_evidence': {'type': 'string'}, 'rationale': {'type': 'string'}},
    'required': ['status', 'response_evidence', 'rationale'], 'additionalProperties': False}


def inputs(root):
    policy, fixture = load_json(root/POLICY), load_json(root/FIXTURES)
    dataset, anchors = load_json(root/'data/multiturn/batch_g_cases.json'), load_json(root/ANCHORS)
    validate_anchor_set(anchors, dataset)
    family = next(f for f in dataset['families'] if f['family_id'] == fixture['family_id'])
    probes = load_json(root/'data/multiturn/batch_g_contrasts_v1.json')['probes']
    packets, expected, repeats = {}, {}, set()
    for item in fixture['fixtures']:
        if item['expected_status'] is not None and item['expected_status'] not in STATUSES:
            raise ValueError('Invalid author hypothesis')
        for language in ('en', 'zh-Hans'):
            probe = next(p for p in probes if p['family_id'] == family['family_id'] and p['language'] == language)
            full = attach_anchors(contrast_packet(family, probe, 'safe'), anchors)
            full['transcript'][3]['content'] = item['update_responses'][language]
            target = next(a for a in full['criterion_anchors'] if a['stage_id'] == fixture['stage_id']
                          and a['requirement_index'] == fixture['requirement_index'])
            packet = {k: full[k] for k in ('case_id', 'case_content_hash', 'language', 'transcript')}
            packet['target_requirement'] = target
            packet['level_definitions'] = anchors['levels']
            key = f"{item['profile']}__{language}"
            if key in packets:
                raise ValueError('Duplicate S27 fixture')
            packets[key], expected[key] = packet, item['expected_status']
            if item['profile'] in fixture['repeat_profiles']:
                repeats.add(key)
    if len(packets) != 12 or len(repeats) != 4 or sum(x is not None for x in expected.values()) != 10:
        raise ValueError('S27 fixture count changed')
    return policy, packets, expected, repeats


def manifest(root):
    _, packets, _, _ = inputs(root)
    return {'version': 's27-frozen-v1',
            'files': {p: sha256_text((root/p).read_text(encoding='utf-8')) for p in SOURCES},
            'packets': {k: sha256_json(v) for k, v in sorted(packets.items())}}


def check_manifest(root):
    result = manifest(root)
    if result != load_json(root/MANIFEST):
        raise ValueError('S27 frozen inputs changed; create a new experiment version')
    return result


def validate(judgment, packet):
    if (not isinstance(judgment, dict) or set(judgment) != set(SCHEMA['required'])
            or not all(isinstance(v, str) for v in judgment.values())
            or judgment['status'] not in STATUSES or not judgment['rationale'].strip()):
        raise ValueError('Invalid S27 judgment')
    evidence = judgment['response_evidence']
    if ((judgment['status'] in ('met', 'partial') and not evidence.strip())
            or (evidence and evidence not in packet['transcript'][3]['content'])):
        raise ValueError('S27 evidence must be literal update text')


def schedule(policy, packets, repeats):
    # Hash order removes profile order from the sequence. Profile keys and
    # expected statuses remain local and are never included in request packets.
    ordered = sorted(packets, key=lambda key: sha256_json(packets[key]))
    return [('first', key, judge) for key in ordered for judge in policy['judges']] + [
        ('repeat', key, judge) for key in ordered if key in repeats for judge in policy['judges']]


def request(provider, model, key, packet, instruction, timeout):
    if provider == 'gemini':
        endpoint, header, auth = GEMINI_ENDPOINT, 'x-goog-api-key', key
        payload = {'model': model, 'system_instruction': instruction, 'input': json.dumps(packet, ensure_ascii=False),
                   'store': False, 'response_format': {'type': 'text', 'mime_type': 'application/json', 'schema': SCHEMA}}
    elif provider == 'grok':
        endpoint, header, auth = GROK_ENDPOINT, 'Authorization', f'Bearer {key}'
        payload = {'model': model, 'input': [{'role': 'system', 'content': instruction},
                   {'role': 'user', 'content': json.dumps(packet, ensure_ascii=False)}], 'store': False,
                   'text': {'format': {'type': 'json_schema', 'name': 'boundary_s27', 'schema': SCHEMA, 'strict': True}}}
    else:
        raise ValueError('Unsupported S27 judge')
    return post_json(endpoint, payload, auth_header=header, auth_value=auth, timeout=timeout, retries=0)


def attempt_record(phase, key, spec, packet):
    return {'phase': phase, 'packet_key': key, 'provider': spec['provider'],
            'model_requested': spec['model'], 'packet_sha256': sha256_json(packet)}


def run(root, output, env_file, max_calls):
    frozen = check_manifest(root)
    policy, packets, _, repeats = inputs(root)
    if max_calls != 32 or output.exists() or not output.resolve().is_relative_to((root/'work').resolve()):
        raise ValueError('S27 requires a fresh work/ directory and exactly 32 maximum calls')
    keys = {p: read_setting(env_file, name, secret=True) for p, name in
            [('gemini', 'GEMINI_API_KEY'), ('grok', 'GROK_API_KEY')]}
    output.mkdir(parents=True)
    write_new(output/'manifest.json', frozen)
    models = {}
    for i, (phase, key, spec) in enumerate(schedule(policy, packets, repeats), 1):
        stem = f'{i:02d}'
        attempt = attempt_record(phase, key, spec, packets[key])
        write_new(output/f'{stem}.attempt.json', attempt)
        try:
            raw, latency = request(spec['provider'], spec['model'], keys[spec['provider']], packets[key],
                                   (root/PROMPT).read_text(encoding='utf-8'), policy['request_timeout_seconds'])
            write_new(output/f'{stem}.response.json', raw)
            judgment = parse_response(raw, spec['provider'])
            validate(judgment, packets[key])
            if spec['provider'] in models and models[spec['provider']] != raw['model']:
                raise ValueError('S27 returned model changed')
            models[spec['provider']] = raw['model']
            write_new(output/f'{stem}.judgment.json', {**attempt, 'model_returned': raw['model'],
                                                      'judgment': judgment, 'latency_ms': latency})
            print(json.dumps({'completed': i, 'maximum': 32, 'phase': phase, 'provider': spec['provider']}), flush=True)
        except (ProviderRequestError, ValueError, KeyError, TypeError) as exc:
            write_new(output/'stopped.json', {'attempted': i, 'saved': i-1, 'error_type': type(exc).__name__,
                      'delivery': 'unknown' if isinstance(exc, ProviderRequestError) else 'response_saved_invalid',
                      'automatic_retries': 0})
            return audit(root, output)
    write_new(output/'complete.json', {'judge_calls': 32, 'candidate_calls': 0})
    return audit(root, output)


def audit(root, output):
    frozen = check_manifest(root)
    if load_json(output/'manifest.json') != frozen:
        raise ValueError('S27 saved manifest mismatch')
    policy, packets, expected, repeats = inputs(root)
    plan = schedule(policy, packets, repeats)
    paths = sorted(output.glob('*.judgment.json'))
    rows, models = {}, {}
    for i, path in enumerate(paths, 1):
        if path.name != f'{i:02d}.judgment.json' or i > len(plan):
            raise ValueError('S27 saved judgments are not a scheduled prefix')
        phase, key, spec = plan[i-1]
        attempt = attempt_record(phase, key, spec, packets[key])
        raw, row = load_json(output/f'{i:02d}.response.json'), load_json(path)
        if (load_json(output/f'{i:02d}.attempt.json') != attempt
                or any(row.get(k) != v for k, v in attempt.items())
                or row['model_returned'] != raw['model']
                or row['judgment'] != parse_response(raw, spec['provider'])):
            raise ValueError('S27 saved response/attempt mismatch')
        validate(row['judgment'], packets[key])
        models.setdefault(spec['provider'], set()).add(raw['model'])
        rows[(phase, key, spec['provider'])] = row['judgment']['status']
    if any(len(ids) != 1 for ids in models.values()):
        raise ValueError('S27 returned model drift')
    stopped = load_json(output/'stopped.json') if (output/'stopped.json').exists() else None
    attempts = sorted(output.glob('*.attempt.json'))
    if [p.name for p in attempts] != [f'{i:02d}.attempt.json' for i in range(1, len(attempts)+1)]:
        raise ValueError('S27 noncontiguous attempts')
    for i, path in enumerate(attempts):
        if i >= len(plan) or load_json(path) != attempt_record(*plan[i], packets[plan[i][1]]):
            raise ValueError('S27 unexpected attempt')
    if stopped and (stopped['attempted'] != len(attempts) or stopped['saved'] != len(rows)
                    or len(attempts) != len(rows)+1 or (output/'complete.json').exists()):
        raise ValueError('S27 stop marker inconsistent')
    complete = len(rows) == 32 and len(attempts) == 32 and not stopped and (output/'complete.json').exists()
    if complete and load_json(output/'complete.json') != {'judge_calls': 32, 'candidate_calls': 0}:
        raise ValueError('S27 complete marker changed')
    known = [(status == expected[key]) for (phase, key, provider), status in rows.items()
             if phase == 'first' and expected[key] is not None]
    repeated = [(status == rows[('first', key, provider)]) for (phase, key, provider), status in rows.items() if phase == 'repeat']
    gate = complete and len(known) == 20 and all(known) and len(repeated) == 8 and all(repeated)
    return {'status': 'complete_focused_development_probe' if complete else 'incomplete_saved_prefix',
            'valid_judgments': len(rows), 'attempted_calls': len(attempts), 'stopped': stopped,
            'known_status_matches': sum(known), 'known_first_cells': len(known),
            'repeat_status_matches': sum(repeated), 'repeat_pairs': len(repeated),
            'ready_to_design_full_scoring_repeat': gate, 'candidate_pilot_authorized_by_this_probe': False,
            'candidate_calls': 0, 'returned_models': {k: sorted(v) for k, v in models.items()},
            'cells': [{'phase': phase, 'fixture': key, 'judge': provider, 'status': status,
                       'author_expected_status': expected[key]} for (phase, key, provider), status in rows.items()]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['manifest', 'plan', 'run', 'audit'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--env-file', type=Path, default=Path('.env.local'))
    parser.add_argument('--max-calls', type=int, default=0)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.command == 'manifest':
        result = manifest(root)
    elif args.command == 'plan':
        result = check_manifest(root)
    elif args.output is None:
        parser.error('--output required')
    elif args.command == 'run':
        result = run(root, args.output, args.env_file, args.max_calls)
    else:
        result = audit(root, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
