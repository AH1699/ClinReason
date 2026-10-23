"""Private, conservative OCR date-role check; never infer episode linkage."""

import argparse
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path

from .local_lab_excerpt import private_json


LABELS = {'collection': r'采样时间|采样日期|采集时间|采集日期',
          'received': r'接收时间|接收日期',
          'reported': r'报告时间|报告日期|检验时间|检验日期'}
DATE = (r'(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?'
        r'(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?'
        r'(?![\d:Tt]|\s+\d+:)')


def date_roles(text):
    results = {role: {'label_lines': [], 'candidates': []} for role in LABELS}
    for line_index, line in enumerate(text.splitlines(), 1):
        for role, label in LABELS.items():
            if not re.search(label, line):
                continue
            results[role]['label_lines'].append(line_index)
            # Same-line adjacent values only: do not infer across OCR columns
            # or accept a valid-looking prefix of a malformed date/time.
            for match in re.finditer(r'(?:'+label+r')\s*[:：]?\s*'+DATE, line):
                year, month, day, hour, minute, second = match.groups()
                try:
                    value = datetime(int(year),int(month),int(day),int(hour or 0),int(minute or 0),int(second or 0))
                except ValueError:
                    continue
                results[role]['candidates'].append({'line':line_index,
                    'local_date_time':value.isoformat() if hour is not None else value.date().isoformat(),
                    'precision':'second' if second else 'minute' if hour is not None else 'day',
                    'status':'ocr_candidate_not_source_pixel_verified'})
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hash-prefix',action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    if args.output.exists() or not args.output.resolve().is_relative_to((root/'work').resolve()):
        parser.error('Use a fresh private work/ output file')
    records=[json.loads(p.read_text(encoding='utf-8')) for p in (root/'work/xi_an_ocr_private').glob('*.json')]
    rows=[]
    for prefix in args.hash_prefix:
        matches=[r for r in records if r['sha256'].startswith(prefix)]
        if len(matches)!=1:
            parser.error('Each hash prefix must resolve uniquely')
        r=matches[0]
        if hashlib.sha256(Path(r['source_path']).read_bytes()).hexdigest()!=r['sha256']:
            raise ValueError('Source bytes changed')
        rows.append({'source_sha256':r['sha256'],'page':1,'roles':date_roles(r['pages'][0]['text'])})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    report={'status':'private_date_role_candidates_not_verified_timeline','sources':rows,
            'encounter_linkage_verified':False,'relative_events':[],
            'rule':'Never substitute received/reported time for collection time. No across-line inference or chronology until source pixels and same-episode linkage are verified.'}
    private_json(args.output,report)
    os.chmod(args.output,0o600)
    print(json.dumps({'pages_checked':len(rows),'collection_candidate_pages':sum(bool(r['roles']['collection']['candidates']) for r in rows),
                     'unresolved_collection_pages':sum(not r['roles']['collection']['candidates'] for r in rows),
                     'episode_linkage_verified':False,'timeline_events_created':0}))


if __name__=='__main__':
    main()
