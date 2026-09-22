"""Render a frozen proposal for review without inference or build confirmation."""
import hashlib
import json
import threading
from workspace_data.desktop_plan import ensure_group_root
from workspace_data.task_contract import validate_compiled_retention,validate_retained_interactions
from workspace_tools import ROOT


def preview(jobs,jid):
    status=jobs.get(jid)
    if not status.get('proposal'):
        raise ValueError('A saved proposal is required for a chart preview')
    folder=jobs.root/jid
    raw=(folder/'compiled.json').read_bytes()
    compiled=ensure_group_root(json.loads(raw))
    if compiled['chart']['component'] not in ('LineChart','Scatterplot','ForceDirectedGraph'):
        raise ValueError('Review table records directly in the proposal')
    required=status.get('task_record_ids',[])
    validate_compiled_retention(compiled,required)
    renderer=ROOT/'scripts/workspace-tools/render_chart.mjs'
    lockfile=ROOT/'scripts/workspace-tools/package-lock.json'
    key=hashlib.sha256(raw+renderer.read_bytes()+lockfile.read_bytes()).hexdigest()
    target=folder/'proposal-preview'/key
    with jobs.preview_guard:
        if not (target/'preview-evidence.json').is_file():
            target.mkdir(parents=True,exist_ok=True)
            jobs.save(target,'chart.json',compiled['chart'])
            result=jobs.worker.tools.command([jobs.worker.tools.node,str(renderer),str(target/'chart.json'),str(target)],target,threading.Event(),timeout=30)
            if not result['ok']:
                raise ValueError('The proposed chart could not be rendered. Revise the view or try again')
            evidence=json.loads((target/'render-evidence.json').read_text())
            retention=validate_retained_interactions(compiled,evidence,required)
            svg=(target/'chart.svg').read_bytes()
            if not svg or len(svg)>2_000_000:
                raise ValueError('The proposed chart preview is empty or exceeds the display limit')
            jobs.save(target,'preview-evidence.json',{'compiled_sha256':hashlib.sha256(raw).hexdigest(),'cache_key':key,'model_calls':0,'build_confirmed':False,'retention':retention,'scope':'Read-only chart layout preview; not human acceptance'})
        svg=(target/'chart.svg').read_bytes()
        if not svg or len(svg)>2_000_000:
            raise ValueError('The proposed chart preview exceeds the display limit')
        return svg
