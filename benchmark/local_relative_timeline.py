"""Private relative time scaffold from owner grouping and pixel-checked times.

Collection, laboratory analysis and receipt are not interchangeable. This does
not establish result availability, a clinical sequence or safe case release.
"""

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from .config import load_json
from .local_lab_excerpt import private_json


def build_timeline(manifest, facts, time_review):
    if manifest['status']!='owner_attested_single_encounter_not_independently_identifier_verified':
        raise ValueError('Missing explicit encounter attestation')
    members={r['source_sha256']:r['page_count'] for r in manifest['files']}
    allowed={'collection','received','laboratory_analysis','report_issued'}
    rows=[];seen=set()
    for row in time_review['verified_time_cells']:
        key=row['source_sha256'],row['page'],row['role']
        if (key in seen or key[0] not in members or not 1<=key[1]<=members[key[0]]
                or row['role'] not in allowed or row['status']!='source_label_and_value_visually_checked'
                or not row['source_label']):
            raise ValueError('Unverified, duplicate or out-of-scope time cell')
        expected_labels={'collection':'采样时间','received':'接收时间',
                         'laboratory_analysis':'检验时间','report_issued':'报告时间'}
        if row['source_label']!=expected_labels[row['role']]:
            raise ValueError('Source label and time role mismatch')
        stamp=datetime.fromisoformat(row['local_date_time'])
        if stamp.tzinfo is not None or row['precision'] not in ('minute','second'):
            raise ValueError('Unsupported timestamp precision or timezone')
        if row['precision']=='minute' and stamp.second!=0:
            raise ValueError('Minute precision cannot assert seconds')
        seen.add(key); rows.append((stamp,row))
    collections=[stamp for stamp,row in rows if row['role']=='collection']
    if not collections:raise ValueError('No verified collection-time anchor')
    origin=min(collections); events=[]
    for stamp,row in sorted(rows,key=lambda pair:(pair[0],pair[1]['source_sha256'],pair[1]['role'])):
        # Use minutes only; keep source precision without inventing sub-minute certainty.
        events.append({'source_sha256':row['source_sha256'],'page':row['page'],'role':row['role'],
            'relative_day':(stamp.date()-origin.date()).days,
            'minutes_from_anchor':int((stamp-origin).total_seconds()//60),
            'precision':row['precision'],'decision_time_result_available':False})
    mapped=[];unplaced=[]
    for source in facts['sources']:
        if source['source_sha256'] not in members:raise ValueError('Lab source outside encounter')
        sample=[e for e in events if e['source_sha256']==source['source_sha256']
                and e['page']==source['page'] and e['role']=='collection']
        if source['verified_source_rows']:
            record={'source_sha256':source['source_sha256'],'page':source['page'],
                'verified_source_rows':source['verified_source_rows'],
                'decision_time_eligible':False,
                'reason':'Result availability and clinical context not verified'}
            if len(sample)==1:
                mapped.append(dict(record,collection_relative_day=sample[0]['relative_day'],
                                   collection_minutes_from_anchor=sample[0]['minutes_from_anchor']))
            else:unplaced.append(dict(record,collection_relative_day=None))
    return {'status':'private_relative_time_scaffold_not_case_ready',
        'encounter_alias':'XIAN-ENCOUNTER-001','membership_basis':manifest['status'],
        'anchor':'Earliest source-pixel-verified collection in this review subset, not admission or symptom onset',
        'event_count':len(events),'events':events,'collection_linked_lab_pages':mapped,
        'lab_pages_without_verified_collection':unplaced,'absolute_dates_exported':False,
        'full_record_privacy_cleared':False,'clinical_course_verified':False,'case_ready':False,
        'limits':'Same-encounter membership does not prove relative clinical evolution. Receipt is not collection; laboratory analysis is not report issuance or clinician availability. No trend, treatment effect or diagnosis is inferred.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--facts',type=Path,required=True)
    parser.add_argument('--time-review',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    if args.output.exists() or not args.output.resolve().is_relative_to((root/'work').resolve()):
        parser.error('Use fresh ignored work/ output')
    manifest=load_json(args.manifest)
    for source in manifest['files']:
        if hashlib.sha256(Path(source['source_path_local_only']).read_bytes()).hexdigest()!=source['source_sha256']:
            raise ValueError('Confirmed source bytes changed')
    result=build_timeline(manifest,load_json(args.facts),load_json(args.time_review))
    private_json(args.output,result)
    print(json.dumps({'verified_time_events':result['event_count'],
        'collection_linked_lab_pages':len(result['collection_linked_lab_pages']),
        'unplaced_lab_pages':len(result['lab_pages_without_verified_collection']),
        'case_ready':False,'privacy_cleared':False}))


if __name__=='__main__':main()
