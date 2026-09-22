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


def validate_compiled_retention(compiled, required):
    """Check retained source identities and the chart's data before rendering."""
    if not required:
        return
    if compiled.get('excluded_record_ids'):
        raise ValueError('The task requires every source record, but the selected chart excludes records')
    rows=compiled['rows'];seen=Counter()
    for row in rows:
        if compiled.get('record_origin')=='model_structured_unreviewed':
            refs={item['record_id'] for item in row['locator']['source_evidence']}
        else:
            refs={row['id']}
        if len(refs)!=1 or not refs<=set(required):
            raise ValueError('Compiled task rows do not map one-to-one to required sources')
        seen.update(refs)
    if seen!=Counter(required):
        raise ValueError('Compiled task rows omit or duplicate required sources')
    ids=[row['id'] for row in rows]
    if len(ids)!=len(set(ids)):
        raise ValueError('Compiled task record IDs must be unique')
    chart=compiled['chart']
    if chart['component'] in ('LineChart','Scatterplot'):
        if Counter(point['record_id'] for point in chart['props']['data'])!=Counter(ids):
            raise ValueError('Chart data omits or duplicates required task records')
    elif chart['component']=='ForceDirectedGraph':
        represented={rid for members in compiled['node_membership'].values() for rid in members}
        if represented!=set(ids):
            raise ValueError('Chart groups do not retain every required task record')


def validate_retained_interactions(compiled, evidence, required):
    """Check interaction targets, without claiming visual or semantic accuracy."""
    if not required:
        return None
    validate_compiled_retention(compiled,required)
    component=compiled['chart']['component']
    if component=='RecordTable':
        if evidence.get('record_count')!=len(required):
            raise ValueError('Table evidence does not retain the required record count')
        kind='table_rows'
    elif component in ('LineChart','Scatterplot'):
        expected=Counter(row['id'] for row in compiled['rows'])
        actual=Counter(point['record_id'] for point in evidence.get('interaction',{}).get('points',[]))
        if actual!=expected:
            raise ValueError('Rendered chart interaction targets omit or duplicate required records')
        kind='point_targets'
    else:
        available={node['id'] for node in evidence.get('interaction',{}).get('nodes',[])}
        members=compiled['node_membership']
        if any(members[node] and node not in available for node in members):
            raise ValueError('Rendered graph is missing a required group interaction target')
        kind='group_targets'
    return {'required_source_records':len(required),'retained_rows':len(compiled['rows']),
            'checked_targets':kind,'status':'passed',
            'scope':'Source identities and interaction targets; not geometry, factual accuracy or human acceptance'}
