<script lang="ts">
  import type { SourceData, SourceSummary } from '$lib/workspace-data-types';
  import WorkspaceImageEvidence from '$lib/WorkspaceImageEvidence.svelte';
  import WorkspaceProposal from '$lib/WorkspaceProposal.svelte';
  import WorkspaceProposalReview from '$lib/WorkspaceProposalReview.svelte';
  import { onMount } from 'svelte';
  import WorkspaceRecordReview from '$lib/WorkspaceRecordReview.svelte';
  let { onProject = (_id: string) => {}, initialSource = '', initialIntake = '', role = 'Research analyst', panel = $bindable('conversation') } = $props<{onProject?: (id: string) => void; initialSource?:string; initialIntake?:string; role?:string; panel?:string}>();
  type Job = {planning_run_id?:string;kind?:string;run_id?:string;id:string; source_id:string; source_ids?:string[]; filename:string; request:string; status:string; stage:string; workspace_id?:string; error?:string; mlflow_url?:string; proposal?:any; proposal_sha256?:string; reply?:string; role?:string; parent_job_id?:string; source_coverage?:any; source_examples?:any[]};
  function sourceLocation(locator: Record<string, unknown>, index: number) {
    if (locator.sheet != null && locator.cell != null) return String(locator.sheet) + ' · ' + locator.cell;
    if (locator.body_block != null) return 'Document block ' + locator.body_block + (locator.table_row != null ? ' · table row ' + locator.table_row : ' · paragraph');
    if (locator.page != null) return 'Page ' + locator.page;
    if (locator.line != null) return 'Line ' + locator.line;
    if (locator.record != null) return 'Record ' + locator.record;
    if (locator.json_pointer != null) return 'JSON record ' + locator.json_pointer;
    return 'Record ' + (index + 1);
  }
  let jobs = $state<Job[]>([]);
  let intent = $state('');
  let messageInput: HTMLTextAreaElement | undefined = $state();
  function startWith(message:string) { intent=message; messageInput?.focus(); }
  function composeKey(event:KeyboardEvent) {
    if(event.key==='Enter' && (event.metaKey || event.ctrlKey) && !event.isComposing) {
      event.preventDefault(); messageInput?.form?.querySelector<HTMLButtonElement>('button[type=submit]')?.click();
    }
  }
  let intakeJobId = $state('');
  const intakeJob = $derived(jobs.find(job=>job.id===intakeJobId));
  const intakeHistory = $derived.by(()=>{
    const result:Job[]=[];let current=intakeJob;
    while(current && result.length<6){result.unshift(current);current=jobs.find(job=>job.id===current?.parent_job_id);}
    return result;
  });
  const completedIntakeId = $derived(intakeJob?.status==='completed' ? intakeJob.id : intakeJob?.parent_job_id ?? '');
  let draftReady = $state(false);
  let draftNotice = $state('Restoring draft…');
  let draftStorageKey = '';
  $effect(() => {
    if (!draftReady) return;
    const draft = {version:1, intent, intakeJobId, attached, sourceId:source?.source_id ?? '', applyReviews};
    try {
      localStorage.setItem(draftStorageKey, JSON.stringify(draft));
      draftNotice = intent || attached.length ? 'Draft saved in this browser.' : '';
    } catch {
      draftNotice = 'Draft could not be saved in this browser. Keep this page open.';
    }
  });
  function clearDraft() {
    intent=''; intakeJobId=''; attached=[]; source=null; applyReviews=false; error='';
  }
  let fileSearch = $state('');
  let selectedRecord = $state('');
  let videoPlayer: HTMLVideoElement | undefined = $state();
  let audioPlayer: HTMLAudioElement | undefined = $state();
  let applyReviews = $state(false);
  let attached = $state<string[]>([]);
  const runningJob = $derived(jobs.find(job => ['queued','running'].includes(job.status)));
  let sources = $state<SourceSummary[]>([]);
  const filteredSources = $derived(sources.filter(item => item.filename.toLowerCase().includes(fileSearch.toLowerCase())));

  let source = $state<SourceData | null>(null);
  const attachedSources = $derived(attached.map(id=>sources.find(item=>item.source_id===id)).filter((item):item is SourceSummary=>Boolean(item)));
  const pendingSources = $derived(attachedSources.filter(item=>item.status!=='extracted'));
  const attachmentsReady = $derived(attached.length===attachedSources.length && pendingSources.length===0);
  const effectiveIntent = $derived(intent.trim() || (source ? intakeJob?.request ?? '' : ''));

  const conversationJobs = $derived(jobs.filter(job => source && job.source_id === source.source_id));
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
  let draggingFiles = $state(false);
  let dragDepth = 0;
  function fileDrag(event:DragEvent) {
    if(!event.dataTransfer?.types.includes('Files'))return;
    event.preventDefault();
    if(event.type==='dragenter'){dragDepth++;draggingFiles=true;}
    if(event.dataTransfer)event.dataTransfer.dropEffect=busy ? 'none' : 'copy';
  }
  function leaveDrag(event:DragEvent) {
    if(!event.dataTransfer?.types.includes('Files'))return;
    dragDepth=Math.max(0,dragDepth-1);if(!dragDepth)draggingFiles=false;
  }
  async function dropFiles(event:DragEvent) {
    if(!event.dataTransfer?.types.includes('Files'))return;
    event.preventDefault();dragDepth=0;draggingFiles=false;
    if(busy)return;
    panel='conversation';
    await uploadFiles(Array.from(event.dataTransfer.files));
    messageInput?.focus();
  }
  async function upload(event: Event & {currentTarget: HTMLInputElement}) {
    const input=event.currentTarget;
    await uploadFiles(Array.from(input.files ?? []));
    input.value='';
  }
  async function uploadFiles(files:File[]) {
    if(busy)return;
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
  async function readVision() {
    if(!source)return;busy=true;error='';
    try {await request('/'+source.source_id+'/vision',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});jobs=(await jobRequest()).jobs;}
    catch(e){error=String(e);}finally{busy=false;}
  }
  async function jobRequest(path = '', body?: object) {
    const response = await fetch('/api/workspace/source-jobs' + path, body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {cache:'no-store'});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Job request failed');
    return result;
  }
  async function generate(event: SubmitEvent) {
    event.preventDefault(); if (runningJob || busy || !intent.trim() && !source || source && (!attachmentsReady || source.status!=='extracted' || effectiveIntent.length<10)) return;
    busy=true;error='';
    try {
      if(!source){
        const reply=await jobRequest('/intake',{role,message:intent,parent_job_id:completedIntakeId || null});
        intakeJobId=reply.id;intent='';panel='conversation';jobs=(await jobRequest()).jobs;return;
      }
      if(attached.length>1) { source=await request('/collection',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_ids:attached,apply_reviews:applyReviews})});await refresh(); }
      if(!source)return;
      await request('/'+source.source_id+'/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request:'Role: '+role+'\n\n'+effectiveIntent,apply_reviews:applyReviews,intake_job_id:completedIntakeId || null})});
      jobs=(await jobRequest()).jobs;
    } catch(e) { error=String(e); } finally { busy=false; }
  }
  async function respondToProposal(job:Job, feedback?:string) {
    busy=true;error='';
    try { await jobRequest('/'+job.id+(feedback === undefined ? '/confirm' : '/revise'),feedback === undefined ? {proposal_sha256:job.proposal_sha256} : {feedback});jobs=(await jobRequest()).jobs; }
    catch(e){error=String(e);}finally{busy=false;}
  }
  async function retryBuild(job:Job) {
    busy=true;error='';
    try {await jobRequest('/'+job.id+'/retry-build',{proposal_sha256:job.proposal_sha256});jobs=(await jobRequest()).jobs;}
    catch(e){error=String(e);}finally{busy=false;}
  }
  async function cancel(id:string) {
    try { await jobRequest('/'+id+'/cancel',{}); } catch(e) { error=String(e); }
  }
  onMount(() => {
    let stopped=false;let timer:ReturnType<typeof setTimeout>;
    draftStorageKey='bonsai-workstream-draft:v1:'+encodeURIComponent(role)+':'+(initialIntake || initialSource || 'new');
    async function restoreDraft() {
      busy=true;
      intakeJobId=initialIntake;
      try {
        const raw=localStorage.getItem(draftStorageKey);
        const saved=raw ? JSON.parse(raw) : null;
        if(saved?.version===1 && typeof saved.intent==='string' && Array.isArray(saved.attached)) {
          intent=saved.intent.slice(0,4000);
          if(typeof saved.intakeJobId==='string' && /^[a-f0-9]{32}$/.test(saved.intakeJobId))intakeJobId=saved.intakeJobId;
          attached=saved.attached.filter((id:unknown)=>typeof id==='string' && /^[a-f0-9]{64}$/.test(id)).slice(0,20);
          applyReviews=saved.applyReviews===true;
          if(typeof saved.sourceId==='string' && /^[a-f0-9]{64}$/.test(saved.sourceId)) {
            try { source=await request('/'+saved.sourceId); }
            catch { error='Your message is restored, but an attached source is unavailable. Remove it or attach the file again.'; }
          }
        } else if(initialSource) await choose(initialSource);
      } catch {
        error='The saved draft could not be restored. You can still attach files and write a new message.';
        if(initialSource) await choose(initialSource);
      } finally { if(!stopped) {busy=false;draftReady=true;} }
    }
    void restoreDraft();
    refresh().catch(e=>error=String(e));
    async function poll() {
      try { jobs=(await jobRequest()).jobs;
        const done=jobs.find(job=>job.kind==='vision_extraction' && job.status==='completed' && job.source_id===source?.source_id);
        if(done?.run_id && source?.extraction_run_id!==done.run_id) {await choose(done.source_id);await refresh();}
      } catch(e) { if(!stopped) error=String(e); }
      if(!stopped) timer=setTimeout(poll,1500);
    }
    void poll();return()=>{stopped=true;clearTimeout(timer);};
  });
