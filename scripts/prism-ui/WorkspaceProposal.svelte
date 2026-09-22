<script lang="ts">
  import WorkspacePdfPage from '$lib/WorkspacePdfPage.svelte';
  import {onMount} from 'svelte';
  type Proposal = {structure?: {rationale:string;records:{values:Record<string,unknown>;evidence:{record_id:string;field:string;quote:string}[]}[]} | null;interpretation:{findings:{text:string;record_ids:string[]}[];rationale:string;uncertainties:string[];questions:string[]};plan:{title:string;summary:string;fields:{name:string;type:string}[];view:{component:string;groupBy?:string[];x?:string;y?:string;color?:string}}};
  let {proposal, sourceFilename = '', draftKey = '', coverage, evidence = [], busy = false, readOnly = false, onConfirm, onRevise} = $props<{proposal:Proposal;sourceFilename?:string;draftKey?:string;coverage?:{records_shown:number;records_total:number;coverage:string;requested_page_coverage?:{requested:number[];shown:number[];omitted:number[];not_found:number[]};member_coverage?:{source_id:string;filename:string;records_shown:number;records_total?:number;represented:boolean}[]};evidence?:{id:string;locator:Record<string,unknown>;data:Record<string,unknown>}[];busy?:boolean;readOnly?:boolean;onConfirm:()=>void;onRevise:(feedback:string)=>void}>();
  let feedback=$state('');
  let draftReady=$state(false);
  let draftNotice=$state('');
  onMount(()=>{
    if(draftKey && !readOnly) {
      try {feedback=localStorage.getItem('bonsai-proposal-feedback:v1:'+draftKey)?.slice(0,4000) ?? '';}
      catch {draftNotice='Draft storage is unavailable. Keep this page open.';}
    }
    draftReady=true;
  });
  $effect(()=>{
    if(!draftReady || !draftKey || readOnly)return;
    try {
      const key='bonsai-proposal-feedback:v1:'+draftKey;
      if(feedback)localStorage.setItem(key,feedback);else localStorage.removeItem(key);
      draftNotice=feedback ? 'Draft saved in this browser.' : '';
    } catch {draftNotice='Draft could not be saved. Keep this page open.';}
  });
  let alternativeView=$state('');
  function draftViewChange() {
    if(!alternativeView)return;
    const request='Please revise the visualization to '+labels[alternativeView]+'. Preserve the source records, values and citations. Explain which fields support this view and any missing information before building.';
    feedback=(feedback ? feedback+'\n\n' : '')+request;
    feedbackInput?.focus();
  }
  let feedbackInput: HTMLTextAreaElement | undefined = $state();
  function questionFinding(text:string) {
    const question='Please recheck this finding against each cited source: “'+text+'”';
    feedback=(feedback ? feedback+'\n\n' : '')+question;
    feedbackInput?.focus();
  }
  function draftMissingPages() {
    const pages=coverage?.requested_page_coverage?.omitted ?? [];
    if(!pages.length)return;
    const request='Please inspect '+pages.map((page:number)=>'page '+page).join(', ')+'. Explain what these pages add to the proposal and disclose any pages that still do not fit.';
    feedback=(feedback ? feedback+'\n\n' : '')+request;
    feedbackInput?.focus();
  }
  function sourceLink(id:string) {
    const row=evidence.find((item:{id:string;locator:Record<string,unknown>;data:Record<string,unknown>})=>item.id===id);
    if (!row || !/^[a-f0-9]{64}:/.test(id)) return null;
    const loc=row.locator;
    const page=Number(loc.page);
    const seconds=loc.start_seconds ?? loc.time_seconds;
    const time=typeof seconds==='number' && Number.isFinite(seconds) && seconds>=0 ? seconds : null;
    const location=Number.isInteger(page) && page>0 ? 'page '+page
      : time!==null ? time.toFixed(1)+'s'
      : loc.sheet && loc.cell ? String(loc.sheet)+' · '+String(loc.cell)
      : loc.body_block ? 'document block '+String(loc.body_block)
      : loc.line ? 'line '+String(loc.line) : 'source record';
    const fragment=Number.isInteger(page) && page>0 ? '#page='+page : time!==null ? '#t='+time : '';
    return {url:'/api/workspace/sources/'+id.split(':')[0]+'/file'+fragment,
      label:'Open '+(loc.source_filename ? String(loc.source_filename)+' · ' : 'original · ')+location};
  }
  const labels:Record<string,string>={RecordTable:'Inspect source records',ForceDirectedGraph:'Explore connected groups',Scatterplot:'Compare observations',LineChart:'Follow changes over time'};
