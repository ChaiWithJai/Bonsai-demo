<script lang="ts">
  import { onMount } from 'svelte';
  import { ArrowUpRight, ArrowRightLeft, Play, RefreshCw, CircleAlert, Cpu, Timer, Activity, Globe, Link, Pause } from '@lucide/svelte';
  import MarkdownContent from '$lib/components/app/content/MarkdownContent/MarkdownContent.svelte';
  type Data = Record<string, any>;
  let status = $state<Data | null>(null);
  const grantPrompt = 'Find funding for a community data center that expands access to AI. Research current public sources with the browser. Verify the funder, program, purpose, eligibility, deadline or application status, and next action from source pages. Explain what is a potential fit and what remains unconfirmed. Unknown applicant details should lead to conditional findings, not invented eligibility. Do not submit an application or contact anyone.';
  const defaultContext = 'Project: A community data center providing accessible AI compute and education so communities can benefit from AI.\nLocation / jurisdiction: Unknown.\nApplicant entity and legal status: Unknown.\nBudget and requested funding: Unknown.\nCurrent stage, partners, and timeline: Unknown.\nTreat these unknowns as open questions; exploratory grant research can proceed.';
  let task = $state('grant_research');
  let projectContext = $state(defaultContext);
  let prompt = $state(grantPrompt);
  let mode = $state('sequential');
  let thinking = $state(false);
  let temperature = $state(0.3);
  let tokenLimit = $state(512);
  let thinkingLimit = $state(128);
  let cancellationRequested = $state(false);
  let requestController: AbortController | null = null;
  let receivedRunFinished = false;
  let loading = $state(true);
  let running = $state(false);
  let error = $state('');
  let run = $state<Data | null>(null);
  let outputs = $state<Record<string, Data>>({});
  let browserViews = $state<Record<string, Data>>({});
  let pausedViews = $state<Record<string, boolean>>({});
  const browserTargets = $derived(running ? JSON.stringify(Object.entries(outputs).filter(([id, result]) => result.browser_session && result.status === 'running' && !pausedViews[id]).map(([id, result]) => [id, result.browser_session])) : '[]');
  function browserImage(view: Data | undefined) { const value = view?.image_data_url; return typeof value === 'string' && /^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(value) ? value : ''; }
  $effect(() => {
    const targets: string[][] = JSON.parse(browserTargets);
    if (!targets.length) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function poll() {
      await Promise.all(targets.map(async ([id, session]) => {
        try {
          const response = await fetch(`/api/browser-view/${encodeURIComponent(session)}`, {cache: 'no-store', signal: controller.signal});
          if (!response.ok) throw new Error(`Browser view unavailable (${response.status})`);
          const value = await response.json();
          if (!cancelled) browserViews[id] = value;
        } catch (error) { if (!cancelled) browserViews[id] = {error: String(error)}; }
      }));
      if (!cancelled) timer = setTimeout(poll, 2000);
    }
    void poll();
    return () => {cancelled = true; controller.abort(); clearTimeout(timer);};
  });

  const ready = $derived((status?.models?.length ?? 0) >= 2 && (status?.models || []).every((model: Data) => model.available) && !status?.busy);
  function pretty(value: unknown) { return value == null ? 'Not captured' : JSON.stringify(value, null, 2); }
  function metric(value: any, unit = '') { return typeof value === 'number' && Number.isFinite(value) ? `${value.toLocaleString(undefined, {maximumFractionDigits: 2})}${unit}` : 'Not captured'; }
  function seconds(value: any) { return typeof value === 'number' ? metric(value / 1000, ' s') : 'Not captured'; }
  function lastTiming(value: any) { return Array.isArray(value) ? value.at(-1) || {} : value || {}; }
  function safeLink(value: unknown) { if (typeof value !== 'string') return undefined; try {const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) ? value : undefined;} catch {return undefined;} }
  function restore(saved: Data) {
    run = saved;
    outputs = Object.fromEntries((saved.results || []).map((result: Data) => [result.model, result]));
    prompt = saved.settings?.prompt ?? prompt;
    task = saved.settings?.task || saved.task || 'text';
    projectContext = saved.settings?.project_context || '';
    mode = saved.mode || saved.settings?.mode || 'sequential';
    temperature = saved.settings?.temperature ?? 0.3;
    tokenLimit = saved.settings?.max_tokens ?? 512;
    thinking = (saved.settings?.thinking_budget_tokens ?? 0) > 0;
    thinkingLimit = saved.settings?.thinking_budget_tokens > 0 ? saved.settings.thinking_budget_tokens : 128;
    cancellationRequested = false; error = '';
  }
  function newResearch() { task = 'grant_research'; projectContext = defaultContext; prompt = grantPrompt; run = null; outputs = {}; browserViews = {}; pausedViews = {}; error = ''; mode = 'sequential'; temperature = 0.3; tokenLimit = 512; thinking = false; cancellationRequested = false; }
  function timeline(result: Data | undefined) {return result?.live_timeline || result?.steps || [];}
  function observedTime(value: unknown) { const parsed = new Date(typeof value === 'number' ? value * 1000 : String(value)); return Number.isNaN(parsed.getTime()) ? 'Observation time unavailable' : parsed.toLocaleString(); }
  function completedInference(entries: Data[]) { return entries.map((entry: Data) => entry.kind === 'step' && entry.status === 'running' ? {...entry, status: 'completed'} : entry); }
  function finishedResult(previous: Data | undefined, result: Data) { return {...previous, ...result, ...(Array.isArray(result.steps) ? {live_timeline: result.steps.map((step: Data) => ({...step, kind: step.tool_call_id ? 'tool' : 'step'}))} : {})}; }

  function sources(result: Data | undefined): Data[] {return result?.sources || [];}
  function evidenceLabel(value: unknown) { return value === 'search_discovery_only' ? 'Search leads only—program pages not verified' : value === 'opened_sources_require_eligibility_review' ? 'Source pages read—eligibility still needs review' : value === 'no_sources' ? 'No sources read' : 'Evidence status not yet recorded'; }

  function restoreId(id: string) {const saved = status?.recent_runs?.find((item: Data) => item.run_id === id); if (saved) restore(saved);}
  function cancel() { cancellationRequested = true; if (run) run = {...run, status: 'cancellation_requested'}; requestController?.abort(); }
  async function refresh() {
    loading = true; error = '';
    try {
      const response = await fetch('/api/comparison/status');
      if (!response.ok) throw new Error(`Status service returned ${response.status}`);
      status = await response.json();
      const saved = status?.recent_runs?.find((item: Data) => item.run_id === run?.run_id);
      if (saved && !running) restore(saved);
      if (!status?.busy && !running) cancellationRequested = false;
    }
    catch (e) { error = String(e); }
    finally { loading = false; }
  }
  function event(name: string, data: Data) {
    if (name === 'run_started') run = {...data, status: 'running'};
    else if (name === 'model_started') outputs[data.model] = {...outputs[data.model], ...data, status: 'running', content: '', reasoning_content: ''};
    else if (name === 'delta') {
      const previous = outputs[data.model] || {status: 'running', content: '', reasoning_content: ''};
      outputs[data.model] = {...previous, content: previous.content + (data.content || ''), reasoning_content: previous.reasoning_content + (data.reasoning_content || '')};
    } else if (name === 'step') {
      const previous = outputs[data.model] || {};
      outputs[data.model] = {...previous, phase: data.phase, turn: data.turn, content: '', reasoning_content: '', live_timeline: [...completedInference(previous.live_timeline || []), {...data, kind: 'step'}]};
    } else if (name === 'tool_started' || name === 'tool_finished') {
      const previous = outputs[data.model] || {};
      const entries = completedInference(previous.live_timeline || []);
      const index = entries.findIndex((item: Data) => item.kind === 'tool' && item.tool_call_id === data.tool_call_id);
      const entry = {...(index >= 0 ? entries[index] : {}), ...data, kind: 'tool', status: data.status || 'running'};
      if (index >= 0) entries[index] = entry; else entries.push(entry);
      const found = [...(previous.sources || [])];
      if (data.source?.url && !found.some((source: Data) => source.url === data.source.url)) found.push(data.source);
      outputs[data.model] = {...previous, live_timeline: entries, sources: found};
    } else if (name === 'model_finished') outputs[data.model] = finishedResult(outputs[data.model], data);
    else if (name === 'run_finished') {
      receivedRunFinished = true;
      run = {...run, ...data};
      for (const result of data.results || []) if (result.model) outputs[result.model] = finishedResult(outputs[result.model], result);
    } else if (name === 'error') throw new Error(data.error || data.message || 'Comparison failed');
  }
  function frame(text: string) {
    let name = 'message'; const lines: string[] = [];
    for (const line of text.split(/\r?\n/)) {
      if (line.startsWith('event:')) name = line.slice(6).trim();
      else if (line.startsWith('data:')) lines.push(line.slice(5).trimStart());
    }
    if (lines.length) event(name, JSON.parse(lines.join('\n')));
  }
  async function start() {
    if (!ready || running || !prompt.trim()) return;
    running = true; error = ''; run = null; browserViews = {}; pausedViews = {}; cancellationRequested = false; receivedRunFinished = false; requestController = new AbortController();
    outputs = Object.fromEntries(status!.models.map((model: Data) => [model.id, {status: 'queued', content: '', reasoning_content: ''}]));
    try {
      const response = await fetch('/api/comparison/run', {method: 'POST', signal: requestController.signal, headers: {'Content-Type': 'application/json'}, body: JSON.stringify({task, project_context: projectContext.trim(), prompt: prompt.trim(), mode, temperature, max_tokens: Math.min(status?.limits?.max_tokens ?? 512, tokenLimit), thinking_budget_tokens: thinking ? Math.min(status?.limits?.thinking_budget_tokens ?? 128, thinkingLimit) : 0})});
      if (!response.ok) { const body = await response.text(); throw new Error(`Comparison returned ${response.status}: ${body.slice(0, 600)}`); }
      if (!response.body) throw new Error('Response stream is unavailable');
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = '';
      while (true) {
        const {value, done} = await reader.read();
        buffer += decoder.decode(value, {stream: !done});
        let boundary;
        while ((boundary = buffer.search(/\r?\n\r?\n/)) >= 0) {
          const separator = buffer.slice(boundary).match(/^\r?\n\r?\n/)![0];
          frame(buffer.slice(0, boundary)); buffer = buffer.slice(boundary + separator.length);
        }
        if (done) break;
      }
      if (buffer.trim()) frame(buffer);
      if (!receivedRunFinished) throw new Error('Stream ended without a recorded run_finished event. Completion is unverified.');
    } catch (e) {
      error = cancellationRequested ? 'Cancellation requested. The browser stream is closed; the server may still be stopping. Refresh status to retrieve the recorded outcome.' : String(e);
      for (const [id, result] of Object.entries(outputs)) if (['queued','running'].includes(result.status)) outputs[id] = {...result, status: 'interrupted', error: 'The UI stream did not complete. Check MLflow for the recorded server outcome.'};
    } finally { running = false; requestController = null; }
  }
  onMount(() => {void refresh();});
