<script lang="ts">
  import type { SourceData, SourceSummary } from '$lib/workspace-data-types';
  import WorkspaceImageEvidence from '$lib/WorkspaceImageEvidence.svelte';
  import WorkspaceProposal from '$lib/WorkspaceProposal.svelte';
  import { onMount } from 'svelte';
  import WorkspaceRecordReview from '$lib/WorkspaceRecordReview.svelte';
  let { onProject = (_id: string) => {} } = $props<{onProject?: (id: string) => void}>();
  type Job = {id:string; source_id:string; source_ids?:string[]; filename:string; request:string; status:string; stage:string; workspace_id?:string; error?:string; mlflow_url?:string; proposal?:any; proposal_sha256?:string; source_coverage?:any; source_examples?:any[]};
  let jobs = $state<Job[]>([]);
  let intent = $state('');
  let selectedRecord = $state('');
  let audioPlayer: HTMLAudioElement | undefined = $state();
  let applyReviews = $state(false);
  let attached = $state<string[]>([]);
  const runningJob = $derived(jobs.find(job => ['queued','running'].includes(job.status)));
  let sources = $state<SourceSummary[]>([]);
  let source = $state<SourceData | null>(null);
  const conversationJobs = $derived(jobs.filter(job => !source || job.source_id === source.source_id));
  let error = $state('');
  let busy = $state(false);
  async function request(path = '', options?: RequestInit) {
    const response = await fetch('/api/workspace/sources' + path, options);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Source request failed');
    return result;
  }
  async function refresh() { sources = (await request()).sources; }
  async function choose(id: string) {
    error = '';
    try { source = await request('/' + id);
      if(source?.kind === 'collection') attached=(source.sources ?? []).map(item=>item.source_id);
      else if(!attached.includes(id)) attached=[...attached,id];
    }
    catch (e) { error = String(e); }
  }
  async function removeAttachment(id:string) {
    attached=attached.filter(value=>value!==id);
    if(!attached.length)source=null;
    else if(source?.source_id===id || source?.kind==='collection')await choose(attached[0]);
  }
  async function upload(event: Event & {currentTarget: HTMLInputElement}) {
    const files=Array.from(event.currentTarget.files ?? []);
    if (!files.length) return;
    if (files.length + attached.length > 20) {error='Attach at most 20 files to one question';return;}
    busy = true; error = '';const failures:string[]=[];
    try {
      for(const file of files) {
        try {
          if (file.size > 25 * 1024 * 1024) throw new Error('Choose a file of at most 25 MiB');
          const uploaded=await request('', {method: 'POST', headers: {'Content-Type': 'application/octet-stream', 'X-Source-Filename': encodeURIComponent(file.name)}, body: file});
          source=uploaded;
          if(!attached.includes(uploaded.source_id)) attached=[...attached,uploaded.source_id];
        } catch(e) { failures.push(file.name+': '+String(e)); }
      }
      await refresh();error=failures.join('\n');
    } catch (e) { error = String(e); }
    finally { busy = false; }
  }
  async function extractMedia() {
    if(!source)return;busy=true;error='';
    try { source=await request('/'+source.source_id+'/extract',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});await refresh(); }
    catch(e){error=String(e);}finally{busy=false;}
  }
  async function jobRequest(path = '', body?: object) {
    const response = await fetch('/api/workspace/source-jobs' + path, body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {cache:'no-store'});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Job request failed');
    return result;
  }
  async function generate(event: SubmitEvent) {
    event.preventDefault(); if (!source || runningJob || busy) return;
    busy=true;error='';
    try {
      if(attached.length>1) { source=await request('/collection',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_ids:attached,apply_reviews:applyReviews})});await refresh(); }
      if(!source)return;
      await request('/'+source.source_id+'/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request:intent,apply_reviews:applyReviews})});
      jobs=(await jobRequest()).jobs;
    } catch(e) { error=String(e); } finally { busy=false; }
  }
  async function respondToProposal(job:Job, feedback?:string) {
    busy=true;error='';
    try { await jobRequest('/'+job.id+(feedback === undefined ? '/confirm' : '/revise'),feedback === undefined ? {proposal_sha256:job.proposal_sha256} : {feedback});jobs=(await jobRequest()).jobs; }
    catch(e){error=String(e);}finally{busy=false;}
  }
  async function cancel(id:string) {
    try { await jobRequest('/'+id+'/cancel',{}); } catch(e) { error=String(e); }
  }
  onMount(() => {
    let stopped=false;let timer:ReturnType<typeof setTimeout>;
    refresh().catch(e=>error=String(e));
    async function poll() {
      try { jobs=(await jobRequest()).jobs; } catch(e) { if(!stopped) error=String(e); }
      if(!stopped) timer=setTimeout(poll,1500);
    }
    void poll();return()=>{stopped=true;clearTimeout(timer);};
  });
</script>