</script>
<section class="proposal" aria-label="Bonsai proposal">
  <p class="eyebrow">BONSAI · FOR YOUR REVIEW</p><h3>Here’s what I’m seeing</h3>
  {#if coverage?.requested_page_coverage?.requested.length}
    <section class="file-coverage" aria-label="Requested page coverage">
      <h4>Pages you asked Bonsai to inspect</h4>
      <p class="coverage">Included: {coverage.requested_page_coverage.shown.join(', ') || 'None'}. Included text may be excerpted; diagrams are not verified.</p>
      {#if coverage.requested_page_coverage.omitted.length}<p class="omitted">Not read because of the evidence limit: {coverage.requested_page_coverage.omitted.join(', ')}.</p>{#if !readOnly}<button onclick={draftMissingPages} disabled={busy}>Draft a follow-up for these pages</button>{/if}{/if}
      {#if coverage.requested_page_coverage.not_found.length}<p class="omitted">Not found in the supplied records: {coverage.requested_page_coverage.not_found.join(', ')}. Check the page numbers or attach the missing source.</p>{/if}
    </section>
  {/if}
  {#each proposal.interpretation.findings as finding,i (i)}
    <div class="finding">
      <p>{finding.text}</p>
      <details class="finding-evidence"><summary>Compare supporting sources ({finding.record_ids.length})</summary>
        <p class="coverage">These records were cited by Bonsai. Check whether each source supports the claim; citation presence does not verify the interpretation.</p>
        <div class="source-comparison">{#each finding.record_ids as id (id)}
          {@const row=evidence.find((r:{id:string;locator:Record<string,unknown>;data:Record<string,unknown>})=>r.id===id)}{@const link=sourceLink(id)}
          <article aria-label={'Supporting source '+(row?.locator.source_filename ?? id)}>
            <strong>{row?.locator.source_filename ?? 'Source record'}</strong>{#if row?.locator.evidence_channel==='visual'}<p class="coverage">Bonsai visual observation · unreviewed. Check the original source before accepting this interpretation.</p>{/if}{#if row && link && String(row.locator.source_filename ?? sourceFilename).toLowerCase().endsWith('.pdf') && Number.isInteger(Number(row.locator.page)) && Number(row.locator.page)>0}<WorkspacePdfPage sourceId={id.split(':')[0]} page={Number(row.locator.page)}/>{/if}
            {#if row}<dl>{#each Object.entries(row.data) as [field,value] (field)}<dt>{field}</dt><dd>{value===null ? 'Missing value' : typeof value==='object' ? JSON.stringify(value) : String(value)}</dd>{/each}</dl>{:else}<p>Record is not available in this preview.</p>{/if}
            {#if link}<a href={link.url} target="_blank" rel="noreferrer">{link.label}</a>{/if}
            <details><summary>Record provenance</summary><pre>{JSON.stringify({id,locator:row?.locator},null,2)}</pre></details>
          </article>
        {/each}</div>
      </details>
      {#if !readOnly}<button class="question-finding" onclick={()=>questionFinding(finding.text)} disabled={busy}>Question this finding</button>{/if}
    </div>
  {/each}
  {#if coverage}<p class="coverage">Included {coverage.records_shown} of {coverage.records_total} records in the model context. {coverage.coverage}.</p>
    {#if coverage.member_coverage?.length}<section class="file-coverage" aria-label="Files included in this proposal"><h4>Files included in this proposal</h4>{#each coverage.member_coverage as member (member.source_id)}<div><strong>{member.filename}</strong><span>{member.records_shown} of {member.records_total ?? 'unknown'} records included</span>{#if !member.represented}<p class="omitted">Not included in the model context. This proposal cannot establish findings about this file.</p>{/if}</div>{/each}<p class="coverage">Included records may contain excerpts. Coverage describes the input, not verified understanding.</p></section>{/if}
  {/if}

  <h3>I suggest: {proposal.plan.title}</h3><p>{proposal.interpretation.rationale}</p>
  <div class="view"><strong>{labels[proposal.plan.view.component] ?? proposal.plan.view.component}</strong>{#if proposal.plan.view.groupBy}<p>Group by {proposal.plan.view.groupBy.join(' → ')}, then drill into the supporting records.</p>{:else if proposal.plan.view.component === 'RecordTable'}<p>Read the structured fields in a searchable table, open supporting evidence, and attach notes to individual records.</p>{:else}<p>{proposal.plan.view.x} compared with {proposal.plan.view.y}{proposal.plan.view.color ? ', grouped by '+proposal.plan.view.color : ''}.</p>{/if}<p>Click through the evidence, add notes, and ask for changes to the saved view.</p></div>
  {#if !readOnly}<details class="view-choice"><summary>Choose another view</summary><label>View to discuss<select bind:value={alternativeView} disabled={busy}><option value="">Select a view</option>{#each Object.entries(labels) as [component,label] (component)}{#if component!==proposal.plan.view.component}<option value={component}>{label}</option>{/if}{/each}</select></label><button onclick={draftViewChange} disabled={busy || !alternativeView}>Draft this change</button><p class="coverage">Review the draft below, then discuss it with Bonsai before building.</p></details>{/if}
  {#if proposal.structure}<details class="record-review"><summary>Review {proposal.structure.records.length} proposed records</summary><p>{proposal.structure.rationale}</p><p class="coverage">Model-structured, unreviewed. Source quotes are checked for presence; the proposed interpretation still needs your review.</p><div class="structured-records">{#each proposal.structure.records as record,i (i)}<article><strong>Record {i+1}</strong><dl>{#each Object.entries(record.values) as [field,value] (field)}<dt>{field}</dt><dd>{value === null ? 'Missing / unsupported' : String(value)}</dd>{/each}</dl><details><summary>Supporting source passages ({record.evidence.length})</summary>{#each record.evidence as item,j (j)}{@const link=sourceLink(item.record_id)}<div class="citation"><p class="coverage">Source field: {item.field}</p><blockquote>{item.quote}</blockquote>{#if link}<a href={link.url} target="_blank" rel="noreferrer">{link.label}</a>{:else}<p class="coverage">Source record {item.record_id} is not available in this preview.</p>{/if}</div>{/each}</details></article>{/each}</div></details>{/if}
  <details><summary>Proposed field structure</summary><dl>{#each proposal.plan.fields as field (field.name)}<dt>{field.name}</dt><dd>{field.type}</dd>{/each}</dl></details>
  {#if proposal.interpretation.uncertainties.length}<h4>What remains uncertain</h4><ul>{#each proposal.interpretation.uncertainties as item (item)}<li>{item}</li>{/each}</ul>{/if}
  <h4>Does this match what you need?</h4><ul>{#each proposal.interpretation.questions as question (question)}<li>{question}</li>{/each}</ul>
  {#if !readOnly}<label>Clarify or change this proposal<textarea bind:this={feedbackInput} bind:value={feedback} maxlength="4000" placeholder="For example: group by the bottleneck being addressed, then show the evidence for each fix." disabled={busy}></textarea></label>
  {#if draftNotice}<p class="coverage" role="status">{draftNotice}</p>{/if}
  <div class="actions"><button onclick={()=>onRevise(feedback)} disabled={busy || !feedback.trim()}>Discuss this change</button><button class="confirm" onclick={onConfirm} disabled={busy || Boolean(feedback.trim())}>Yes, build this view</button></div>
  {#if feedback.trim()}<p class="coverage" role="status">Discuss your drafted change first, or clear it to build the current proposal.</p>{/if}
  <p class="coverage">Your response stays with this proposal and its evidence. Confirming a view does not label its findings as fact or train the model.</p>{/if}
</section>
<style>
  .proposal{font-size:13px}.citation{margin:12px 0;overflow-wrap:anywhere}.citation a{text-decoration:underline}.eyebrow{font-size:10px;letter-spacing:.12em;color:var(--muted-foreground)}h3{font-weight:500;font-size:19px;margin:22px 0 12px}h4{font-size:13px;font-weight:600;margin:20px 0 8px}p,li{line-height:1.65}.finding{border-left:2px solid var(--border);padding-left:14px;margin:16px 0}.finding p{margin:0 0 7px}details{font-size:11px;margin:8px 0}summary{cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:250px;overflow:auto;font-size:11px}.record-review{border:1px solid var(--border);border-radius:10px;padding:12px 16px;margin:14px 0}.record-review>summary{font-size:13px;font-weight:500}.structured-records{max-height:460px;overflow:auto}.structured-records article{border:1px solid var(--border);border-radius:9px;padding:12px;margin:10px 0}.structured-records dd{overflow-wrap:anywhere}blockquote{margin:10px 0;padding-left:12px;border-left:2px solid var(--border);white-space:pre-wrap}.coverage{font-size:11px;color:var(--muted-foreground)}.view{padding:16px;border:1px solid var(--border);background:var(--background);border-radius:10px}.view p{margin:8px 0 0}dl{display:grid;grid-template-columns:1fr 1fr;gap:6px}dd{margin:0}dt{overflow-wrap:anywhere}textarea{display:block;box-sizing:border-box;width:100%;min-height:90px;padding:12px;margin:10px 0;border:1px solid var(--border);border-radius:8px;background:var(--background);color:inherit;font:inherit}.actions{display:flex;gap:10px;flex-wrap:wrap}button{padding:11px 14px;border:1px solid var(--border);border-radius:8px;background:var(--background);color:inherit;cursor:pointer}.confirm{background:var(--primary);color:var(--primary-foreground)}button:disabled{opacity:.5;cursor:default}ul{padding-left:20px}label{font-size:12px}
.view-choice{margin:14px 0}.view-choice label{display:block;margin:12px 0}.view-choice select{display:block;width:100%;max-width:360px;padding:10px;margin-top:8px;background:var(--background);color:inherit;border:1px solid var(--border);border-radius:8px;font:inherit}
.file-coverage{padding:12px 16px;border:1px solid var(--border);border-radius:10px;margin:16px 0}.file-coverage h4{margin:0 0 12px}.file-coverage>div{padding:10px 0;border-bottom:1px solid var(--border);overflow-wrap:anywhere}.file-coverage strong,.file-coverage span{display:block;font-size:12px}.file-coverage span{font-size:11px;margin-top:4px}.omitted{font-size:12px;color:var(--foreground);border-left:3px solid #b47b2b;padding-left:10px}
.source-comparison{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(260px,100%),1fr));gap:12px}.source-comparison article{min-width:0;padding:12px;border:1px solid var(--border);border-radius:8px;background:var(--background)}.source-comparison strong{overflow-wrap:anywhere}.source-comparison dl{display:block}.source-comparison dt{color:var(--muted-foreground);font-size:10px;margin-top:12px}.source-comparison dd{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;line-height:1.6;margin-top:4px;max-height:260px;overflow:auto}.source-comparison a{display:block;text-decoration:underline;margin:12px 0;font-size:11px}.question-finding{padding:5px 0;border:0;font-size:11px;color:var(--muted-foreground);text-decoration:underline}
</style>