</script>

<svelte:head><title>Compare models · Prism ML</title></svelte:head>
<div class="comparison-page">
  <header><div><p class="eyebrow">PRISM ML / MODEL COMPARISON</p><h1>Find funding for a community data center that expands access to AI.</h1><p class="intro">Two models research the same project. Follow their browser work, sources, and recommendations.</p></div><button class="button" onclick={() => refresh()} disabled={loading || running}><RefreshCw size={15}/>{loading ? 'Checking…' : 'Refresh status'}</button></header>
  {#if error}<div class="notice" role="alert"><CircleAlert size={18}/><span>{error}</span></div>{/if}
  {#if status?.recent_runs?.length}<div class="recent-runs"><label for="comparison-history">Load a saved run</label><select id="comparison-history" value={run?.run_id || ''} disabled={running} onchange={(event) => restoreId(event.currentTarget.value)}><option value="" disabled>Select a recorded run</option>{#each status.recent_runs as saved}<option value={saved.run_id}>{saved.status} · {saved.mode} · {(saved.settings?.prompt || saved.run_id).slice(0,80)}</option>{/each}</select><button class="button" onclick={newResearch} disabled={running}>New grant research</button><span class="caption">Saved text comparisons remain available; loading one restores its original task.</span></div>{/if}
  <section class="prompt-card" aria-label="Shared comparison prompt">
    <div class="section-title"><span class="eyebrow">SHARED INPUT</span><span class="pill">{task === 'grant_research' ? 'Public browser research · draft findings only' : 'Saved text comparison · no browser tools'}</span></div>
    {#if task === 'grant_research'}
      <label class="prompt-label" for="project-context">Shared project context</label>
      <textarea id="project-context" bind:value={projectContext} disabled={running} rows="7" placeholder="Describe the project, location, applicant, and funding needs. Unknowns are welcome."></textarea>
      <p class="caption">Both models receive this same context and research independently. Location, applicant type, and budget can remain unknown; eligibility must then stay conditional.</p>
    {/if}
    <label class="prompt-label" for="comparison-prompt">{task === 'grant_research' ? 'Research brief sent to both models' : 'Original text prompt'}</label>
    <textarea id="comparison-prompt" bind:value={prompt} disabled={running} rows="5" placeholder="Enter one bounded task for both models…"></textarea>
    <div class="controls"><fieldset disabled={running}><legend>Execution mode</legend><label><input type="radio" name="comparison-mode" bind:group={mode} value="sequential"/> Sequential</label><label><input type="radio" name="comparison-mode" bind:group={mode} value="concurrent"/> Concurrent · shared hardware</label></fieldset><label class="thinking"><input type="checkbox" bind:checked={thinking} disabled={running}/> Enable bounded reasoning ({Math.min(status?.limits?.thinking_budget_tokens ?? 128,thinkingLimit)} tokens)</label></div>
    <p class="caption">{mode === 'concurrent' ? 'Both models run at once on shared hardware. Contention affects timings; this is a live contention experiment, not an isolated speed benchmark.' : 'Models run one after the other. This avoids overlapping these two requests; cache state, model format, and other machine activity can still affect timing.'}</p>
    <div class="run-controls"><span class="caption">Temperature {temperature} · Up to {Math.min(status?.limits?.max_tokens ?? 512,tokenLimit)} {task === 'grant_research' ? 'tokens per research turn; up to 1,024 final tokens · Up to 6 browser tool calls per model' : 'generated tokens · Same prompt and request settings'}</span><button class="button primary" onclick={start} disabled={!ready || running || cancellationRequested || !prompt.trim()}><Play size={15}/>{running ? 'Research running…' : task === 'grant_research' ? 'Find grants with both models' : 'Run text comparison'}</button>{#if running}<button class="button" onclick={cancel} disabled={cancellationRequested}>{cancellationRequested ? 'Cancellation requested…' : 'Cancel comparison'}</button>{/if}</div>
    {#if !ready && !loading}<p class="caption">{status?.busy ? 'A comparison is still active on the server. Refresh status after it finishes or stops.' : 'Both model endpoints must be available before a comparison can run. Endpoint status is shown below.'}</p>{/if}
  </section>
  {#if run}<section class="run-banner" aria-label="Comparison run"><span><Activity size={15}/>{run.status || 'running'} · {run.mode || mode}{run.contention ? ' · hardware contention' : ''}</span><code>{run.run_id}</code>{#if safeLink(run.mlflow_url)}<a href={safeLink(run.mlflow_url)} target="_blank" rel="noreferrer">Open run in MLflow <ArrowUpRight size={14}/></a>{/if}</section>{/if}
  <div class="model-grid">
    {#each status?.models || [] as model (model.id)}
      {@const result = outputs[model.id]}
      {@const timings = lastTiming(result?.timings)}
      <section class="model-card" aria-label={model.label || model.id}>
        <div class="model-heading"><div><p class="eyebrow">{model.id}</p><h2>{result?.identity?.label || model.label || model.id}</h2></div><span class="pill" class:unavailable={!model.available}>{result?.status || (model.available ? 'Ready' : 'Unavailable')}</span></div>
        <p class="caption model-id">{(result?.model_id || result?.identity?.model_id || model.model_id)?.split('/').at(-1) || 'Model identity not reported'}</p>
        <p class="caption">Quantization: <strong>{result?.identity?.quantization || model.quantization || model.identity?.quantization || 'Not reported'}</strong> · Different quantizations are part of this comparison.</p>
        {#if model.error}<div class="notice"><CircleAlert size={15}/><span>{model.error}</span></div>{/if}
        {#if result?.error}<div class="notice" role="alert"><CircleAlert size={15}/><span>{result.error}</span></div>{/if}
        {#if result?.independent_browser_session}<p class="caption"><Globe size={13}/> Independent browser session recorded for this model.</p>{/if}
        <div class="metrics"><div><Timer size={14}/><small>Exchange elapsed</small><strong>{seconds(result?.elapsed_ms)}</strong></div><div><Activity size={14}/><small>First output delta</small><strong>{seconds(result?.time_to_first_token_ms)}</strong></div><div><Cpu size={14}/><small>Generation rate</small><strong>{metric(timings.predicted_per_second,' tok/s')}</strong></div></div>
        <p class="caption">First output delta is client-observed and includes emitted reasoning when enabled; it is not physical token timing.</p>
        {#if task === 'grant_research' || result?.task === 'grant_research'}
          {#if result?.browser_session && running}
            <section class="research-browser" aria-label={`${model.label || model.id} live browser`}><div class="research-heading"><h3><Globe size={16}/> Agent browser view</h3><button class="button" onclick={() => pausedViews[model.id] = !pausedViews[model.id]}>{#if pausedViews[model.id]}<Play size={12}/> Resume{:else}<Pause size={12}/> Pause{/if}</button></div>
              {#if pausedViews[model.id]}<p class="caption">Live view paused.</p>{:else if browserViews[model.id]?.error}<p class="caption">{browserViews[model.id].error}</p>{:else if browserImage(browserViews[model.id])}<img src={browserImage(browserViews[model.id])} alt={`${model.label || model.id} current browser viewport`}/><p class="caption">{browserViews[model.id]?.title || ''} · {browserViews[model.id]?.url || ''}</p>{:else}<p class="caption">{browserViews[model.id]?.message || 'Waiting for this model’s browser page.'}</p>{/if}
              <p class="caption">Transient live snapshots every 2 seconds during research. This is not a historical replay.</p>
            </section>
          {/if}
          <section class="research-timeline" aria-label={`${model.label || model.id} browser research`}>
            <div class="research-heading"><h3><Globe size={16}/> Browser research</h3><span class="pill">{result?.tool_calls_count ?? timeline(result).filter((item: Data) => item.kind === 'tool').length} tool calls</span></div>
            {#if timeline(result).length}<ol>{#each timeline(result) as step, index}<li class:tool-error={step.status === 'error'}><span class="step-index">{index + 1}</span><div><strong>{step.name || step.message || (step.phase === 'final' ? 'Writing grounded findings' : 'Model research step')}</strong><small>Turn {step.turn ?? 'not captured'}{step.status ? ` · ${step.status}` : ''}</small>{#if safeLink(step.url)}<a href={safeLink(step.url)} target="_blank" rel="noreferrer">{step.url}<ArrowUpRight size={12}/></a>{/if}{#if step.error}<p>{step.error}</p>{/if}<details><summary>Recorded step details</summary><pre>{pretty(step)}</pre></details></div></li>{/each}</ol>{:else}<p class="caption">Browser actions will appear here as the model requests them. No actions have been recorded yet.</p>{/if}
          </section>
          <section class="research-sources" aria-label={`${model.label || model.id} observed sources`}><h3><Link size={15}/> Observed sources</h3>{#if result?.evidence_status || result?.eligibility_verified === false}<div class="source-status"><strong>{evidenceLabel(result?.evidence_status)}</strong>{#if result?.eligibility_verified === false}<p>Eligibility is not verified. Treat these findings as leads for review, not confirmed grant opportunities for this applicant.</p>{/if}</div>{/if}{#if result?.citation_audit}<p class="caption"><strong>Citation check: {result.citation_audit.status === 'passed' ? 'cited links match pages read' : 'needs review'}.</strong> This checks URL provenance, not whether every claim is supported.</p>{/if}{#if sources(result).length}<ul>{#each sources(result) as source}<li>{#if safeLink(source.url)}<a href={safeLink(source.url)} target="_blank" rel="noreferrer">{source.title || source.url}<ArrowUpRight size={12}/></a>{:else}<span>{source.url || 'URL not captured'}</span>{/if}<small>{source.observed_at ? `Observed ${observedTime(source.observed_at)}` : 'Observation time not captured'}</small></li>{/each}</ul>{:else}<p class="caption">No source observations captured yet.</p>{/if}<p class="caption">A visited page is evidence of retrieval, not proof that a grant is open or the project is eligible.</p></section>
          <h3 class="output-heading">{result?.phase === 'final' || !running && result?.content ? 'Grant findings' : 'Live working output'}</h3>
        {/if}
        {#if result?.reasoning_content}<details class="reasoning" open={running}><summary>Emitted reasoning</summary><p class="caption">Model-generated text; not an activation measurement.</p><pre>{result.reasoning_content}</pre></details>{/if}
        <div class="answer" aria-label={`${model.label || model.id} output`}>
          {#if result?.content}<MarkdownContent content={result.content}/>{:else}<p class="empty">{result?.status === 'running' ? 'Waiting for generated output…' : result?.status === 'queued' ? 'Queued for this run.' : 'The model’s live output will appear here.'}</p>{/if}
        </div>
        {#if result?.finish_reason}<p class="caption">Finish reason: <code>{result.finish_reason}</code>{result.finish_reason === 'length' ? ' · Output reached its token limit and may be incomplete.' : ''}</p>{/if}
        {#if safeLink(result?.trace_url)}<a class="trace-link" href={safeLink(result.trace_url)} target="_blank" rel="noreferrer">Inspect this inference in MLflow <ArrowUpRight size={14}/></a>{/if}
        <details class="evidence"><summary>Model identity and captured runtime evidence</summary><pre>{pretty({endpoint:model.endpoint,identity:result?.identity || model.identity,model_id:result?.model_id || model.model_id,timings:result?.timings,elapsed_ms:result?.elapsed_ms,time_to_first_token_ms:result?.time_to_first_token_ms,finish_reason:result?.finish_reason,trace_id:result?.trace_id,settings:run?.settings})}</pre></details>
        {#if result?.content}<details class="evidence"><summary>Raw output</summary><pre>{result.content}</pre></details>{/if}
      </section>
    {/each}
  </div>
  {#if loading && !status}<div class="empty" role="status">Checking model endpoints…</div>{/if}
  <div class="notice"><Activity size={18}/><span>Research records inference and browser exchanges, not internal activations. <a href="#/observability">Inspect the separate Bonsai activation diagnostic in Observability</a>; it does not explain either output in this comparison.</span></div>
  <footer><ArrowRightLeft size={18}/><div><strong>Compare evidence, then judge usefulness.</strong><p>No winner is inferred from speed alone. These runs are bounded demonstrations, not quality or equivalence benchmarks. Unavailable measurements are not reported as zero.</p>{#if status?.limitations?.length}<details><summary>Comparison boundaries</summary><ul>{#each status.limitations as limitation}<li>{limitation}</li>{/each}</ul></details>{/if}</div></footer>
</div>

<style>
  .comparison-page{max-width:1550px;margin:auto;padding:40px 36px 70px;height:100dvh;overflow:auto;background:radial-gradient(ellipse at 85% 0%,#b893891a,transparent 60%)}
  header{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;margin-bottom:28px}.eyebrow{font-family:var(--font-mono);font-size:10px;letter-spacing:.13em;color:var(--muted-foreground);margin:0 0 12px}h1{font-size:clamp(28px,3vw,42px);font-weight:600;letter-spacing:-.045em;line-height:1.12}.intro{font-size:14px;color:var(--muted-foreground);margin-top:12px}.button{display:inline-flex;align-items:center;justify-content:center;gap:8px;border:1px solid var(--border);border-radius:24px;background:var(--card);padding:10px 15px;font-size:12px;white-space:nowrap;cursor:pointer}.button:disabled{opacity:.5;cursor:default}.button.primary{background:var(--primary);color:var(--primary-foreground);border-color:var(--primary)}
  .recent-runs{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:18px}.recent-runs label{font-size:12px;font-weight:600}.recent-runs select{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:10px;max-width:100%;font-size:11px;min-width:200px}.recent-runs .caption{margin-top:0}
  .prompt-card,.model-card{border:1px solid var(--border);background:color-mix(in srgb,var(--card) 90%,transparent);border-radius:18px;padding:23px;box-shadow:0 8px 30px #262c3505}.section-title,.model-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:15px}.pill{background:var(--secondary);border-radius:25px;padding:6px 10px;font-size:10px;white-space:nowrap}.pill.unavailable{background:var(--muted);color:var(--muted-foreground)}.prompt-label{display:block;font-size:13px;font-weight:600;margin:10px 0}textarea{width:100%;padding:15px;border:1px solid var(--border);border-radius:12px;background:var(--background);font:inherit;font-size:13px;line-height:1.6;resize:vertical;min-height:115px}.controls{display:flex;align-items:flex-end;gap:25px;flex-wrap:wrap;margin-top:18px}fieldset{display:flex;gap:16px;flex-wrap:wrap}legend{font-size:10px;color:var(--muted-foreground);margin-bottom:9px}fieldset label,.thinking{display:flex;gap:7px;align-items:center;font-size:12px}input{accent-color:var(--ring)}.caption{font-size:11px;line-height:1.6;color:var(--muted-foreground);margin-top:11px;overflow-wrap:anywhere}.run-controls{display:flex;justify-content:space-between;align-items:center;gap:15px;margin-top:15px}.run-banner{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin:20px 0;padding:14px 18px;background:var(--secondary);border-radius:12px;font-size:11px}.run-banner span,.run-banner a,.trace-link{display:inline-flex;gap:7px;align-items:center}.run-banner code{font-size:10px;overflow-wrap:anywhere}.run-banner a{margin-left:auto}.model-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin-top:22px}.model-card{min-width:0}h2{font-size:21px;font-weight:600;letter-spacing:-.03em;overflow-wrap:anywhere}.model-id{margin-top:3px}.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin:20px 0}.metrics>div{display:flex;flex-direction:column;gap:7px;padding:12px;border:1px solid var(--border);border-radius:11px}.metrics small{font-size:9px;color:var(--muted-foreground)}.metrics strong{font-size:17px;font-weight:600;letter-spacing:-.04em}.answer{min-height:220px;max-height:650px;overflow:auto;font-size:13px;line-height:1.7;padding:5px 0 20px}.empty{font-size:12px;color:var(--muted-foreground);padding:30px 0}.reasoning{border-left:2px solid var(--ring);padding:0 0 0 12px;margin-bottom:17px}.reasoning pre{max-height:190px;background:transparent;padding:5px 0}.evidence{margin-top:12px;border-top:1px solid var(--border);padding-top:6px}summary{font-size:11px;cursor:pointer;padding:8px 0}pre{font-family:var(--font-mono);font-size:10px;line-height:1.6;white-space:pre-wrap;overflow-wrap:anywhere;overflow:auto;max-height:350px;background:var(--code-background);padding:14px;border-radius:10px;margin-top:8px}.trace-link{font-size:11px;margin-top:15px}.notice{display:flex;align-items:flex-start;gap:10px;padding:13px;border:1px solid var(--border);background:var(--secondary);border-radius:11px;margin:15px 0;font-size:12px;line-height:1.6}.notice :global(svg){flex-shrink:0}footer{display:flex;gap:14px;padding:25px 5px;margin-top:12px;color:var(--muted-foreground)}footer strong{font-size:12px;color:var(--foreground)}footer p,footer li{font-size:11px;line-height:1.7;margin-top:6px}footer ul{list-style:disc;padding-left:17px}button:focus-visible,a:focus-visible,summary:focus-visible,input:focus-visible,textarea:focus-visible{outline:2px solid var(--ring);outline-offset:3px}
  .source-status{padding:12px;margin-top:12px;border:1px solid var(--border);border-radius:9px;background:var(--secondary)}.source-status strong{font-size:11px;line-height:1.5}.source-status p{font-size:11px;line-height:1.6;margin-top:6px;color:var(--muted-foreground)}
  .research-browser{border:1px solid var(--border);border-radius:12px;padding:14px;margin:18px 0}.research-browser img{width:100%;max-height:300px;object-fit:contain;border-radius:8px;margin-top:12px;background:var(--background)}
  .research-timeline,.research-sources{border:1px solid var(--border);border-radius:12px;padding:15px;margin:18px 0}.research-heading{display:flex;justify-content:space-between;align-items:center;gap:10px}h3{display:flex;gap:7px;align-items:center;font-size:13px;font-weight:600}.research-timeline ol{list-style:none;padding:0;margin:15px 0 0;max-height:400px;overflow:auto}.research-timeline li{display:flex;gap:10px;border-bottom:1px solid var(--border);padding:10px 0}.step-index{font-size:10px;color:var(--muted-foreground);padding-top:2px}.research-timeline li>div{min-width:0}.research-timeline strong{font-size:11px;line-height:1.5;display:block}.research-timeline small,.research-sources small{display:block;font-size:10px;color:var(--muted-foreground);margin-top:5px}.research-timeline a,.research-sources a{display:inline-flex;gap:5px;font-size:10px;overflow-wrap:anywhere;margin-top:6px}.research-timeline p{font-size:11px}.research-timeline .tool-error{border-left:2px solid var(--ring);padding-left:8px}.research-sources ul{padding:0;list-style:none}.research-sources li{padding:8px 0;border-bottom:1px solid var(--border)}.output-heading{margin:19px 0 10px}
  @media(max-width:1050px){.comparison-page{padding:28px 22px 60px}.model-card{padding:17px}.metrics{gap:5px}.metrics>div{padding:9px}.metrics strong{font-size:14px}}
  @media(max-width:767px){.comparison-page{height:auto;min-height:100dvh;padding:25px 14px}.model-grid{grid-template-columns:1fr}header{flex-wrap:wrap;gap:14px}.prompt-card{padding:17px}.run-controls{flex-wrap:wrap}.run-banner a{margin-left:0}.metrics strong{font-size:18px}.answer{min-height:120px}.section-title{flex-wrap:wrap}}
</style>
