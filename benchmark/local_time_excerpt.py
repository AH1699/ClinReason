"""Render only previously recognized inline time cells for private pixel review."""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from .config import load_json
from .local_lab_excerpt import private_json


def time_cells(source):
    cells=[]
    for role in ('collection','received','reported'):
        for row in source['fields'][role]:
            bounds=row['bounds']
            if row['method']!='inline':continue
            if (len(bounds)!=4 or not all(type(v) in (int,float) for v in bounds)
                    or not 0<=bounds[0]<bounds[2]<=1 or not 0<=bounds[1]<bounds[3]<=1
                    or bounds[2]-bounds[0]>.4 or bounds[3]-bounds[1]>.06):
                raise ValueError('Unsafe time-cell bounds')
            cells.append({'role':role,'bounds':bounds,'ocr_candidate':row['value'],
                          'verification':'pending_source_pixel_check'})
    return cells


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hash-prefix',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    if args.output.exists() or not args.output.resolve().is_relative_to((root/'work').resolve()):
        parser.error('Use fresh private work/ output')
    fields=load_json(root/'work/xi_an_linkage_candidates_v1/field_candidates.json')['sources']
    matches=[r for r in fields if r['source_sha256'].startswith(args.hash_prefix)]
    if len(matches)!=1:parser.error('Prefix must uniquely resolve to reviewed fields')
    source=matches[0];cells=time_cells(source)
    records=[load_json(p) for p in (root/'work/xi_an_ocr_private').glob('*.json')]
    record=next(r for r in records if r['sha256']==source['source_sha256'])
    if hashlib.sha256(Path(record['source_path']).read_bytes()).hexdigest()!=record['sha256']:
        raise ValueError('Source bytes changed')
    from PIL import Image
    args.output.mkdir(parents=True,mode=0o700)
    with tempfile.TemporaryDirectory(prefix='clinreason_time_') as tmp:
        png=Path(tmp)/'page.png';page=str(source['page'])
        subprocess.run(['pdftoppm','-f',page,'-l',page,'-r','240','-singlefile','-png',
                        record['source_path'],str(png.with_suffix(''))],check=True,capture_output=True)
        with Image.open(png) as original:
            for i,cell in enumerate(cells,1):
                a,b,c,d=cell['bounds'];w,h=original.size
                # No expansion into neighboring identity cells.
                image=original.crop((int(a*w),int(b*h),int(c*w)+1,int(d*h)+1))
                target=args.output/f'{i:02d}_{cell["role"]}.png'
                image.save(target);os.chmod(target,0o600)
                cell['image_local_only']=str(target.relative_to(root) if target.is_absolute() else target)
    private_json(args.output/'time_cells.json',{'source_sha256':record['sha256'],
        'page':source['page'],'cells':cells,'privacy_cleared':False,
        'limits':'Exact dates remain local. Source date labels and OCR values need visual review. Report time is not sampling time or proven clinician availability.'})
    print(json.dumps({'time_cell_images':len(cells),'roles':[c['role'] for c in cells],
                      'status':'private_pixel_review_pending'}))


if __name__=='__main__':main()
