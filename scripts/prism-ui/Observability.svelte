<script lang="ts">
  import { onMount } from 'svelte';
  import MarkdownContent from '$lib/components/app/content/MarkdownContent/MarkdownContent.svelte';
  import { Activity, ArrowUpRight, RefreshCw, GitBranch, CircleAlert, Cpu, Layers } from '@lucide/svelte';
  type RecordData = Record<string, any>;
  let sessions = $state<RecordData[]>([]);
  let detail = $state<RecordData | null>(null);
  let model = $state<RecordData | null>(null);
  let selected = $state('');
  let tab = $state('context');
  let view = $state('chain');
  let showProtocol = $state(false);
  const views = [{id: 'chain', label: 'Chain', icon: GitBranch}, {id: 'node', label: 'Node', icon: Cpu}, {id: 'weights', label: 'Model weights', icon: Layers}];
  function moveView(event: KeyboardEvent, index: number) {
    const next = event.key === 'ArrowRight' ? (index + 1) % views.length : event.key === 'ArrowLeft' ? (index + views.length - 1) % views.length : event.key === 'Home' ? 0 : event.key === 'End' ? views.length - 1 : -1;
    if (next < 0) return;
    event.preventDefault(); view = views[next].id;
    document.getElementById(`obs-tab-${view}`)?.focus();
  }
  let loading = $state(true);
  let loadingDetail = $state(false);
  let error = $state('');
  let requestVersion = 0;
  const node = $derived(detail?.nodes?.find((n: RecordData) => n.id === selected));
  const timing = $derived(Array.isArray(node?.timings) ? node.timings.at(-1) : node?.timings);
  function isInference(step: RecordData | undefined) {return !!step && step.generation_available !== false && ['completion', 'llm', 'inference'].includes(step.kind);}
  function isProtocol(step: RecordData | undefined) {return !!step && !isInference(step) && (step.kind === 'protocol' || step.category === 'protocol' || (!!step.request?.method && step.request.method !== 'tools/call'));}
  const inspectTabs = $derived(isInference(node) ? ['context', 'response', 'configuration', 'runtime', 'tools'] : ['context', 'response', 'runtime']);
  const protocolCount = $derived((detail?.nodes || []).filter((step: RecordData) => isProtocol(step)).length);
  const visibleNodes = $derived((detail?.nodes || []).filter((step: RecordData) => showProtocol || !isProtocol(step)));
  function nodeLabel(step: RecordData) {return isProtocol(step) ? `MCP setup · ${step.request?.method || step.name}` : step.name || (isInference(step) ? 'Model inference' : 'Tool exchange');}
  function nodeStatus(step: RecordData) {return step.complete === false ? 'Incomplete' : typeof step.status === 'number' ? `HTTP ${step.status}` : step.execution_status || step.status || 'Status unavailable';}
  function traceLink(step: RecordData) {return diagnosticLink(step.trace_url) || (step.trace_id ? `http://127.0.0.1:5210/#/experiments/${encodeURIComponent(step.experiment_id || detail?.session?.experiment_id || '3')}/traces?traceId=${encodeURIComponent(step.trace_id)}` : undefined);}

  const manifest = $derived(model?.checkpoint || {});
  const checkpoint = $derived(manifest.checkpoint || {});
  const tensors = $derived(manifest.tensor_metadata || {});
  function attachedReplay(step: RecordData | undefined) {
    const replay = step?.activation_replay;
    const source = replay?.source;
    if (!['new_instrumented_real_request_replay','new_teacher_forced_reconstructed_window'].includes(replay?.kind)) return null;
    if (source?.native_request_id || source?.request_id) return (source.native_request_id || source.request_id) === (step?.original_request_id || step?.request_id) && source.session === detail?.session?.id && source.request_sha256 === step?.request_sha256 ? replay : null;
    return source?.comparison_run_id === detail?.session?.run_id && source?.model === detail?.session?.model && Number(source?.turn) === Number(step?.turn) ? replay : null;
  }
  const activationDiagnostic = $derived(attachedReplay(node));
  const forcedWindow = $derived(activationDiagnostic?.kind === 'new_teacher_forced_reconstructed_window');
  const captureExplanation = $derived(forcedWindow ? 'New teacher-forced diagnostic: recorded answer tokens were fed through a reconstructed prefix. These are not original activations, regenerated answers, or evidence of what caused the error.' : 'These measurements replay the recorded request in a separate execution. They belong to that replay, not the original live generation.');
  const selectedModel = $derived(activationDiagnostic?.model || node?.server?.checkpoint_release || node?.model_identity?.identity?.checkpoint_provenance || node?.server || {});
  const selectedModelName = $derived(selectedModel.repo || selectedModel.path?.split('/').at(-1) || selectedModel.model_path?.split('/').at(-1) || node?.model_identity?.label || 'Identity not captured for this inference');
  const selectedModelHash = $derived(selectedModel.sha256 || selectedModel.verified_file?.sha256 || selectedModel.file?.sha256);

  const replayStatus = $derived(node?.activation_replay_status);
  const replayPending = $derived(['queued', 'running'].includes(replayStatus?.status));
  let requestingCapture = $state(false);
  async function captureInference() {
    if (!node || !detail?.session?.id || requestingCapture) return;
    requestingCapture = true; error = '';
    try {
      const response = await fetch('/api/activation-replay', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({session_id: detail.session.id, node_id: node.id})});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || result.message || `Capture request returned ${response.status}`);
      node.activation_replay_status = result;
      await selectSession(detail.session.id, true);
    } catch (failure) {error = String(failure);} finally {requestingCapture = false;}
  }
  $effect(() => {
    if (!replayPending || !detail?.session?.id) return;
    const id = detail.session.id;
    const timer = setTimeout(() => {void selectSession(id, true);}, 4000);
    return () => clearTimeout(timer);
  });
  const activationSamples = $derived((activationDiagnostic?.samples || []).filter((sample: RecordData) => typeof sample.stats?.rms === 'number' && Number.isFinite(sample.stats.rms)));
  const activationLayers = $derived([...new Set<number>(activationSamples.map((sample: RecordData) => sample.layer))].sort((a, b) => a - b));
  const activationSteps = $derived([...new Set<number>(activationSamples.map((sample: RecordData) => sample.step))].sort((a, b) => a - b));
  const activationMax = $derived(Math.max(0, ...activationSamples.map((sample: RecordData) => sample.stats.rms)));
  let activationSelection = $state('');
  const activationSample = $derived(activationSamples.find((sample: RecordData) => `${sample.layer}:${sample.step}` === activationSelection) || activationSamples[0]);
  let playingActivations = $state(false);
  const activationStepIndex = $derived(Math.max(0, activationSteps.indexOf(activationSample?.step)));
  const vectorScale = $derived(Math.max(0.000001, ...activationSamples.flatMap((sample: RecordData) => (sample.sample || []).filter((value: unknown) => typeof value === 'number' && Number.isFinite(value)).map((value: number) => Math.abs(value)))));
  function selectActivationStep(index: number) {const step = activationSteps[Math.max(0, Math.min(index, activationSteps.length - 1))]; activationSelection = `${activationSample?.layer ?? activationLayers[0]}:${step}`;}
  $effect(() => {void node?.id; activationSelection = ''; playingActivations = false;});
  $effect(() => {
    if (!playingActivations || view !== 'weights' || !activationSamples.length) return;
    if (activationStepIndex >= activationSteps.length - 1) {playingActivations = false; return;}
    const timer = setTimeout(() => selectActivationStep(activationStepIndex + 1), 700);
    return () => clearTimeout(timer);
  });
  let fullVector = $state<RecordData | null>(null);
  let loadingVector = $state(false);
  let vectorError = $state('');
  let vectorDimension = $state(0);
  const vectorKey = $derived(`${node?.id}:${activationSample?.step}:${activationSample?.layer}`);
  const fullVectorScale = $derived(Math.max(.000001, ...(fullVector?.values || []).map((value: number) => Math.abs(value))));
  const fullVectorPoints = $derived((fullVector?.values || []).map((value: number, index: number) => `${20 + index / Math.max(1, fullVector!.length - 1) * 600},${85 - value / fullVectorScale * 68}`).join(' '));
  $effect(() => {void vectorKey; fullVector = null; vectorError = ''; vectorDimension = 0; loadingVector = false;});
  async function loadFullVector() {
    if (!detail?.session?.id || !node || !activationSample) return;
    const key = vectorKey;
    const expectedHash = activationSample.vector_sha256;
    const expectedLength = activationSample.vector_length;
    loadingVector = true; vectorError = '';
    try {
      const params = new URLSearchParams({session: detail.session.id, node: node.id, step: String(activationSample.step), layer: String(activationSample.layer)});
      const data = await get(`/api/observability/activation-vector?${params}`);
      if (key !== vectorKey) return;
      if (data.vector_sha256 !== expectedHash || data.length !== expectedLength || !Array.isArray(data.values) || data.values.length !== expectedLength || !data.values.every((value: unknown) => typeof value === 'number' && Number.isFinite(value))) throw new Error('Vector identity or shape does not match the selected capture.');
      fullVector = data;
    } catch (failure) {if (key === vectorKey) vectorError = String(failure);}
    finally {if (key === vectorKey) loadingVector = false;}
  }
  function activationCell(layer: number, step: number) { return activationSamples.find((sample: RecordData) => sample.layer === layer && sample.step === step); }
  function activationColor(value: number) { return `color-mix(in srgb, var(--ring) ${activationMax > 0 ? Math.round(value / activationMax * 80) : 0}%, var(--card))`; }
  function diagnosticLink(value: unknown) { if (typeof value !== 'string') return undefined; try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) ? value : undefined; } catch { return undefined; } }

  function number(value: any, unit = '') { return typeof value === 'number' && Number.isFinite(value) ? `${value.toLocaleString(undefined, {maximumFractionDigits: 2})}${unit}` : 'Not captured'; }
  function measurement(value: any) { return typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString(undefined, {maximumSignificantDigits: 6}) : 'Not captured'; }
  function diagnosticStatus(item: RecordData) {
    const m = item.metadata || {};
    if (m.overall_quality_pass === false || m.passed === false || m.results?.some((r: RecordData) => r.valid === false)) return 'Retained failure';
    if (m.passed === true) return 'Passed within stated scope';
    return 'Recorded experiment';
  }
  const output = $derived(detail?.session?.latest_output || detail?.session?.last_output || 'No completed text output was captured for this conversation.');
  function json(value: unknown) { return value == null ? 'Not captured' : JSON.stringify(value, null, 2); }
  function date(value: any) { if (!value) return 'Time unavailable'; return new Date(typeof value === 'number' ? value * 1000 : value).toLocaleString(); }
  function duration(value: any) { return typeof value === 'number' ? `${(value / 1000).toFixed(2)} s` : 'Not captured'; }
  async function get(path: string) { const response = await fetch(path); if (!response.ok) throw new Error(`Evidence service returned ${response.status}`); return response.json(); }
  async function selectSession(id: string, preserveSelection = false) {
    const version = ++requestVersion;
    if (!preserveSelection) loadingDetail = true; error = '';
    try {
      const data = await get(`/api/observability/sessions/${encodeURIComponent(id)}`);
      if (version !== requestVersion) return;
      detail = data;
      const newestFirst = [...(data.nodes || [])].reverse();
      const answerNode = newestFirst.find((step: RecordData) => isInference(step) && !step.auxiliary && step.category !== 'title_generation' && step.complete === true && step.response?.choices?.some((choice: RecordData) => choice.finish_reason === 'stop' && choice.message?.content));
      if (!preserveSelection || !data.nodes?.some((step: RecordData) => step.id === selected)) {
        selected = (answerNode || newestFirst.find((step: RecordData) => isInference(step) && !step.auxiliary && step.category !== 'title_generation' && step.category !== 'instrumented_replay') || newestFirst[0])?.id || '';
        tab = 'context';
      }
    } catch (e) { if (version === requestVersion) error = String(e); }
    finally { if (version === requestVersion) loadingDetail = false; }
  }
  async function refresh() {
    loading = true; error = '';
    try {
      const [list, weights] = await Promise.all([get('/api/observability/sessions'), get('/api/observability/model')]);
      sessions = (list.sessions || []).sort((a: RecordData, b: RecordData) => Number(a.id === 'unassigned') - Number(b.id === 'unassigned')); model = weights;
      const id = detail?.session?.id || sessions.find((session) => session.completion_count > 0)?.id || sessions[0]?.id;
      if (id) await selectSession(id);
    } catch (e) { error = String(e); }
    finally { loading = false; }
  }
  onMount(() => { void refresh(); });
