"""Local-only field alignment candidates; never approve identity or chronology."""

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import subprocess
import tempfile
from pathlib import Path

from .local_lab_excerpt import private_json, recognize_boxes
from .local_temporal_check import date_roles

LABELS = {'collection':r'采样时间|采样日期|采集时间|采集日期',
          'received':r'接收时间|接收日期', 'reported':r'报告时间|报告日期|检验时间|检验日期',
          'patient_name':r'姓名', 'admission_id':r'住院号|住院流水号',
          'record_id':r'病案号|病历号', 'sex':r'性别', 'age':r'年龄'}


def acceptable(role, value):
    value=value.strip().strip(':：').strip()
    if role in ('collection','received','reported'):
        label={'collection':'采样时间','received':'接收时间','reported':'报告时间'}[role]
        # Whole date cell only, not a date embedded in unrelated text.
        if not re.fullmatch(r'20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}日?(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?',value): return None
        rows=date_roles(label+':'+value)[role]['candidates']
        return rows[0]['local_date_time'] if len(rows)==1 else None
    patterns={'patient_name':r'[\u4e00-\u9fff]{2,4}', 'admission_id':r'[A-Za-z0-9-]{4,32}',
              'record_id':r'[A-Za-z0-9-]{4,32}', 'sex':r'男|女', 'age':r'\d{1,3}\s*岁'}
    return re.sub(r'\s+','',value) if re.fullmatch(patterns[role],value) else None


def extract_fields(boxes):
    fields={role:[] for role in LABELS}
    for role,pattern in LABELS.items():
        for box in boxes:
            label=re.fullmatch(r'\s*('+pattern+r')\s*[:：]?\s*(.*?)\s*',box['text'])
            if not label: continue
            inline=acceptable(role,label.group(2))
            if inline:
                fields[role].append({'value':inline,'bounds':box['bounds'],'method':'inline'})
                continue
            if label.group(2): continue  # Never skip over unparsed inline text.
            x0,y0,x1,y1=box['bounds']; cy=(y0+y1)/2; height=y1-y0
            candidates=[]
            for other in boxes:
                a,b,c,d=other['bounds']
                if 0<=a-x1<=.22 and abs((b+d)/2-cy)<height*.55:
                    candidates.append(other)
            # Only the nearest cell may supply the value. Do not jump over a
            # different field or choose whichever candidate looks convenient.
            if candidates:
                nearest=min(candidates,key=lambda b:b['bounds'][0])
                value=acceptable(role,nearest['text'])
                if value: fields[role].append({'value':value,'bounds':nearest['bounds'],'method':'same_visual_row'})
    return fields


def compare(left, right):
    def unique(fields,role):
        values={r['value'] for r in fields[role]}
        return next(iter(values)) if len(values)==1 else None
    matches={}
    conflicts=[]
    for role in ('patient_name','admission_id','record_id','sex','age'):
        a,b=unique(left,role),unique(right,role)
        matches[role]=None if a is None or b is None else a==b
        if matches[role] is False: conflicts.append(role)
    return {'field_matches':matches,'conflicting_fields':conflicts,
            'same_person_candidate':not conflicts and matches['patient_name'] is True and matches['sex'] is True,
            'same_admission_candidate':not conflicts and matches['patient_name'] is True and matches['admission_id'] is True,
            'verified_linkage':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hash-prefix',action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    if args.output.exists() or not args.output.resolve().is_relative_to((root/'work').resolve()):
        parser.error('Use a fresh private work/ output directory')
    records=[json.loads(p.read_text()) for p in (root/'work/xi_an_ocr_private').glob('*.json')]
    selected=[]
    for prefix in args.hash_prefix:
        matches=[r for r in records if r['sha256'].startswith(prefix)]
        if len(matches)!=1: parser.error('Each source prefix must resolve uniquely')
        record=matches[0]
        if hashlib.sha256(Path(record['source_path']).read_bytes()).hexdigest()!=record['sha256']:
            raise ValueError('Source changed')
        selected.append(record)
    if len({r['sha256'] for r in selected})!=len(selected): parser.error('Repeated source')
    args.output.mkdir(parents=True,mode=0o700)
    os.chmod(args.output,0o700)
    salt=secrets.token_bytes(32)
    private_json(args.output/'local_key.json',{'hmac_key_hex':salt.hex(),'scope':'this local review only'})
    rows=[]; raw_fields=[]
    for record in selected:
        with tempfile.TemporaryDirectory(prefix='clinreason_linkage_') as tmp:
            png=Path(tmp)/'page.png'
            subprocess.run(['pdftoppm','-f','1','-l','1','-r','180','-singlefile','-png',
                            record['source_path'],str(png.with_suffix(''))],check=True,capture_output=True)
            fields=extract_fields(recognize_boxes(png))
        raw_fields.append(fields)
        # Names/IDs are never persisted in plaintext by this utility. Exact dates
        # remain local review candidates; do not publish or infer relative days.
        safe={role:[dict(row,value=hmac.new(salt,row['value'].encode(),hashlib.sha256).hexdigest())
                    if role not in ('collection','received','reported') else row for row in values]
              for role,values in fields.items()}
        rows.append({'source_sha256':record['sha256'],'page':1,'fields':safe,
                     'status':'ocr_alignment_candidates_not_visual_verification'})
    pairs=[dict(left=i,right=j,**compare(raw_fields[i],raw_fields[j]))
           for i in range(len(rows)) for j in range(i+1,len(rows))]
    private_json(args.output/'field_candidates.json',{'sources':rows,'pairs':pairs,
        'relative_events':[],'verified_linkage':False,'privacy_cleared':False,
        'limits':'Same name, age or bed is not encounter identity. OCR equality is not source-pixel approval. Do not publish absolute dates or create clinical questions from these candidates.'})
    print(json.dumps({'pages_checked':len(rows),'collection_candidate_pages':sum(bool(r['fields']['collection']) for r in rows),
        'admission_id_candidate_pages':sum(bool(r['fields']['admission_id']) for r in rows),
        'same_person_candidate_pairs':sum(p['same_person_candidate'] for p in pairs),
        'same_admission_candidate_pairs':sum(p['same_admission_candidate'] for p in pairs),
        'conflicting_pairs':sum(bool(p['conflicting_fields']) for p in pairs),
        'verified_linkage':False,'relative_events_created':0}))


if __name__=='__main__': main()
