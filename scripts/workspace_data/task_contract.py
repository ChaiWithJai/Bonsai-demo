"""Explicit data-retention requirements, independent of chart validity."""
from collections import Counter


def task_record_ids(manifest, scope, contract):
    if contract is None:
        return []
    if contract != {'record_policy':'one_per_source_record'}:
        raise ValueError('Task contract requires record_policy one_per_source_record')
    ids=[row['id'] for row in manifest['records'] if scope is None or row.get('locator',{}).get('page') in scope['pages']]
    if not 1<=len(ids)<=30:
        raise ValueError('One-record-per-source tasks currently require 1 to 30 source records; narrow the source scope explicitly')
    return ids


def validate_task_records(proposal, packet, required):
    if not required:
        return
    if not isinstance(proposal,dict):
        raise ValueError('Task proposal must be an object')
    aliases=packet['record_id_map'];shown=set(aliases.values())
    if set(required)-shown:
        raise ValueError('Required source records are missing from the model context; this task cannot use sampled coverage')
    structure=proposal.get('structure')
    if structure is None:
        return  # Original records are retained by the compiler; exclusions are checked afterward.
    if not isinstance(structure,dict) or not isinstance(structure.get('records'),list):
        raise ValueError('Task structure requires a records array')
    seen=Counter()
    for row in structure['records']:
        if not isinstance(row,dict) or not isinstance(row.get('evidence'),list) or any(not isinstance(item,dict) or not isinstance(item.get('record_id'),str) for item in row['evidence']):
            raise ValueError('Each task record requires source evidence')
        refs={aliases.get(item['record_id'],item['record_id']) for item in row['evidence']}
        if len(refs)!=1 or not refs<=set(required):
            raise ValueError('Task requires one output record per source record. Each output record must cite exactly one distinct required source record; multiple passages from that record are allowed')
        seen.update(refs)
    reverse={value:key for key,value in aliases.items()}
    missing=[reverse[rid] for rid in required if not seen[rid]]
    repeated=[reverse[rid] for rid in required if seen[rid]>1]
    if missing or repeated:
        raise ValueError('Task requires exactly one output record per source record. Missing: '+', '.join(missing)+'; repeated: '+', '.join(repeated)+'. Extract the missing records from their supplied evidence. Do not change the chart type to bypass this data requirement')