</script>

<svelte:head><title>Observability · Prism ML</title></svelte:head>
<div class="prism-observability">
  <header class="obs-header">
    <div><p class="prism-eyebrow">PRISM ML / OBSERVABILITY</p><h1>See the work behind the answer.</h1><p class="obs-subtitle">Follow the conversation. Inspect the evidence. Know what is still unknown.</p></div>
    <button class="obs-button" onclick={refresh} disabled={loading}><RefreshCw size={15} />{loading ? 'Loading…' : 'Refresh'}</button>
  </header>
  <div class="obs-top-tabs" role="tablist" aria-label="Observability views">
    {#each views as item, index}<button id={`obs-tab-${item.id}`} role="tab" aria-selected={view === item.id} aria-controls={`obs-panel-${item.id}`} tabindex={view === item.id ? 0 : -1} class:active={view === item.id} onclick={() => view = item.id} onkeydown={(event) => moveView(event, index)}><item.icon size={17}/>{item.label}</button>{/each}
  </div>
  {#if error}<div role="alert" class="obs-notice"><CircleAlert size={17}/><span>{error}. Evidence is unavailable; no substitute data is displayed.</span></div>{/if}
  <div class="obs-workspace">
    <aside class="obs-sessions" aria-label="Recorded conversations">
      <div class="obs-section-label">CONVERSATIONS <span>{sessions.length}</span></div><p class="obs-caption">Native chats and recorded per-model comparisons. Titles come from recorded inputs.</p>
      {#if !sessions.length && !loading}<p class="obs-empty">No recorded conversations yet. Run a chat through this demo to begin.</p>{/if}
      {#each sessions as session (session.id)}
        <button class:chosen={detail?.session?.id === session.id} class="obs-session" onclick={() => selectSession(session.id)}>
          {#if session.source === 'comparison'}<small>Comparison · {session.label || session.model} · {session.status}</small>{/if}
          <strong>{session.id === 'unassigned' ? 'Unassigned transport / setup' : session.title || 'Recorded conversation'}</strong><span>{date(session.updated_at || session.started_at)}</span>
          <small>{session.completion_count ?? 0} model calls · {session.tool_count ?? 0} tool exchanges{session.error_count ? ` · ${session.error_count} errors` : ''}</small>
        </button>
      {/each}
    </aside>
    <main class="obs-main" aria-busy={loadingDetail}>
      {#if loadingDetail}<p class="obs-caption" role="status">Loading this conversation’s recorded exchanges…</p>{/if}
      {#if view === 'chain'}
      <div class="obs-view-panel" role="tabpanel" id="obs-panel-chain" aria-labelledby="obs-tab-chain" tabindex="0">
      {#if detail}
        <section class="obs-card obs-output">
          <div class="obs-card-heading"><div><p class="obs-section-label">01 / OBSERVED OUTPUT</p><h2>{detail.session?.title || 'Recorded conversation'}</h2></div>{#if detail.session?.source === 'comparison'}<a class="obs-link" href="#/comparison">Open comparison <ArrowUpRight size={15}/></a>{:else if detail.session?.id && detail.session.id !== 'unassigned'}<a class="obs-link" href={`#/chat/${encodeURIComponent(detail.session?.id || '')}`}>Open chat <ArrowUpRight size={15}/></a>{/if}</div>
          {#if detail.session?.source === 'comparison'}<p class="obs-caption">Actual {detail.session.label || detail.session.model} run · {detail.session.run_id} · {detail.session.status}. {#if diagnosticLink(detail.session.trace_url)}<a class="obs-link" href={diagnosticLink(detail.session.trace_url)} target="_blank" rel="noreferrer">Open recorded comparison trace <ArrowUpRight size={13}/></a>{/if}</p>{/if}
          <details open><summary>Latest captured answer</summary><div class="obs-answer obs-answer-rendered"><MarkdownContent content={typeof output === 'string' ? output : json(output)} /></div></details><details><summary>Raw captured answer</summary><pre class="obs-answer">{typeof output === 'string' ? output : json(output)}</pre></details>
          <p class="obs-caption">Captured output is evidence of what was generated, not a quality or factuality assessment.</p>
        </section>
        <section class="obs-card">
          <div class="obs-card-heading"><div><p class="obs-section-label">02 / CONVERSATION TRAJECTORY</p><h2>Every recorded step, in order.</h2></div><span class="obs-pill">{visibleNodes.length} shown exchanges</span></div>
          {#if protocolCount}<label class="obs-caption"><input type="checkbox" bind:checked={showProtocol}/> Show {protocolCount} MCP setup exchanges (not model inference)</label>{/if}
          <div class="obs-chain" aria-label="Trajectory steps">
            {#each visibleNodes as step, i (step.id)}
              <button class="obs-step" class:selected={selected === step.id} onclick={() => {selected = step.id; tab = 'context'; view = 'node';}} aria-pressed={selected === step.id}>
                <span class="obs-step-index">{String(i + 1).padStart(2, '0')}</span>
                {#if step.error || step.execution_status === 'error' || step.status >= 400 || step.complete === false}<CircleAlert size={17}/>{:else}<Activity size={17}/>{/if}
                <span><strong>{nodeLabel(step)}</strong><small>{duration(step.elapsed_ms)} · {nodeStatus(step)}</small></span>
              </button>
            {/each}
          </div>
          <p class="obs-caption">Order shows recorded chronology. Connections below distinguish sequence from matched tool results.</p>
          {#if detail.edges?.length}<details><summary>Recorded connections ({detail.edges.length})</summary><div class="obs-edges">{#each detail.edges as edge}<div><code>{edge.from}</code><span>→ {edge.label || edge.type} →</span><code>{edge.to}</code></div>{/each}</div></details>{/if}
        </section>
      {:else if loading}<div class="obs-card obs-empty">Loading recorded evidence…</div>{:else}<div class="obs-card obs-empty">Select a recorded conversation to inspect its chain.</div>{/if}
      </div>
      {:else if view === 'node'}
      <div class="obs-view-panel" role="tabpanel" id="obs-panel-node" aria-labelledby="obs-tab-node" tabindex="0">
        {#if node}
          <div class="obs-node-navigation"><button class="obs-button" onclick={() => view = 'chain'}><GitBranch size={15}/> Back to chain</button><label>Selected exchange <select aria-label="Selected exchange" value={selected} onchange={(event) => {selected = event.currentTarget.value; tab = 'context';}}>{#each detail?.nodes || [] as step, index}<option value={step.id}>{index + 1}. {nodeLabel(step)}</option>{/each}</select></label></div>
          <section class="obs-card">
            <div class="obs-card-heading"><div><p class="obs-section-label">03 / {isInference(node) ? 'MODEL INFERENCE' : isProtocol(node) ? 'MCP PROTOCOL SETUP' : 'BROWSER / TOOL EXCHANGE'}</p><h2>{nodeLabel(node)}</h2></div><span class="obs-pill">{duration(node.elapsed_ms)}</span></div>
            <p class="obs-caption">{date(node.started_at)} · {node.timestamp_source === 'artifact_mtime' ? 'Artifact modification time (inference start was not captured)' : 'Recorded event time'} · Capture {node.id}</p>
            {#if node.auxiliary || node.category === 'title_generation'}<p class="obs-caption">Auxiliary UI request: generates the chat title, not the answer to the user’s task.</p>{/if}
            {#if isProtocol(node)}<div class="obs-notice"><CircleAlert size={17}/><span>This is an MCP connection handshake or protocol request. It is not model inference: no prompt was evaluated and no model tokens were generated by this exchange. Select a model inference step to inspect generation.</span></div>{/if}
            {#if traceLink(node)}<p class="obs-caption">MLflow trace <code>{node.trace_id}</code> · <a class="obs-link" href={traceLink(node)} target="_blank" rel="noreferrer">Open MLflow <ArrowUpRight size={13}/></a></p>{/if}
            {#if attachedReplay(node)}<div class="obs-notice"><Activity size={17}/><span>A measured diagnostic linked to this recorded request is ready. <button class="obs-link" onclick={() => view = 'weights'}>Inspect measured replay activations <ArrowUpRight size={13}/></button></span></div>{/if}
            {#if replayStatus && !attachedReplay(node)}<div class="obs-notice" role="status"><Activity size={17}/><span>Activation capture: {replayStatus.status}. {replayPending ? 'The replay is processing automatically; this view refreshes every 4 seconds.' : replayStatus.error || ''}</span></div>{/if}
            {#if isInference(node) && !attachedReplay(node) && !replayPending}<button class="obs-button" onclick={captureInference} disabled={requestingCapture}>{requestingCapture ? 'Requesting capture…' : 'Capture this inference'}</button>{/if}
            <div class="obs-tabs" aria-label="Inspect exchange">{#each inspectTabs as name}<button class:active={tab === name} onclick={() => tab = name} aria-pressed={tab === name}>{name}</button>{/each}</div>
            {#if tab === 'runtime' && isInference(node)}
              <div class="obs-metrics">
                <div><small>Recorded exchange</small><strong>{duration(node.elapsed_ms)}</strong><span>Wall-clock duration</span></div>
                <div><small>Generation rate</small><strong>{number(timing?.predicted_per_second, ' tok/s')}</strong><span>Server timing, if emitted</span></div>
                <div><small>Generated tokens</small><strong>{number(timing?.predicted_n)}</strong><span>Includes server-counted tokens</span></div>
                <div><small>Fresh prompt evaluation</small><strong>{typeof timing?.prompt_ms === 'number' ? duration(timing.prompt_ms) : 'Not captured'}</strong><span>{number(timing?.prompt_n)} freshly evaluated tokens</span></div>
                <div><small>Reused prompt cache</small><strong>{number(timing?.cache_n)}</strong><span>Cached input tokens, separate from fresh prefill</span></div>
              </div>
              <p class="obs-caption">Summary uses the last emitted timing snapshot. Streaming snapshots are not added together.</p>
            {/if}
            {#if tab === 'runtime' && !isInference(node)}<div class="obs-metrics"><div><small>{isProtocol(node) ? 'Protocol round trip' : 'Tool exchange duration'}</small><strong>{duration(node.elapsed_ms)}</strong><span>Observed wall-clock time, not generation latency</span></div></div><p class="obs-caption">Generation metrics do not apply to this exchange.</p>{/if}
            <pre class="obs-json">{tab === 'context' ? json(node.request) : tab === 'response' ? json(node.response) : tab === 'configuration' ? json({settings: node.settings, server: node.server}) : tab === 'runtime' ? json({...(isInference(node) ? {timings: node.timings} : {}), elapsed_ms: node.elapsed_ms, status: node.status, execution_status: node.execution_status, timestamp_source: node.timestamp_source, complete: node.complete, error: node.error}) : json({tool_calls: node.tool_calls, tool_results: node.tool_results})}</pre>
            {#if isInference(node)}<p class="obs-caption">Captured reasoning, when present, is model-generated text; it is not a measurement of internal activations.</p>{/if}
            {#if node.citation_audit}<section class="obs-experiment" aria-label="Recorded citation URL audit"><div class="obs-card-heading"><strong>Citation URL check</strong><span class="obs-pill">{node.citation_audit.status || 'Status not recorded'}</span></div><p class="obs-caption">Checks recorded URL provenance only. A pass does not verify claims, current grant availability, or applicant eligibility.</p><dl class="obs-facts"><div><dt>Matched URLs</dt><dd>{node.citation_audit.matched_urls?.length ?? 'Not recorded'}</dd></div><div><dt>Unsupported URLs</dt><dd>{node.citation_audit.unsupported_urls?.length ?? 'Not recorded'}</dd></div><div><dt>Opened-page citation</dt><dd>{node.citation_audit.missing_citations === true ? 'Missing — check failed' : node.citation_audit.missing_citations === false ? 'Present' : 'Not recorded'}</dd></div></dl><details><summary>Recorded URLs and audit scope</summary><pre class="obs-json">{json(node.citation_audit)}</pre></details></section>{/if}
            {#if node.assessments?.length}<details class="obs-reviews"><summary>Recorded reviews ({node.assessments.length})</summary><p class="obs-caption">Reviews retain their recorded judge and source. Automated feedback is not human approval.</p>{#each node.assessments as assessment}<div class="obs-experiment"><strong>{assessment.name || 'Recorded assessment'}</strong><p>Source: {assessment.source?.source_type || assessment.source?.type || 'Not captured'} · {assessment.source?.source_id || 'Judge identity not captured'}</p><pre class="obs-json">{json(assessment)}</pre></div>{/each}</details>{/if}
          </section>
        {:else}<div class="obs-card obs-empty">Select a step in the Chain tab to inspect its recorded context and runtime.</div>{/if}
      </div>
      {:else if view === 'weights'}
      <div class="obs-view-panel" role="tabpanel" id="obs-panel-weights" aria-labelledby="obs-tab-weights" tabindex="0">
      <section class="obs-card">
        <div class="obs-card-heading"><div><p class="obs-section-label">04 / MODEL EVIDENCE</p><h2>Inside the selected inference.</h2></div><Layers size={22}/></div>
        <p class="obs-caption"><strong>{selectedModelName}</strong><br/>Checkpoint SHA-256: <code>{selectedModelHash || 'Not captured'}</code></p>
        <details><summary>Selected inference checkpoint identity</summary><p class="obs-caption">SHA-256: <code>{selectedModelHash || 'Not captured'}</code></p><pre class="obs-json">{json(selectedModel)}</pre></details>
        <div class="obs-activation"><CircleAlert size={20}/><div><strong>{activationDiagnostic ? 'Measured activations for the selected request' : replayPending ? `Activation capture ${replayStatus.status}` : replayStatus?.status === 'error' || replayStatus?.status === 'failed' ? 'Activation capture failed' : 'Capture not requested for this historical inference'}</strong><p>{activationDiagnostic ? captureExplanation : replayPending ? 'Processing automatically. This view refreshes every 4 seconds while capture is queued or running.' : replayStatus?.error || 'Select a recent model turn to inspect its automatically recorded activation replay.'}</p></div></div>
        {#if isInference(node) && !activationDiagnostic && !replayPending}<button class="obs-button" onclick={captureInference} disabled={requestingCapture}>{requestingCapture ? 'Requesting capture…' : 'Capture this inference'}</button>{/if}
        {#if node}<p class="obs-caption">Selected evidence: {detail?.session?.label || detail?.session?.model || 'Native chat'} · {nodeLabel(node)}{node.turn ? ` · turn ${node.turn}` : ''} · {node.id}</p>{/if}
        {#if activationDiagnostic}
          <section class="obs-activation-diagnostic" aria-label="Instrumented replay of recorded request">
            <div class="obs-card-heading"><div><p class="obs-section-label">{forcedWindow ? 'RECORDED ERROR / TEACHER-FORCED DIAGNOSTIC' : 'ACTUAL REQUEST / INSTRUMENTED REPLAY'}</p><h3>Measured activations from this recorded request.</h3></div><span class="obs-pill">{activationDiagnostic.passed === true ? 'Capture passed' : 'Capture status not verified'}</span></div>
            <p class="obs-caption">{captureExplanation}</p>
            <p class="obs-caption"><strong>{activationDiagnostic.settings?.decode_steps ?? 'Unrecorded'}-step capture limit · {activationLayers.length} sampled layers · {activationSteps.length} steps recorded</strong>. Selected layers: {activationLayers.join(', ')}. Generation may end before the limit.</p>
            {#if activationSamples.length && activationSample}
              <div class="activation-player">
                <div class="activation-controls"><button class="obs-button" aria-label="Previous decode step" disabled={activationStepIndex === 0} onclick={() => {playingActivations = false; selectActivationStep(activationStepIndex - 1);}}>← Previous</button><button class="obs-button" onclick={() => {if (activationStepIndex === activationSteps.length - 1) selectActivationStep(0); playingActivations = !playingActivations;}}>{playingActivations ? 'Pause' : 'Play steps'}</button><button class="obs-button" aria-label="Next decode step" disabled={activationStepIndex >= activationSteps.length - 1} onclick={() => {playingActivations = false; selectActivationStep(activationStepIndex + 1);}}>Next →</button><label>Layer <select aria-label="Activation layer" value={activationSample.layer} onchange={(event) => activationSelection = `${event.currentTarget.value}:${activationSample.step}`}>{#each activationLayers as layer}<option value={layer}>{layer}</option>{/each}</select></label></div>
                <label class="activation-scrubber">Decode step {activationStepIndex + 1} of {activationSteps.length}<input type="range" aria-label="Decode step" min="0" max={Math.max(0, activationSteps.length - 1)} value={activationStepIndex} oninput={(event) => {playingActivations = false; selectActivationStep(Number(event.currentTarget.value));}}/></label>
                <p class="obs-caption">Playback follows recorded decode order at a viewing pace, not wall-clock speed.</p>
                <div class="activation-token-strip" aria-label="Recorded token sequence">{#each activationDiagnostic.tokens || [] as token}<button class:active={token.step === activationSample.step} aria-pressed={token.step === activationSample.step} aria-label={`Decode step ${token.step}, processed token ${json(token.input_token_text)}`} onclick={() => {playingActivations = false; selectActivationStep(activationSteps.indexOf(token.step));}}>{token.input_token_text || `#${token.input_token_id}`}</button>{/each}</div>
                <div class="activation-token-focus"><span>Processed token <code>{json(activationSample.input_token_text)}</code></span><span>Decode step {activationSample.step}</span></div><p class="obs-caption">The vector was captured after this token passed through the selected layer.</p>
                <div class="activation-plot-heading"><strong>{activationSample.tensor}</strong><span>RMS {measurement(activationSample.stats.rms)} · {activationSample.vector_length} values captured</span></div>
                <svg class="activation-vector-plot" viewBox="0 0 640 190" role="img" aria-label={`First ${activationSample.sample?.length || 0} actual activation values, layer ${activationSample.layer}, decode step ${activationSample.step}`}>
                  <line x1="20" y1="85" x2="620" y2="85" stroke="currentColor" opacity=".3"/>
                  {#each activationSample.sample || [] as value, index}
                    {@const width = 600 / activationSample.sample.length}
                    {@const height = Math.abs(value) / vectorScale * 68}
                    <rect x={20 + index * width + 3} y={value >= 0 ? 85 - height : 85} width={Math.max(1,width-6)} height={Math.max(.6,height)} rx="2" fill={value >= 0 ? 'var(--ring)' : 'var(--muted-foreground)'}><title>Element {index}: {value}</title></rect>
                    <text x={20 + (index+.5)*width} y="174" text-anchor="middle">{index}</text>
                  {/each}
                </svg>
                <p class="obs-caption">First {activationSample.sample?.length || 0} recorded elements of the full vector; shared vertical scale ±{measurement(vectorScale)} across steps. These are measured values, not a map of causal importance.</p>
                <button class="obs-button" onclick={loadFullVector} disabled={loadingVector || !!fullVector}>{loadingVector ? 'Loading measured vector…' : fullVector ? `All ${fullVector.length} values loaded` : `Inspect all ${activationSample.vector_length} captured values`}</button>
                {#if vectorError}<p class="obs-caption" role="alert">{vectorError}</p>{/if}
                {#if fullVector}<div class="activation-full-vector"><strong>Full activation vector · layer {activationSample.layer}, decode step {activationSample.step}</strong><svg class="activation-vector-plot" viewBox="0 0 640 190" role="img" aria-label={`All ${fullVector.length} captured activation dimensions`}><line x1="20" y1="85" x2="620" y2="85" stroke="currentColor" opacity=".3"/><polyline points={fullVectorPoints} fill="none" stroke="var(--ring)" stroke-width=".8"/><line x1={20 + vectorDimension / Math.max(1,fullVector.length-1)*600} y1="15" x2={20 + vectorDimension / Math.max(1,fullVector.length-1)*600} y2="155" stroke="currentColor" stroke-dasharray="3 3"/><text x="20" y="178">dimension 0</text><text x="620" y="178" text-anchor="end">dimension {fullVector.length - 1}</text></svg><label class="activation-scrubber">Activation dimension {vectorDimension}: {measurement(fullVector.values[vectorDimension])}<input type="range" aria-label="Activation vector dimension" min="0" max={fullVector.length - 1} bind:value={vectorDimension}/></label><p class="obs-caption">Horizontal axis is activation dimension, not token order. All {fullVector.length} values are plotted; SHA-256 was checked by the local endpoint and matched to this captured vector.</p></div>{/if}
                <details><summary>Layer overview across all steps</summary><div class="obs-activation-map"><table><thead><tr><th>Layer / step</th>{#each activationSteps as step}<th>{step}</th>{/each}</tr></thead><tbody>{#each activationLayers as layer}<tr><th>{layer}</th>{#each activationSteps as step}{@const sample = activationCell(layer, step)}<td>{#if sample}<button style:background={activationColor(sample.stats.rms)} class:chosen={activationSample === sample} aria-label={`Layer ${layer}, decode step ${step}, RMS ${sample.stats.rms}`} aria-pressed={activationSample === sample} onclick={() => {playingActivations = false; activationSelection = `${layer}:${step}`;}}>{number(sample.stats.rms)}</button>{:else}<span>Not captured</span>{/if}</td>{/each}</tr>{/each}</tbody></table></div><p class="obs-caption">Color shows measured RMS on a shared scale from 0 to {measurement(activationMax)}.</p></details>
                <details><summary>Exact selected values and statistics</summary><pre class="obs-json">{json(activationSample)}</pre></details>
              </div>
            {:else}<p class="obs-caption">No measured activation samples are available yet.</p>{/if}
            <details><summary>Recorded context and replay output</summary><p class="obs-caption">Prompt</p><pre class="obs-answer">{activationDiagnostic.prompt || activationDiagnostic.rendered_prompt || 'Not recorded'}</pre><p class="obs-caption">{forcedWindow ? 'Recorded tokens fed into this diagnostic' : 'Generated text'}</p><pre class="obs-answer">{(forcedWindow ? activationDiagnostic.forced_text : activationDiagnostic.generated_text) || 'Not recorded'}</pre></details>
            {#if diagnosticLink(activationDiagnostic.mlflow?.url)}<a class="obs-link" href={diagnosticLink(activationDiagnostic.mlflow.url)} target="_blank" rel="noreferrer">Open instrumented replay in MLflow <ArrowUpRight size={14}/></a>{/if}
            <details><summary>Replay lineage, settings and all measurements</summary><pre class="obs-json">{json(activationDiagnostic)}</pre></details>
          </section>
        {/if}
        <details><summary>Current deployment reference (separate from selected inference)</summary>
        <div class="obs-checkpoint">
          <div class="obs-card-heading"><div><small>PUBLIC CHECKPOINT</small><h3>{checkpoint.repo || 'Identity not yet verified'}</h3></div><span class="obs-pill">{(manifest.status || 'not_verified').replaceAll('_', ' ')}</span></div>
          <dl class="obs-facts"><div><dt>Published revision</dt><dd>{checkpoint.revision || 'Not captured'}</dd></div><div><dt>Public demo commit</dt><dd>{manifest.public_demo?.commit || 'Not captured'}</dd></div><div><dt>Runtime</dt><dd>{manifest.runtime?.architecture || 'Not captured'}</dd></div></dl>
          {#each checkpoint.files || [] as file}
            <div class="obs-file"><div><strong>{file.filename}</strong><span class="obs-pill">{file.verified ? 'Hash verified' : 'Verification pending'}</span></div><p>{number(file.size_bytes / (1024 ** 3), ' GiB')} · SHA-256</p><code>{file.sha256 || 'Not captured'}</code></div>
          {/each}
        </div>
        {#if tensors.tensor_count}
          <div class="obs-metrics"><div><small>Architecture</small><strong>{tensors.architecture}</strong><span>GGUF header</span></div><div><small>Weight tensors</small><strong>{number(tensors.tensor_count)}</strong><span>Tensor count, not parameter count</span></div><div><small>Transformer blocks</small><strong>{number(tensors.metadata?.[`${tensors.architecture}.block_count`])}</strong><span>Declared model structure</span></div></div>
          <p class="obs-caption">{tensors.source}. This is checkpoint structure, not a visualization of neuron activity.</p>
          <div class="obs-tensor-types" aria-label="Tensor storage types">{#each Object.entries(tensors.type_counts || {}) as [type, count]}<div><span>{type}</span><div class="obs-bar-track"><div style:width={`${Number(count) / tensors.tensor_count * 100}%`}></div></div><strong>{String(count)}</strong></div>{/each}</div>
          <details><summary>Inspect example weight tensors</summary><div class="obs-tensor-table"><table><thead><tr><th>Tensor</th><th>Shape</th><th>Storage</th></tr></thead><tbody>{#each tensors.examples || [] as tensor}<tr><td><code>{tensor.name}</code></td><td>{tensor.shape?.join(' × ')}</td><td>{tensor.type}</td></tr>{/each}</tbody></table></div></details>
        {/if}
        {#if tensors.weight_samples?.length}
          <details class="obs-weight-samples" open><summary>Stored weight samples</summary>
            <p class="obs-caption">Actual stored values sampled from the checkpoint. These are model parameters, not inference activations or a causal explanation of an answer. Only the displayed elements are sampled.</p>
            {#each tensors.weight_samples as sample}
              <div class="obs-experiment"><strong>{sample.name}</strong><p>{sample.type} · Shape {sample.shape?.join(' × ')} · {sample.values?.length || 0} displayed values</p>
                <div class="obs-tensor-table"><table><thead><tr><th>Sample position</th><th>Stored value</th></tr></thead><tbody>{#each sample.values || [] as value, index}<tr><td>{index}</td><td><code>{String(value)}</code></td></tr>{/each}</tbody></table></div>
                <details><summary>Sample provenance and metadata</summary><pre class="obs-json">{json(sample)}</pre></details>
              </div>
            {/each}
          </details>
        {/if}
        <details><summary>Current server and checkpoint provenance</summary><pre class="obs-json">{json(model && {current_server: model.current_server, checkpoint: model.checkpoint})}</pre></details>
        {#if detail?.model_evidence}<details><summary>Current deployment evidence (not historical activation data)</summary><pre class="obs-json">{json(detail.model_evidence)}</pre></details>{/if}
        {#if model?.diagnostics}
          <div class="obs-diagnostics"><p class="obs-section-label">LIFECYCLE / RETAINED EXPERIMENTS</p><h3>What was tested beyond this conversation?</h3><p class="obs-caption">These isolated diagnostics have their own scope and checkpoint identity. They do not explain this chat's internal activations.</p>
          {#each model.diagnostics.diagnostics || [] as experiment}<details class="obs-experiment"><summary><span>{experiment.name}</span><small>{diagnosticStatus(experiment)}</small></summary><p>{experiment.limitation}</p><pre class="obs-json">{json(experiment)}</pre></details>{/each}
          <details><summary>Full diagnostic inventory and tracking stores</summary><pre class="obs-json">{json(model.diagnostics)}</pre></details></div>
        {/if}

        </details>
      </section>
      </div>
      {/if}
      {#if detail?.limitations?.length || model?.limitations?.length}<details class="obs-card"><summary>Evidence boundaries</summary><ul class="obs-limitations">{#each [...new Set([...(detail?.limitations || []), ...(model?.limitations || [])])] as limitation}<li>{limitation}</li>{/each}</ul></details>{/if}
    </main>
  </div>
</div>