<section class="data" aria-label="Desktop sources">
  <h2>Bring your files and a question.</h2>
  <p>Bonsai will explain what it finds and propose a view. Discuss the proposal before building it.</p>
  <label for="visualization-intent">What should this visualization help you understand?</label><textarea id="visualization-intent" form="source-request" bind:value={intent} minlength="10" maxlength="4000" required placeholder="What are you trying to understand, compare, or discuss with your team?" disabled={busy}></textarea>
  <label class="upload">{busy ? 'Extracting source; PDFs may take a moment…' : 'Attach files'}<input type="file" multiple accept=".eml,.mbox,.csv,.tsv,.json,.jsonl,.txt,.md,.png,.jpg,.jpeg,.webp,.pdf,.wav,.mp3,.m4a,.mp4,.mov,.webm" onchange={upload} disabled={busy}/></label>
  <p class="fine">Up to 20 files, 25 MiB each. Tables, text, email exports, and PDF pages are extracted locally. PDF pages without embedded text use OCR on this Mac. Images use local OCR. English audio uses local Whisper transcription. Visual interpretation and video workflows are still being connected.</p>
  {#if attached.length}<div class="attachments" aria-label="Attached files">{#each attached as id (id)}{@const file=sources.find((item:SourceSummary)=>item.source_id===id)}<div><button class="attachment" onclick={()=>choose(id)} disabled={busy}>{file?.filename ?? 'Attached file'}</button><button class="remove" aria-label={'Remove '+(file?.filename ?? 'attached file')} onclick={()=>removeAttachment(id)} disabled={busy}>×</button></div>{/each}</div>{/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  {#if sources.length}
    <label>Saved source<select value={source?.source_id ?? ''} onchange={event => choose(event.currentTarget.value)}><option value="" disabled>Choose a source</option>{#each sources as item (item.source_id)}<option value={item.source_id}>{item.filename} · {item.record_count} records</option>{/each}</select></label>
  {/if}
  {#if source}
    <article class="source-summary"><h3>{source.filename}</h3><p>{source.record_count} records · {source.kind} · {source.status.replaceAll('_', ' ')}</p><a href={'/api/workspace/sources/' + source.source_id + '/file'} download={source.filename}>{source.kind === 'collection' ? 'Download source snapshot' : 'Download original file'}</a>{#if source.audio_coverage}<p>{source.audio_coverage.segments} speech segments · {Math.round(source.audio_coverage.duration_seconds)} seconds</p><p class="fine">{source.audio_coverage.limitation}</p>{/if}{#if source.image_coverage}<p>{source.image_coverage.text_regions} readable text regions</p><p class="fine">{source.image_coverage.limitation}</p>{/if}{#if source.email_coverage}<p>{source.email_coverage.messages} messages · {source.email_coverage.attachments} attachments listed</p><p class="fine">{source.email_coverage.limitation}</p>{/if}<details><summary>Source integrity</summary><p class="fine">SHA256 {source.sha256}</p></details>{#if source.extraction_coverage}<p>{source.extraction_coverage.pages_with_text} of {source.extraction_coverage.page_count} pages contain extracted text · {source.extraction_coverage.ocr_pages.length} OCR pages</p><p class="fine">{source.extraction_coverage.limitation}</p>{#if source.extraction_coverage.unresolved_pages.length}<p class="error">Pages requiring review: {source.extraction_coverage.unresolved_pages.join(', ')}</p>{/if}{/if}{#if source.extraction_run_url}<a href={source.extraction_run_url} target="_blank" rel="noreferrer">Extraction evidence</a>{/if}</article>
    {#if source.status === 'extracted'}
      <p class="fine">Previewing the first {source.records.length} of {source.record_count} records. Source IDs and locations are retained. Review the source evidence here or ask Bonsai to propose a view.</p>
      <form id="source-request" class="generate" onsubmit={generate}><label class="review-option"><input type="checkbox" bind:checked={applyReviews} disabled={Boolean(runningJob) || busy}/> Apply saved human corrections to a new working copy</label><button type="submit" disabled={Boolean(runningJob) || busy || intent.trim().length < 10}>Understand these files</button><p class="fine">First, review what Bonsai found and how it proposes to organize the data. Nothing is rendered until you confirm the view.</p></form>
      {#if source.kind === 'audio'}<section aria-label="Audio evidence"><h3>Listen and check the transcript</h3><audio controls bind:this={audioPlayer} src={'/api/workspace/sources/'+source.source_id+'/file'}></audio><div class="transcript">{#each source.records as row (row.id)}<button aria-pressed={selectedRecord===row.id} onclick={()=>{selectedRecord=row.id;if(audioPlayer){audioPlayer.currentTime=Number(row.locator.start_seconds);void audioPlayer.play().catch(()=>{});}}}>{Number(row.locator.start_seconds).toFixed(1)}s · {String(row.data.text)}</button>{/each}</div></section>{:else if source.kind === 'image'}<WorkspaceImageEvidence {source} bind:selected={selectedRecord}/>{:else}<div class="records">{#each source.records.slice(0, 10) as row (row.id)}<details><summary>{JSON.stringify(row.locator)}</summary><pre>{JSON.stringify(row.data, null, 2)}</pre></details>{/each}</div>{/if}
      {#key source.source_id+selectedRecord}<WorkspaceRecordReview {source} initialRecordId={selectedRecord} onSaved={() => source ? choose(source.source_id) : Promise.resolve()}/>{/key}
    {:else if source.kind === 'document' || source.kind === 'image' || source.kind === 'audio'}<p class="error" role="alert">{source.extraction_error ?? 'This file has not been extracted yet.'}</p><button onclick={extractMedia} disabled={busy}>{busy ? 'Extracting…' : 'Extract text'}</button>
    {:else}<p>Original media is saved. Extracted records and review will appear once the media workflow is connected.</p>{/if}
  {/if}
  {#if conversationJobs.length}<section class="jobs" aria-label="Visualization jobs"><h3>Your conversation with Bonsai</h3>{#each conversationJobs.slice(0,1) as job (job.id)}<article><strong>{job.filename}</strong><p>{job.request}</p><p role="status">{job.stage} · {job.status}</p>{#if job.status === 'awaiting_confirmation' && job.proposal}<WorkspaceProposal proposal={job.proposal} coverage={job.source_coverage} evidence={job.source_examples} busy={busy || Boolean(runningJob)} onConfirm={()=>respondToProposal(job)} onRevise={(feedback)=>respondToProposal(job,feedback)}/>{/if}{#if job.error}<p class="error">{job.error}</p>{/if}{#if ['queued','running'].includes(job.status)}<button onclick={()=>cancel(job.id)}>Cancel generation</button>{/if}{#if job.workspace_id}<button onclick={()=>onProject(job.workspace_id!)}>{job.status === 'completed' ? 'Open editable project' : 'Inspect saved project'}</button>{/if}{#if job.mlflow_url}<a href={job.mlflow_url} target="_blank" rel="noreferrer">MLflow evidence</a>{/if}</article>{/each}{#if conversationJobs.length > 1}<details><summary>Earlier proposals and attempts ({conversationJobs.length - 1})</summary>{#each conversationJobs.slice(1) as old (old.id)}<p>{old.filename} · {old.stage} · {old.status}{#if old.mlflow_url} <a href={old.mlflow_url} target="_blank" rel="noreferrer">Evidence</a>{/if}</p>{/each}</details>{/if}</section>{/if}
</section>

<style>
  audio{width:100%;margin:12px 0}.transcript{display:grid;gap:8px;margin-bottom:18px}.transcript button{text-align:left;background:var(--background);color:inherit;line-height:1.6}.transcript button[aria-pressed=true]{border-color:#94702e;background:#94702e12}
  .attachments{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}.attachments>div{display:flex;max-width:100%;border:1px solid var(--border);border-radius:8px;overflow:hidden}.attachments button{background:var(--background);color:inherit;border:0;border-radius:0}.attachment{overflow-wrap:anywhere;text-align:left}.remove{font-size:18px;padding:8px}.error{white-space:pre-wrap}

  .generate{border-top:1px solid var(--border);padding-top:20px;margin-top:20px}textarea{display:block;width:100%;box-sizing:border-box;min-height:95px;margin:10px 0;padding:12px;border:1px solid var(--border);border-radius:8px;background:var(--background);color:inherit;font:inherit;resize:vertical}.review-option{display:flex;gap:8px;font-size:11px;line-height:1.6;margin:12px 0}button{border:1px solid var(--border);border-radius:8px;padding:10px 14px;background:var(--primary);color:var(--primary-foreground);cursor:pointer}button:disabled{opacity:.5;cursor:default}.jobs article{border:1px solid var(--border);padding:14px;border-radius:10px;margin-top:12px;overflow-wrap:anywhere}.jobs a{display:inline-block;margin:10px}.jobs p{font-size:12px}

  .data{padding:24px;overflow:auto;min-width:0;height:100%;font-size:13px}.data h2{font-size:20px;margin:0 0 10px}.data p{line-height:1.6}.fine{color:var(--muted-foreground);font-size:11px;overflow-wrap:anywhere}.upload{display:block;padding:16px;border:1px dashed var(--border);border-radius:10px;margin:18px 0}.upload input{display:block;margin-top:10px;max-width:100%}label{display:block}select{display:block;max-width:100%;width:100%;padding:10px;margin:8px 0;background:var(--background);border:1px solid var(--border);border-radius:8px}.source-summary{padding:14px;border:1px solid var(--border);border-radius:10px;margin-top:18px}.source-summary h3{margin:0;font-size:14px}.records details{border-bottom:1px solid var(--border);padding:10px 0}.records pre{white-space:pre-wrap;overflow-wrap:anywhere}.error{color:#ac3434}a{text-decoration:underline}
</style>
