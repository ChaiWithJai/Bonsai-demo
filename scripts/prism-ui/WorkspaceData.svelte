<script lang="ts">
  import type { SourceData, SourceSummary } from '$lib/workspace-data-types';
  import { onMount } from 'svelte';
  import WorkspaceRecordReview from '$lib/WorkspaceRecordReview.svelte';
  let { onProject = (_id: string) => {} } = $props<{onProject?: (id: string) => void}>();
  type Job = {id:string; source_id:string; filename:string; request:string; status:string; stage:string; workspace_id?:string; error?:string; mlflow_url?:string};
  let jobs = $state<Job[]>([]);
  let intent = $state('');
  let applyReviews = $state(false);
  const runningJob = $derived(jobs.find(job => ['queued','running'].includes(job.status)));
  let sources = $state<SourceSummary[]>([]);
  let source = $state<SourceData | null>(null);
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
    try { source = await request('/' + id); }
    catch (e) { error = String(e); }
  }
  async function upload(event: Event & {currentTarget: HTMLInputElement}) {
    const file = event.currentTarget.files?.[0];
    if (!file) return;
    busy = true; error = '';
    try {
      if (file.size > 25 * 1024 * 1024) throw new Error('Choose a file of at most 25 MiB');
      source = await request('', {method: 'POST', headers: {'Content-Type': 'application/octet-stream', 'X-Source-Filename': encodeURIComponent(file.name)}, body: file});
      await refresh();
    } catch (e) { error = String(e); }
    finally { busy = false; }
  }
  async function extractPDF() {
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
      await request('/'+source.source_id+'/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request:intent,apply_reviews:applyReviews})});
      jobs=(await jobRequest()).jobs;
    } catch(e) { error=String(e); } finally { busy=false; }
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
  <h2>Your source data</h2>
  <p>Keep the original file, inspect its records, and preserve corrections for the next model iteration.</p>
  <label class="upload">{busy ? 'Extracting source; PDFs may take a moment…' : 'Add a desktop file'}<input type="file" accept=".csv,.tsv,.json,.jsonl,.txt,.md,.png,.jpg,.jpeg,.webp,.pdf,.wav,.mp3,.m4a,.mp4,.mov,.webm" onchange={upload} disabled={busy}/></label>
  <p class="fine">Up to 25 MiB. Tables, text, and PDF pages are extracted locally. PDF pages without embedded text use OCR on this Mac. Image, audio, and video workflows are still being connected.</p>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  {#if sources.length}
    <label>Saved source<select value={source?.source_id ?? ''} onchange={event => choose(event.currentTarget.value)}><option value="" disabled>Choose a source</option>{#each sources as item (item.source_id)}<option value={item.source_id}>{item.filename} · {item.record_count} records</option>{/each}</select></label>
  {/if}
  {#if source}
    <article class="source-summary"><h3>{source.filename}</h3><p>{source.record_count} records · {source.kind} · {source.status.replaceAll('_', ' ')}</p><a href={'/api/workspace/sources/' + source.source_id + '/file'} download={source.filename}>Download original file</a><details><summary>Source integrity</summary><p class="fine">SHA256 {source.sha256}</p></details>{#if source.extraction_coverage}<p>{source.extraction_coverage.pages_with_text} of {source.extraction_coverage.page_count} pages contain extracted text · {source.extraction_coverage.ocr_pages.length} OCR pages</p><p class="fine">{source.extraction_coverage.limitation}</p>{#if source.extraction_coverage.unresolved_pages.length}<p class="error">Pages requiring review: {source.extraction_coverage.unresolved_pages.join(', ')}</p>{/if}{/if}{#if source.extraction_run_url}<a href={source.extraction_run_url} target="_blank" rel="noreferrer">Extraction evidence</a>{/if}</article>
    {#if source.status === 'extracted'}
      <p class="fine">Previewing the first {source.records.length} of {source.record_count} records. Source IDs and locations are retained. Create a saved visualization below, then edit it in Workspace.</p>
      <form class="generate" onsubmit={generate}><label for="visualization-intent">What should this visualization help you understand?</label><textarea id="visualization-intent" bind:value={intent} minlength="10" maxlength="4000" required placeholder="Explore groups, compare observations, or follow changes over time…" disabled={Boolean(runningJob) || busy}></textarea><label class="review-option"><input type="checkbox" bind:checked={applyReviews} disabled={Boolean(runningJob) || busy}/> Apply saved human corrections to a new working copy</label><button type="submit" disabled={Boolean(runningJob) || busy || intent.trim().length < 10}>Create visualization</button><p class="fine">Bonsai selects field types and a Semiotic view. A reusable Svelte layout becomes your saved, editable project.</p></form>
      <div class="records">{#each source.records.slice(0, 10) as row (row.id)}<details><summary>{JSON.stringify(row.locator)}</summary><pre>{JSON.stringify(row.data, null, 2)}</pre></details>{/each}</div>
      {#key source.source_id}<WorkspaceRecordReview {source} onSaved={() => source ? choose(source.source_id) : Promise.resolve()}/>{/key}
    {:else if source.kind === 'document'}<p class="error" role="alert">{source.extraction_error ?? 'This PDF has not been extracted yet.'}</p><button onclick={extractPDF} disabled={busy}>{busy ? 'Extracting PDF pages…' : 'Extract PDF pages'}</button>
    {:else}<p>Original media is saved. Extracted records and review will appear once the media workflow is connected.</p>{/if}
  {/if}
  {#if jobs.length}<section class="jobs" aria-label="Visualization jobs"><h3>Visualizations</h3>{#each jobs as job (job.id)}<article><strong>{job.filename}</strong><p>{job.request}</p><p role="status">{job.stage} · {job.status}</p>{#if job.error}<p class="error">{job.error}</p>{/if}{#if ['queued','running'].includes(job.status)}<button onclick={()=>cancel(job.id)}>Cancel generation</button>{/if}{#if job.workspace_id}<button onclick={()=>onProject(job.workspace_id!)}>{job.status === 'completed' ? 'Open editable project' : 'Inspect saved project'}</button>{/if}{#if job.mlflow_url}<a href={job.mlflow_url} target="_blank" rel="noreferrer">MLflow evidence</a>{/if}</article>{/each}</section>{/if}
</section>

<style>
  .generate{border-top:1px solid var(--border);padding-top:20px;margin-top:20px}textarea{display:block;width:100%;box-sizing:border-box;min-height:95px;margin:10px 0;padding:12px;border:1px solid var(--border);border-radius:8px;background:var(--background);color:inherit;font:inherit;resize:vertical}.review-option{display:flex;gap:8px;font-size:11px;line-height:1.6;margin:12px 0}button{border:1px solid var(--border);border-radius:8px;padding:10px 14px;background:var(--primary);color:var(--primary-foreground);cursor:pointer}button:disabled{opacity:.5;cursor:default}.jobs article{border:1px solid var(--border);padding:14px;border-radius:10px;margin-top:12px;overflow-wrap:anywhere}.jobs a{display:inline-block;margin:10px}.jobs p{font-size:12px}

  .data{padding:24px;overflow:auto;min-width:0;height:100%;font-size:13px}.data h2{font-size:20px;margin:0 0 10px}.data p{line-height:1.6}.fine{color:var(--muted-foreground);font-size:11px;overflow-wrap:anywhere}.upload{display:block;padding:16px;border:1px dashed var(--border);border-radius:10px;margin:18px 0}.upload input{display:block;margin-top:10px;max-width:100%}label{display:block}select{display:block;max-width:100%;width:100%;padding:10px;margin:8px 0;background:var(--background);border:1px solid var(--border);border-radius:8px}.source-summary{padding:14px;border:1px solid var(--border);border-radius:10px;margin-top:18px}.source-summary h3{margin:0;font-size:14px}.records details{border-bottom:1px solid var(--border);padding:10px 0}.records pre{white-space:pre-wrap;overflow-wrap:anywhere}.error{color:#ac3434}a{text-decoration:underline}
</style>
