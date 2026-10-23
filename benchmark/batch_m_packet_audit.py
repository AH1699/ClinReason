"""Exact-case audit of batch M boundaries and declared answer edits, offline."""

import json
from pathlib import Path
from .config import load_json
from .criterion_anchors import attach_anchors, validate_anchor_set
from .multiturn import validate_multiturn_dataset, variant_hash
from .multiturn_diagnostics import contrast_packet
from .provenance import sha256_json


def validate_packet(dataset, anchors, contrasts, provenance):
    validate_multiturn_dataset(dataset); validate_anchor_set(anchors,dataset)
    families={f['family_id']:f for f in dataset['families']}
    records={r['family_id']:r for r in provenance['records']}
    if (len(families)!=2 or set(records)!=set(families) or len(records)!=len(provenance['records'])
            or {f['family_id'] for f in anchors['families']}!=set(families)):
        raise ValueError('Batch M family/source/anchor coverage mismatch')
    count=0
    for key,family in families.items():
        wanted=[(t['stage_id'],i) for t in family['variants']['en']['turns']
                for i in range(1,len(t['critical_requirements'])+1)]
        support=records[key]['requirement_support']
        if ([(r['stage'],r['index']) for r in support]!=wanted
                or any(r['guidance_url'] not in family['source_refs'] or not r['basis'] for r in support)):
            raise ValueError('Incomplete source mapping')
        count+=len(wanted)
    seen=set(); hashes={}; paired_edits={}
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
        omitted=edit['partial_omitted_requirement_index']; replacements=edit['unsafe_replacements']
        sep=edit['component_separator']
        if (len(parts)!=len(turn['critical_requirements']) or any(not isinstance(s,str) or not s.strip() for s in parts)
                or type(omitted) is not int or not 1<=omitted<=len(parts)
                or not isinstance(replacements,dict) or not replacements
                or any(k not in {str(i) for i in range(1,len(parts)+1)}
                       or not isinstance(s,str) or not s.strip() or s==parts[int(k)-1] for k,s in replacements.items())
                or sep!=(' ' if key[1]=='en' else '')):
            raise ValueError('Invalid declared answer edits')
        signature=(omitted,sorted(replacements),probe['expected_unsafe_error_id'])
        if key[0] in paired_edits and paired_edits[key[0]]!=signature:
            raise ValueError('Bilingual edit targets differ')
        paired_edits[key[0]]=signature
        expected={'safe':sep.join(parts),'partial':sep.join(s for i,s in enumerate(parts,1) if i!=omitted),
                  'unsafe':sep.join(replacements.get(str(i),s) for i,s in enumerate(parts,1))}
        if not isinstance(probe['initial_response'],str) or not probe['initial_response'].strip():
            raise ValueError('Missing initial response')
        for kind,text in expected.items():
            if probe[f'{kind}_update_response']!=text:
                raise ValueError('Response differs from declared edits')
            packet=attach_anchors(contrast_packet(family,probe,kind),anchors)
            if any(name in packet for name in ('expected_unsafe_error_id','construction','profile')):
                raise ValueError('Author profile leaked into judge packet')
            hashes['__'.join((*key,kind))]=sha256_json(packet)
    if seen!={(f,l) for f in families for l in ('en','zh-Hans')}:
        raise ValueError('Missing paired language')
    return {'status':'offline_structural_check_not_clinical_or_score_validation','family_count':2,
            'variant_count':4,'criterion_positions':count,'bilingual_criterion_positions':2*count,
            'shared_initial_answers':4,'update_answer_examples':12,'packet_hashes':hashes,
            'candidate_calls':0,'judge_calls':0,
            'limits':'Unsafe edits can affect multiple criteria. No expected numeric score, independent clinical validation or default-runner integration.'}


def audit(root):
    return validate_packet(load_json(root/'data/multiturn/batch_m_cases.json'),
        load_json(root/'config/multiturn_criterion_anchors_batch_m_v1.json'),
        load_json(root/'data/multiturn/batch_m_contrasts_v1.json'),
        load_json(root/'data/multiturn/batch_m_provenance.json'))


if __name__=='__main__':print(json.dumps(audit(Path(__file__).resolve().parents[1]),indent=2))
