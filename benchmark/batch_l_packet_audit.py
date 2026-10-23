"""Offline structure and exact-edit audit; does not certify clinical labels."""

import argparse
import json
from pathlib import Path

from .config import load_json
from .criterion_anchors import attach_anchors, validate_anchor_set
from .multiturn import validate_multiturn_dataset, variant_hash
from .multiturn_diagnostics import contrast_packet
from .provenance import sha256_json


def validate_packet(dataset, anchors, contrasts, provenance):
    validate_multiturn_dataset(dataset)
    validate_anchor_set(anchors, dataset)
    families={f['family_id']:f for f in dataset['families']}
    records={r['family_id']:r for r in provenance['records']}
    if (len(families)!=5 or set(records)!=set(families)
            or len(records)!=len(provenance['records'])
            or {f['family_id'] for f in anchors['families']}!=set(families)):
        raise ValueError('Batch L family/source/anchor coverage mismatch')
    criterion_count=0
    for family_id,family in families.items():
        wanted=[(t['stage_id'],i) for t in family['variants']['en']['turns']
                for i in range(1,len(t['critical_requirements'])+1)]
        mappings=records[family_id]['requirement_support']
        if ([(r['stage'],r['index']) for r in mappings]!=wanted
                or any(r['guidance_url'] not in family['source_refs'] or not r['basis'] for r in mappings)):
            raise ValueError('Incomplete criterion source mapping')
        criterion_count+=len(wanted)
    seen=set(); hashes={}
    for probe in contrasts['probes']:
        key=probe['family_id'],probe['language']
        if key in seen or key[0] not in families or key[1] not in ('en','zh-Hans'):
            raise ValueError('Duplicate or unknown response variant')
        seen.add(key); family=families[key[0]]
        if probe['case_content_hash']!=variant_hash(family,key[1]):
            raise ValueError('Stale response case hash')
        turn=family['variants'][key[1]]['turns'][1]
        if probe['expected_unsafe_error_id'] not in {e['id'] for e in turn['critical_errors']}:
            raise ValueError('Invented critical error')
        edit=probe['construction']; parts=edit['safe_components']
        omitted,replaced=edit['partial_omitted_requirement_index'],edit['unsafe_replaced_requirement_index']
        if (len(parts)!=len(turn['critical_requirements']) or any(not isinstance(s,str) or not s.strip() for s in parts)
                or type(omitted) is not int or type(replaced) is not int
                or not 1<=omitted<=len(parts) or not 1<=replaced<=len(parts)
                or not isinstance(edit['unsafe_replacement'],str) or not edit['unsafe_replacement'].strip()):
            raise ValueError('Invalid response component construction')
        sep=edit['component_separator']
        if sep!=(' ' if key[1]=='en' else ''):
            raise ValueError('Unexpected component separator')
        expected={'safe':sep.join(parts),'partial':sep.join(s for i,s in enumerate(parts,1) if i!=omitted),
                  'unsafe':sep.join(edit['unsafe_replacement'] if i==replaced else s for i,s in enumerate(parts,1))}
        for kind,text in expected.items():
            if probe[f'{kind}_update_response']!=text or not text.strip():
                raise ValueError('Response differs from the declared single edit')
            packet=attach_anchors(contrast_packet(family,probe,kind),anchors)
            if not probe['initial_response'].strip():
                raise ValueError('Missing initial response')
            if any(name in packet for name in ('expected_unsafe_error_id','construction','profile')):
                raise ValueError('Author control label leaked into packet')
            hashes['__'.join((*key,kind))]=sha256_json(packet)
    if seen!={(f,l) for f in families for l in ('en','zh-Hans')}:
        raise ValueError('Missing paired language response')
    return {'status':'offline_structural_check_not_clinical_or_score_validation','family_count':5,
            'variant_count':10,'criterion_positions':criterion_count,'bilingual_criterion_positions':2*criterion_count,
            'shared_initial_answers':10,'update_answer_examples':30,'judge_packets':len(hashes),
            'packet_hashes':hashes,'candidate_calls':0,'judge_calls':0,
            'limits':'One component edit does not prove independent clinical effects. All anchors, severity and language equivalence await review.'}


def audit(root):
    return validate_packet(load_json(root/'data/multiturn/batch_l_cases.json'),
        load_json(root/'config/multiturn_criterion_anchors_batch_l_v1.json'),
        load_json(root/'data/multiturn/batch_l_contrasts_v1.json'),
        load_json(root/'data/multiturn/batch_l_provenance.json'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(audit(Path(__file__).resolve().parents[1]),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