</script>

<svelte:window ondragenter={fileDrag} ondragover={fileDrag} ondragleave={leaveDrag} ondrop={dropFiles} onblur={()=>{dragDepth=0;draggingFiles=false;}}/>

<section class="data" class:empty={!source} class:starting={panel==='conversation' && !intakeHistory.length && !conversationJobs.length} aria-label="Desktop sources">
  {#if draggingFiles}<div class="file-drop-overlay" role="status"><strong>{busy ? 'Finish the current upload first' : 'Drop files into this workstream'}</strong><span>Your message stays here. Review the evidence before building.</span></div>{/if}
  <nav class="intake-tabs" aria-label="Workstream sections">{#each [['conversation','Conversation'],['files','Files'],['activity','Activity']] as [key,label] (key)}<button class:active={panel===key} aria-pressed={panel===key} onclick={()=>panel=key}>{label}{key==='files' && attached.length ? ' · '+attached.length : ''}</button>{/each}</nav>
  <div class="conversation-intro" hidden={panel!=='conversation' || intakeHistory.length>0 || conversationJobs.length>0}><p class="role-label">{role}</p><h2>What would you like to understand?</h2><p class="welcome-message">Start with a question or attach your files. Together, we’ll make sense of the evidence and choose what to build.</p><div class="conversation-starters" aria-label="Ways to start"><button onclick={()=>startWith('Compare the evidence across these files and show where the sources agree or disagree.')}>Compare evidence</button><button onclick={()=>startWith('Organize these files into a timeline, preserving the source for every event.')}>Explore a timeline</button><button onclick={()=>startWith('Group related records and help me explore the patterns, with links back to the sources.')}>Find patterns</button></div></div>
  <div class="file-panel" hidden={panel!=='files'}><h2>Files for this workstream</h2><p class="fine">Inspect extracted records and original evidence here. The conversation stays in its own tab.</p>
  <details class="file-help"><summary>Supported files and extraction details</summary><p class="fine">Up to 20 files, 25 MiB each. Tables, text, email exports, and PDF pages are extracted locally. PDF pages without embedded text use OCR on this Mac. Images use local OCR. English audio uses local Whisper transcription. Bonsai can read image content and sampled video frames for review.</p></details>
  {#if attached.length}<div class="attachments" aria-label="Attached files">{#each attached as id (id)}{@const file=sources.find((item:SourceSummary)=>item.source_id===id)}<div><button class="attachment" onclick={()=>choose(id)} disabled={busy}>{file?.filename ?? 'Attached file'}</button><button class="remove" aria-label={'Remove '+(file?.filename ?? 'attached file')} onclick={()=>removeAttachment(id)} disabled={busy}>×</button></div>{/each}</div>{/if}
  {#if sources.length}
    <details class="saved-source" open><summary>Previously attached files</summary><label>Search attached files<input bind:value={fileSearch} placeholder="Search filenames" /></label><label>Saved source<select value={source?.source_id ?? ''} onchange={event => choose(event.currentTarget.value)}><option value="" disabled>Choose a source</option>{#each filteredSources as item (item.source_id)}<option value={item.source_id}>{item.filename} · {item.record_count} records</option>{/each}</select></label></details>
  {/if}
  {#if source}
    <article class="source-summary"><h3>{source.filename}</h3><p>{source.record_count} records · {source.kind} · {source.status.replaceAll('_', ' ')}</p><a href={'/api/workspace/sources/' + source.source_id + '/file'} download={source.filename}>{source.kind === 'collection' ? 'Download source snapshot' : 'Download original file'}</a>{#if source.workbook_coverage}<p>{source.workbook_coverage.cells} nonempty cells · {source.workbook_coverage.sheets.length} worksheets · {source.workbook_coverage.formulas} formulas</p><p class="fine">{source.workbook_coverage.formulas_without_cached_value} formulas have no saved result. {source.workbook_coverage.limitation}</p><details><summary>Workbook sheets</summary><ul>{#each source.workbook_coverage.sheets as sheet (sheet.name)}<li>{sheet.name} · {sheet.state} · {sheet.cells} cells</li>{/each}</ul></details>{/if}{#if source.document_coverage}<p>{source.document_coverage.scope}</p><p class="fine">{source.document_coverage.limitations} {source.document_coverage.embedded_media_not_read} embedded media files not read.</p>{/if}{#if source.vision_coverage}<p>{source.vision_coverage.samples} visual samples · {source.vision_coverage.records} extracted records</p><p class="fine">{source.vision_coverage.limitation}</p>{/if}{#if source.audio_coverage}<p>{source.audio_coverage.segments} speech segments · {Math.round(source.audio_coverage.duration_seconds)} seconds</p><p class="fine">{source.audio_coverage.limitation}</p>{/if}{#if source.image_coverage}<p>{source.image_coverage.text_regions} readable text regions</p><p class="fine">{source.image_coverage.limitation}</p>{/if}{#if source.email_coverage}<p>{source.email_coverage.messages} messages · {source.email_coverage.attachments} attachments listed</p><p class="fine">{source.email_coverage.limitation}</p>{/if}<details><summary>Source integrity</summary><p class="fine">SHA256 {source.sha256}</p></details>{#if source.extraction_coverage}<p>{source.extraction_coverage.pages_with_text} of {source.extraction_coverage.page_count} pages contain extracted text · {source.extraction_coverage.ocr_pages.length} OCR pages</p><p class="fine">{source.extraction_coverage.limitation}</p>{#if source.extraction_coverage.unresolved_pages.length}<p class="error">Pages requiring review: {source.extraction_coverage.unresolved_pages.join(', ')}</p>{/if}{/if}{#if source.evidence_error}<p class="error">Evidence export is unavailable. The original file and extraction result are saved locally.</p>{/if}{#if source.extraction_run_url}<a href={source.extraction_run_url} target="_blank" rel="noreferrer">Extraction evidence</a>{/if}</article>
    {#if ['image','video'].includes(source.kind)}<button onclick={readVision} disabled={busy || Boolean(runningJob)}>Read visual content with Bonsai</button><p class="fine">Extract visible tables and text. Video samples up to 20 frames across the clip. This pass does not read speech or unsampled motion.</p>{/if}
    {#if source.kind==='video'}<button onclick={extractMedia} disabled={busy || Boolean(runningJob) || Boolean(source.audio_coverage)}>{source.audio_coverage ? 'Speech transcribed' : 'Transcribe video speech'}</button><p class="fine">English speech uses Whisper on CPU. It is separate from Bonsai’s frame reading. Up to five minutes; no speaker identification.</p>{#if source.speech_extraction_error}<p class="error" role="alert">Speech: {source.speech_extraction_error}. Existing visual evidence is retained.</p>{/if}{#if source.visual_extraction_pending}<p class="fine">Speech is available. Visual frames have not been read yet.</p>{/if}{#if source.speech_extraction_run_url}<a href={source.speech_extraction_run_url} target="_blank" rel="noreferrer">Speech extraction evidence</a>{/if}{/if}
    {#if source.status === 'extracted'}
      <p class="fine">Previewing the first {source.records.length} of {source.record_count} records. Source IDs and locations are retained. Review the source evidence here or ask Bonsai to propose a view.</p>
      <details><summary>Use reviewed corrections</summary><label class="review-option"><input type="checkbox" bind:checked={applyReviews} disabled={Boolean(runningJob) || busy}/> Apply saved human corrections to a new working copy</label></details>
      {#if source.kind === 'audio'}<section aria-label="Audio evidence"><h3>Listen and check the transcript</h3><audio controls bind:this={audioPlayer} src={'/api/workspace/sources/'+source.source_id+'/file'}></audio><div class="transcript">{#each source.records as row (row.id)}<button aria-pressed={selectedRecord===row.id} onclick={()=>{selectedRecord=row.id;if(audioPlayer){audioPlayer.currentTime=Number(row.locator.start_seconds);void audioPlayer.play().catch(()=>{});}}}>{Number(row.locator.start_seconds).toFixed(1)}s · {String(row.data.text)}</button>{/each}</div></section>{:else if source.kind === 'video'}<section aria-label="Video evidence"><h3>Check the sampled frames</h3><p>Frame observations and speech segments are separate evidence. Select a record to inspect its timestamp in the original video.</p><!-- Source video is unmodified; this workflow extracts visual samples, not a caption track. --><!-- svelte-ignore a11y_media_has_caption --><video controls muted playsinline bind:this={videoPlayer} src={'/api/workspace/sources/'+source.source_id+'/file'}></video><div class="transcript">{#each source.records as row (row.id)}<button aria-pressed={selectedRecord===row.id} onclick={()=>{selectedRecord=row.id;if(videoPlayer)videoPlayer.currentTime=Number(row.locator.time_seconds ?? row.locator.start_seconds);}}>{row.locator.evidence_channel==='speech' ? 'Speech' : 'Frame'} · {Number(row.locator.time_seconds ?? row.locator.start_seconds).toFixed(1)}s · {Object.entries(row.data).map(([key,value])=>key+': '+String(value)).join(' · ')}</button>{/each}</div></section>{:else if source.kind === 'image' && source.image_coverage}<WorkspaceImageEvidence {source} bind:selected={selectedRecord}/>{:else}<div class="records">{#each source.records.slice(0, 10) as row, index (row.id)}<details><summary>{sourceLocation(row.locator, index)}</summary><pre>{JSON.stringify(row.data, null, 2)}</pre><p class="fine">Source location: {JSON.stringify(row.locator)}</p></details>{/each}</div>{/if}
      {#key source.source_id+selectedRecord}<WorkspaceRecordReview {source} initialRecordId={selectedRecord} onSaved={() => source ? choose(source.source_id) : Promise.resolve()}/>{/key}
    {:else if ['document','image','audio','workbook','table','text','email'].includes(source.kind)}<p class="error" role="alert">{source.extraction_error ?? 'This file has not been extracted yet.'}</p><p class="fine">The original file is saved. Retry after fixing the extraction issue, or attach a corrected file.</p><button onclick={extractMedia} disabled={busy}>{busy ? 'Extracting…' : source.status === 'extraction_failed' ? 'Retry extraction' : 'Extract text'}</button>
    {:else}<p>Original media is saved. Extracted records and review will appear once the media workflow is connected.</p>{/if}
  {/if}
  </div>
  <div class="conversation-thread" hidden={panel!=='conversation'}>
  {#if intakeHistory.length}<section class="intake-history" aria-label="Conversation before attachment">{#each intakeHistory as turn (turn.id)}<p class="intake-user">{turn.request}</p>{#if turn.reply}<p class="intake-reply">{turn.reply}</p>{:else}<p role="status">{turn.stage}</p>{/if}{#if turn.error}<p class="error" role="alert">{turn.error}</p>{/if}{#if ['queued','running'].includes(turn.status)}<button onclick={()=>cancel(turn.id)}>Stop reply</button>{/if}<details><summary>Reply evidence</summary><p>No source files were read in this reply.</p>{#if turn.mlflow_url}<a href={turn.mlflow_url} target="_blank" rel="noreferrer">View MLflow trace</a>{/if}</details>{/each}</section>{/if}
  {#if conversationJobs.length}<section class="jobs" aria-label="Visualization jobs"><h3>Your conversation with Bonsai</h3>{#each conversationJobs.slice(0,1) as job (job.id)}<article><strong>{job.filename}</strong><p>{job.request}</p><p role="status">{job.stage} · {job.status}</p>{#if job.proposal}<WorkspaceProposal readOnly={job.status !== 'awaiting_confirmation'} proposal={job.proposal} coverage={job.source_coverage} evidence={job.source_examples} busy={busy || Boolean(runningJob)} onConfirm={()=>respondToProposal(job)} onRevise={(feedback)=>respondToProposal(job,feedback)}/>{/if}{#if job.proposal}{#key job.id}<WorkspaceProposalReview jobId={job.id}/>{/key}{/if}{#if job.error}<p class="error">{job.error}</p>{/if}{#if ['queued','running'].includes(job.status)}<button onclick={()=>cancel(job.id)}>Cancel generation</button>{/if}{#if job.status==='failed' && job.planning_run_id && !job.workspace_id}<button onclick={()=>retryBuild(job)} disabled={busy || Boolean(runningJob)}>Retry confirmed build</button>{/if}{#if job.workspace_id}<button onclick={()=>onProject(job.workspace_id!)}>{job.status === 'completed' ? 'Open editable project' : 'Inspect saved project'}</button>{/if}{#if job.mlflow_url}<a href={job.mlflow_url} target="_blank" rel="noreferrer">MLflow evidence</a>{/if}</article>{/each}{#if conversationJobs.length > 1}<details><summary>Earlier proposals and attempts ({conversationJobs.length - 1})</summary>{#each conversationJobs.slice(1) as old (old.id)}<p>{old.filename} · {old.stage} · {old.status}{#if old.mlflow_url} <a href={old.mlflow_url} target="_blank" rel="noreferrer">Evidence</a>{/if}</p>{/each}</details>{/if}</section>{/if}
  </div>
  {#if panel==='activity'}<section class="runtime-panel"><h2>Runtime activity</h2>{#if busy}<p role="status">Processing your files…</p>{:else if runningJob}<p role="status">{runningJob.stage}</p>{:else}<p>No task is running.</p>{/if}{#each conversationJobs as job (job.id)}<article><strong>{job.stage}</strong><p>{job.status.replaceAll('_',' ')}</p>{#if job.error}<p class="error">{job.error}</p>{/if}{#if job.mlflow_url}<a href={job.mlflow_url} target="_blank" rel="noreferrer">View run evidence</a>{/if}</article>{/each}</section>{/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  {#if panel==='conversation' && attached.length && !conversationJobs.length}
    <section class="intake-receipt" aria-label="File intake summary">
      <strong>{busy ? 'Reading your files…' : attachmentsReady ? 'Your files are ready to discuss' : 'Some files need attention'}</strong>
      <p>{attachedSources.reduce((total,item)=>total+item.record_count,0)} extracted records across {attached.length} {attached.length===1 ? 'file' : 'files'}. Bonsai will use your question to propose a structure and a view for you to review.</p>
      {#if pendingSources.length}<ul>{#each pendingSources as item (item.source_id)}<li><button type="button" onclick={()=>{void choose(item.source_id);panel='files';}}>{item.filename}: {item.status.replaceAll('_',' ')} · Inspect</button></li>{/each}</ul>{/if}
      <details><summary>What was read</summary>{#each attachedSources as item (item.source_id)}<p><strong>{item.filename}</strong> · {item.record_count} records{#if item.extraction_coverage} · Text from {item.extraction_coverage.pages_with_text} of {item.extraction_coverage.page_count} pages. {item.extraction_coverage.limitation}{:else if item.document_coverage} · {item.document_coverage.scope}. {item.document_coverage.limitations}{:else if item.vision_coverage} · {item.vision_coverage.limitation}{:else if item.audio_coverage} · {item.audio_coverage.limitation}{:else if item.image_coverage} · {item.image_coverage.limitation}{/if}</p>{/each}</details>
    </section>
  {/if}
  <form id="source-request" hidden={panel!=='conversation'} class="message-compose" onsubmit={generate}>
    {#if attached.length}<div class="composer-files">{#each attached as id (id)}{@const file=sources.find(item=>item.source_id===id)}<span>{file?.filename ?? 'Attached file'}{#if file}<small>{file.status==='extracted' ? file.record_count+' records' : file.status.replaceAll('_',' ')}</small>{/if}<button type="button" aria-label={'Remove '+(file?.filename ?? 'file')} onclick={()=>removeAttachment(id)} disabled={busy}>×</button></span>{/each}<button type="button" onclick={()=>panel='files'}>Inspect files</button></div>{/if}
    <label class="message-label" for="visualization-intent">Message {role}</label><textarea id="visualization-intent" bind:this={messageInput} onkeydown={composeKey} bind:value={intent} maxlength="4000" placeholder="Tell me what you want to understand…" disabled={busy}></textarea>
    <div class="composer-actions"><label class="attach-button">＋ Attach files<input type="file" multiple accept=".xlsx,.docx,.eml,.mbox,.csv,.tsv,.json,.jsonl,.txt,.md,.png,.jpg,.jpeg,.webp,.pdf,.wav,.mp3,.m4a,.mp4,.mov,.webm" onchange={upload} disabled={busy}/></label><button type="submit" class="send-message" disabled={Boolean(runningJob) || busy || (!source ? !intent.trim() : !attachmentsReady || source.status!=='extracted' || effectiveIntent.length<10)}>Send ↑</button></div>
    <p class="composer-hint">{!draftReady ? 'Restoring draft…' : busy ? source ? 'Reading your files…' : 'Sending your message…' : !source ? 'Ask a question, attach files, or drop them here.' : !attachmentsReady || source.status!=='extracted' ? 'Some files need extraction. Open Files to inspect or retry.' : effectiveIntent.length<10 ? 'Describe what you want to understand (at least 10 characters).' : 'Bonsai will propose a view for your review.'}</p>
    <div class="draft-status"><span role="status">{draftNotice}</span>{#if intent || attached.length}<button type="button" onclick={clearDraft} disabled={busy || Boolean(runningJob)}>Clear draft</button>{/if}</div>
  </form>

</section>

<style>
  .draft-status{display:flex;align-items:center;justify-content:space-between;gap:12px;font-size:11px;color:var(--muted-foreground);margin-top:8px}.draft-status button{background:none;color:inherit;border:0;padding:4px;font-size:11px}
  video{display:block;width:100%;max-height:420px;background:#111;border-radius:8px}audio{width:100%;margin:12px 0}.transcript{display:grid;gap:8px;margin-bottom:18px}.transcript button{text-align:left;background:var(--background);color:inherit;line-height:1.6}.transcript button[aria-pressed=true]{border-color:#94702e;background:#94702e12}
  .attachments{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}.attachments>div{display:flex;max-width:100%;border:1px solid var(--border);border-radius:8px;overflow:hidden}.attachments button{background:var(--background);color:inherit;border:0;border-radius:0}.attachment{overflow-wrap:anywhere;text-align:left}.remove{font-size:18px;padding:8px}.error{white-space:pre-wrap}

  textarea{display:block;width:100%;box-sizing:border-box;min-height:95px;margin:10px 0;padding:12px;border:1px solid var(--border);border-radius:8px;background:var(--background);color:inherit;font:inherit;resize:vertical}.review-option{display:flex;gap:8px;font-size:11px;line-height:1.6;margin:12px 0}button{border:1px solid var(--border);border-radius:8px;padding:10px 14px;background:var(--primary);color:var(--primary-foreground);cursor:pointer}button:disabled{opacity:.5;cursor:default}.jobs article{border:1px solid var(--border);padding:14px;border-radius:10px;margin-top:12px;overflow-wrap:anywhere}.jobs a{display:inline-block;margin:10px}.jobs p{font-size:12px}

  .data{padding:24px;overflow:auto;min-width:0;height:100%;font-size:13px}.data h2{font-size:20px;margin:0 0 10px}.data p{line-height:1.6}.fine{color:var(--muted-foreground);font-size:11px;overflow-wrap:anywhere}label{display:block}select{display:block;max-width:100%;width:100%;padding:10px;margin:8px 0;background:var(--background);border:1px solid var(--border);border-radius:8px}.source-summary{padding:14px;border:1px solid var(--border);border-radius:10px;margin-top:18px}.source-summary h3{margin:0;font-size:14px}.records summary{overflow-wrap:anywhere}.records details{border-bottom:1px solid var(--border);padding:10px 0}.records pre{white-space:pre-wrap;overflow-wrap:anywhere}.error{color:#ac3434}a{text-decoration:underline}
.welcome-message{max-width:440px;padding:16px 20px;border-radius:18px 18px 18px 4px;background:var(--muted);line-height:1.7;margin:20px 0 32px}.file-help{font-size:11px;margin:12px 0}.data{max-width:760px;margin:0 auto;padding:28px}textarea{border-radius:18px}h2{font-size:20px}
.data.empty{min-height:calc(100dvh - 90px);box-sizing:border-box;display:flex;flex-direction:column}.empty .message-compose{margin-top:auto}.message-compose{border:1px solid var(--border);border-radius:20px;padding:12px 16px;margin-top:20px}.message-compose textarea{border:0;background:transparent;margin:5px 0;min-height:70px;padding:8px 0;resize:vertical}.saved-source{font-size:11px;margin:10px 0}.saved-source label{display:block;margin-top:10px}@media(max-width:750px){.data.empty{min-height:500px}.data{padding:20px}}

  .data,.data.empty{max-width:900px;width:100%;min-height:0;box-sizing:border-box;margin:0 auto;padding:0 28px 24px;display:flex;flex-direction:column}.intake-tabs{display:flex;gap:20px;border-bottom:1px solid var(--border);margin:0 -28px 24px;padding:0 28px}.intake-tabs button{border:0;border-radius:0;background:none;padding:16px 2px;color:var(--muted-foreground)}.intake-tabs button.active{color:var(--foreground);border-bottom:2px solid var(--foreground)}.conversation-intro{padding:12px 0}.role-label{font-size:11px;color:var(--muted-foreground)}.welcome-message{background:none;padding:0;max-width:480px;margin:12px 0 24px}.message-compose,.empty .message-compose{margin:24px 0 0;background:var(--card);border-radius:16px;box-shadow:0 4px 18px #00000006;padding:16px}.message-label{font-size:12px}.message-compose textarea{min-height:95px;max-height:200px;box-sizing:border-box;width:100%}.composer-actions{display:flex;align-items:center;justify-content:space-between;gap:12px}.attach-button{cursor:pointer;font-size:12px;border:1px solid var(--border);border-radius:8px;padding:8px 12px}.attach-button:focus-within{outline:2px solid var(--ring)}.attach-button input{position:absolute;width:1px;height:1px;opacity:0}.send-message{background:var(--primary);color:var(--primary-foreground);border-radius:9px;padding:10px 18px}.composer-hint{font-size:11px;line-height:1.6;color:var(--muted-foreground);margin:12px 0 0}.composer-files{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}.composer-files span{font-size:11px;background:var(--muted);border-radius:6px;padding:4px 8px;overflow-wrap:anywhere}.composer-files button{padding:3px 6px;font-size:11px}.runtime-panel article{padding:12px 0;border-bottom:1px solid var(--border)}[hidden]{display:none!important}@media(max-width:750px){.data,.data.empty{padding:0 16px 20px;min-height:0}.intake-tabs{margin:0 -16px 16px;padding:0 16px}}

.conversation-intro{padding:30px 0 16px}.role-label{letter-spacing:.03em}.welcome-message{background:var(--muted);padding:18px 20px;border-radius:18px 18px 18px 4px;max-width:520px;margin:18px 0;line-height:1.8}.conversation-starters{display:flex;flex-wrap:wrap;gap:8px}.conversation-starters button{background:transparent;color:var(--foreground);font-size:12px;padding:9px 12px;border-radius:20px}.message-compose,.empty .message-compose{margin-top:auto;position:sticky;bottom:0;flex-shrink:0;box-shadow:0 -12px 24px var(--background)}.conversation-intro{margin-bottom:28px}.message-compose textarea{min-height:70px}.intake-tabs{position:sticky;top:0;z-index:2;background:var(--background);flex-shrink:0}.file-panel,.runtime-panel{padding-bottom:24px}button:focus-visible,textarea:focus-visible{outline:2px solid var(--ring);outline-offset:3px}
@media(max-width:750px){.conversation-intro{padding-top:10px}.message-compose,.empty .message-compose{position:static;margin-top:20px}.conversation-starters{gap:6px}.conversation-starters button{font-size:11px}.data,.data.empty{height:auto;min-height:480px}}

.intake-history{padding-bottom:24px}.intake-history p{white-space:pre-wrap;overflow-wrap:anywhere;padding:14px 18px;line-height:1.7}.intake-user{margin-left:15%;background:var(--primary);color:var(--primary-foreground);border-radius:18px 18px 4px 18px}.intake-reply{margin-right:8%;background:var(--muted);border-radius:18px 18px 18px 4px}.intake-history details{font-size:11px;color:var(--muted-foreground);margin:12px 0 24px}

.data,.data.empty{overflow:hidden}.conversation-intro{flex-shrink:0}.conversation-thread,.file-panel,.runtime-panel{flex:1;min-height:0;overflow:auto}.message-compose,.empty .message-compose{position:relative;bottom:auto;box-shadow:none;margin-top:16px}.conversation-thread{padding-right:8px}.intake-history{padding-bottom:0}
@media(max-width:750px){.data,.data.empty{overflow:visible}.conversation-thread,.file-panel,.runtime-panel{overflow:visible;flex:auto}.conversation-thread{padding-right:0}}

/* Keep the first action next to its explanation, then make room for the conversation. */
.data.starting{max-width:820px}.starting .conversation-intro{padding-top:clamp(24px,8vh,88px);margin-bottom:8px}.starting .conversation-thread{flex:0;padding:0}.starting .message-compose{margin-top:20px}.starting .welcome-message{background:transparent;padding:0;max-width:560px;font-size:15px;line-height:1.7}.starting h2{font-size:28px;line-height:1.25;letter-spacing:-.6px}.starting .message-compose textarea{min-height:100px;font-size:15px;line-height:1.6}.role-label{font-weight:600}.message-compose:focus-within{border-color:var(--ring)}
@media(max-width:750px){.starting .conversation-intro{padding-top:20px;margin-bottom:0}.starting h2{font-size:24px}.starting .welcome-message{font-size:14px}.starting .message-compose{margin-top:16px}.starting .message-compose textarea{min-height:80px}}
.file-drop-overlay{position:fixed;inset:12px;z-index:1000;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;background:var(--card);border:2px dashed var(--ring);border-radius:20px;pointer-events:none;padding:24px;text-align:center}.file-drop-overlay strong{font-size:24px}.file-drop-overlay span{font-size:14px}.composer-files small{display:inline-block;margin-left:8px;color:var(--muted-foreground)}
.intake-receipt{flex-shrink:0;border-left:3px solid var(--ring);padding:12px 16px;margin:12px 0;font-size:12px;max-height:210px;overflow:auto}.intake-receipt p{margin:7px 0;overflow-wrap:anywhere}.intake-receipt summary{cursor:pointer;color:var(--muted-foreground)}.intake-receipt button{background:transparent;color:inherit;text-align:left;padding:6px}.intake-receipt ul{padding-left:16px}
</style>
