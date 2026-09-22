"""Explicit accounting for source records a person asks Bonsai to recheck."""
from copy import deepcopy
from workspace_data.proposal_schema import obj, array, EVIDENCE, TEXT, generation_schema


def review_schema(schema):
    result=deepcopy(schema)
    result['properties']['source_review']=generation_schema(array(obj({'reason':TEXT,'evidence':EVIDENCE}),0,30))
    result['required'].append('source_review')
    return result


def validate_source_review(manifest, proposal, aliases, required=()):
    from workspace_data.proposal import resolve_evidence
    supplied=set(aliases.values())
    if set(required)-supplied:
        raise ValueError('Sources requested for review are missing from the model context; narrow the request explicitly')
    entries=proposal.get('source_review',[])
    if not isinstance(entries,list) or len(entries)>30:
        raise ValueError('source_review must contain at most 30 source exclusion explanations')
    original={row['id']:row for row in manifest['records']}
    excluded=set()
    structure=proposal.get('structure')
    cited={aliases.get(item['record_id'],item['record_id']) for row in (structure or {}).get('records',[]) for item in row['evidence']} if structure is not None else supplied
    for entry in entries:
        if not isinstance(entry,dict) or set(entry)!={'reason','evidence'} or not isinstance(entry['reason'],str) or not 1<=len(entry['reason'].strip())<=2000:
            raise ValueError('Each source_review entry requires a short reason and source evidence')
        resolved=resolve_evidence(manifest,entry['evidence'],aliases,original)
        rid=resolved['record_id']
        if rid in cited or rid in excluded:
            raise ValueError('An excluded source cannot also be cited by structured data or excluded twice')
        excluded.add(rid)
    missing=set(required)-cited-excluded
    if missing:
        reverse={value:key for key,value in aliases.items()}
        raise ValueError('Source review is incomplete for: '+', '.join(reverse[rid] for rid in sorted(missing))+'. Add supported observations to structure.records, or add source_review entries with a specific exclusion reason and a verbatim quote from each excluded source. Merely mentioning a source in prose does not account for it.')
    return {'requested_records':len(required),'represented_records':len(set(required)&cited),'excluded_records':len(set(required)&excluded),'scope':'Citation presence and quoted exclusions only; explanations remain unreviewed'}


def expand_review_ids(proposal, aliases):
    for entry in proposal.get('source_review',[]):
        evidence=entry['evidence']
        evidence['record_id']=aliases[evidence['record_id']]
