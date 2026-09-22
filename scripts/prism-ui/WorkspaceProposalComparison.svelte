<script lang="ts">
  import WorkspaceModelEvidence from '$lib/WorkspaceModelEvidence.svelte';
  let {jobId}:{jobId:string}=$props();
  let comparison=$state<any>(null);
  let busy=$state(false);
  let error=$state('');
  const labels:Record<string,string>={source_snapshot:'Source snapshot',source_context:'Source context',generation_settings:'Generation settings',model_runtime:'Model and runtime',harness:'Harness files',recorded_parent_snapshot:'Previous source snapshot matches its recorded hash'};
  async function load(){
    busy=true;error='';
    try{
      const response=await fetch('/api/workspace/source-jobs/'+jobId+'/comparison',{cache:'no-store'});
      const data=await response.json();if(!response.ok)throw new Error(data.error ?? 'Comparison could not be loaded');comparison=data;
    }catch(e){error=String(e);}finally{busy=false;}
  }
  function value(item:unknown){return item===null ? 'Not provided' : typeof item==='object' ? JSON.stringify(item) : String(item);}
  function viewLabel(view:any){return view.component==='RecordTable' ? 'Table · '+view.columns.join(', ') : view.component==='ForceDirectedGraph' ? 'Network · '+view.groupBy.join(', ') : view.component+' · '+view.x+' / '+view.y+(view.color ? ' · Color: '+view.color : '');}
</script>
<details class="proposal-comparison" ontoggle={event=>{if(event.currentTarget.open && !comparison && !busy && !error)void load();}}>
  <summary>What changed in this proposal?</summary>
  {#if busy}<p role="status">Comparing saved versions…</p>{/if}
  {#if error}<p role="alert">{error}</p><button onclick={load} disabled={busy}>Retry comparison</button>{/if}
  {#if comparison}
    <p class="counts">{comparison.records.unchanged} structured records keep the same values and citations. {comparison.records.previous_only} appear only in the previous version; {comparison.records.current_only} appear only in this version.</p>
    <p>{comparison.view_changed ? 'The visualization choice changed.' : 'The visualization choice is unchanged.'} Changed records appear on both sides; this comparison does not infer which records correspond.</p>
    {#if comparison.feedback}<details><summary>Requested change</summary><blockquote>{comparison.feedback}</blockquote></details>{/if}
    <details><summary>Source and configuration comparison</summary><dl>{#each Object.entries(comparison.matches) as [key,match] (key)}<div><dt>{labels[key] ?? key}</dt><dd>{match===true ? 'Matches' : match===false ? 'Differs' : 'Not recorded'}</dd></div>{/each}</dl><p>Matching metadata does not prove identical inference context or cache state, factual accuracy, or human acceptance.</p></details>
    <div class="versions">
      {#each [['Previous',comparison.previous],['Current',comparison.current]] as [label,version] (label)}
        <section aria-label={label+' proposal version'}><h4>{label}</h4><p>{version.plan.title}</p><p class="view">{viewLabel(version.plan.view)}</p><p>{version.plan.summary}</p>
          <WorkspaceModelEvidence config={version.generation_config}/>
          <details><summary>Interpretation and uncertainties</summary><ul>{#each version.interpretation.findings as finding,i (i)}<li>{finding.text}</li>{/each}</ul>{#if version.interpretation.uncertainties.length}<h5>Uncertainties</h5><ul>{#each version.interpretation.uncertainties as uncertainty,i (i)}<li>{uncertainty}</li>{/each}</ul>{/if}</details>
          <details><summary>Structured records ({version.records.length})</summary>{#each version.records as record,index (index)}<article><h5>Record {index+1}</h5><dl>{#each Object.entries(record.values) as [field,item] (field)}<div><dt>{field.replaceAll('_',' ')}</dt><dd>{value(item)}</dd></div>{/each}</dl><details><summary>Cited passages</summary>{#each record.evidence as evidence,i (i)}<blockquote>{evidence.quote}</blockquote><p class="fine">Source record: {evidence.record_id}</p>{/each}</details></article>{/each}</details>
          {#if version.planning_elapsed_seconds != null}<p class="fine">Planning: {version.planning_elapsed_seconds} seconds</p>{/if}
          {#if version.planning_url}<a href={version.planning_url} target="_blank" rel="noreferrer">Open {label.toLowerCase()} planning run</a>{/if}
        </section>
      {/each}
    </div>
  {/if}
</details>
<style>
 .proposal-comparison{margin:16px 0;border-top:1px solid var(--border);padding-top:12px;font-size:13px;line-height:1.6}summary{cursor:pointer;padding:6px 0}p{margin:10px 0;overflow-wrap:anywhere}.counts{font-weight:600}.versions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-top:14px}section,article{min-width:0;border:1px solid var(--border);border-radius:10px;padding:14px}article{margin:10px 0}h4,h5{margin:0 0 8px}h4{font-size:15px}h5{font-size:13px}.view{font-weight:600}dl{margin:10px 0}dl div{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px;border-bottom:1px solid var(--border);padding:6px 0}dt,dd{margin:0;overflow-wrap:anywhere}dt{color:var(--muted-foreground)}blockquote{margin:8px 0;padding-left:12px;border-left:2px solid var(--border);white-space:pre-wrap;overflow-wrap:anywhere}ul{padding-left:20px}li{margin:8px 0;overflow-wrap:anywhere}.fine{font-size:11px;color:var(--muted-foreground)}a{text-decoration:underline}button{font:inherit;padding:8px;background:var(--card);color:inherit;border:1px solid var(--border);border-radius:6px}summary:focus-visible,button:focus-visible,a:focus-visible{outline:2px solid var(--ring);outline-offset:3px}@media(max-width:750px){.versions{grid-template-columns:1fr}}
</style>
