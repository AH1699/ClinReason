"""Bind a directly supplied encounter confirmation to exact local source bytes.

Owner attestation permits grouping, not chronological or clinical verification.
No network, public record export, identity inference or automatic time ordering.
"""

import argparse
import hashlib
import json
from pathlib import Path
from .config import load_json
from .local_lab_excerpt import private_json
from .local_temporal_check import date_roles


def build_manifest(records, confirmation, confirmed_on, source_root):
    if confirmation != 'all files belong to one encounter':
        raise ValueError('An explicit single-encounter owner confirmation is required')
    if not records:
        raise ValueError('No source inventory')
    entries=[]; seen=set()
    for row in records:
        path=Path(row['source_path']).resolve()
        if not path.is_relative_to(source_root.resolve()) or not path.is_file():
            raise ValueError('Source outside the purchased asset scope')
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=row['sha256'] or digest in seen:
            raise ValueError('Changed or repeated source bytes')
        seen.add(digest)
        pages=row['pages']
        if [p['page'] for p in pages]!=list(range(1,len(pages)+1)):
            raise ValueError('OCR page inventory is not contiguous')
        entries.append({'source_path_local_only':str(path),'source_sha256':digest,
                        'encounter_alias':'XIAN-ENCOUNTER-001','page_count':len(pages)})
    return {'version':'private-owner-attested-encounter-v1','confirmed_on':confirmed_on,
        'confirmation_source':'direct project owner message','confirmation':confirmation,
        'status':'owner_attested_single_encounter_not_independently_identifier_verified',
        'files':sorted(entries,key=lambda r:r['source_sha256']),
        'file_count':len(entries),'page_count':sum(r['page_count'] for r in entries),
        'scope_rule':'Only these exact source hashes. New, replaced or unlisted files require a fresh mapping check.',
        'source_identifier_linkage_verified':False,'chronology_verified':False,'privacy_cleared':False,
        'external_model_use_allowed':False}


def temporal_index(records, manifest):
    expected={r['source_sha256']:r['page_count'] for r in manifest['files']}
    if len(records)!=len(expected) or {r['sha256'] for r in records}!=set(expected):
        raise ValueError('Encounter membership mismatch')
    rows=[]
    for record in records:
        if len(record['pages'])!=expected[record['sha256']]:
            raise ValueError('Encounter page count mismatch')
        for page in record['pages']:
            rows.append({'source_sha256':record['sha256'],'page':page['page'],
                         'roles':date_roles(page['text']),
                         'status':'ocr_time_candidates_not_pixel_verified'})
    return {'status':'private_unordered_time_role_index','encounter_alias':'XIAN-ENCOUNTER-001',
        'membership_basis':manifest['status'],'pages':rows,'relative_events':[],
        'chronology_verified':False,'privacy_cleared':False,
        'rule':'Sampling, receipt and reporting are different events. Do not impute missing sampling times or expose later report facts at an earlier decision point.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner-confirmation',required=True)
    parser.add_argument('--confirmed-on',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    if args.output.exists() or not args.output.resolve().is_relative_to((root/'work').resolve()):
        parser.error('Use a fresh ignored work/ output directory')
    records=[load_json(p) for p in sorted((root/'work/xi_an_ocr_private').glob('*.json'))]
    manifest=build_manifest(records,args.owner_confirmation,args.confirmed_on,root/'purchasedAssets')
    index=temporal_index(records,manifest)
    args.output.mkdir(parents=True,mode=0o700)
    private_json(args.output/'encounter_manifest.json',manifest)
    private_json(args.output/'time_role_index.json',index)
    print(json.dumps({'owner_attested_files':manifest['file_count'],'pages':manifest['page_count'],
        'pages_with_time_candidates':{role:sum(bool(p['roles'][role]['candidates']) for p in index['pages'])
                                     for role in ('collection','received','reported')},
        'chronology_verified':False,'privacy_cleared':False,'relative_events':0}))


if __name__=='__main__':main()
