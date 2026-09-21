<script lang="ts">
  import { onMount } from 'svelte';
  import WorkspaceData from '$lib/WorkspaceData.svelte';
  import { ArrowUp, Code2, ExternalLink, Layers, Monitor, Plus, Square, Workflow } from '@lucide/svelte';
  type Data = Record<string, any>;
  let status = $state<Data | null>(null);
  let project = $state<Data | null>(null);
  let events = $state<Data[]>([]);
  let attempt = $state('');
  let prompt = $state('');
  let error = $state('');
  let busy = $state(false);
  let loading = $state(true);
  let tab = $state('preview');
  let home = $state(true);
  let selectedCase = $state('baseline');
  let preview = $state<Data | null>(null);
  const running = $derived(Boolean(status?.running_attempts?.length));
  const sourceBusy = $derived(Boolean(status?.running_source_jobs?.length));
  const lastEvent = $derived(events.at(-1));
  const trace = $derived(events.find(e => e.kind === 'trace.started')?.payload);
  const content = $derived(events.filter(e => e.kind === 'model.delta' && e.payload.field === 'content').map(e => e.payload.text).join(''));
  const activity = $derived(events.filter(e => e.kind !== 'model.delta'));
  const requests = $derived(project?.attempts ?? []);
  const suggestions = [
    {label: 'Drill into runtimes', case: 'W1', prompt: 'Add runtime drilldown under the existing parameter-size groups. Use an accessible Runtime select. Preserve source identities, values, links, note saving, and Clear filters. Build and verify the result.'},
    {label: 'Focus evidence notes', case: 'W2', prompt: 'Keep the runtime drilldown. Filter the existing saved-note list to the selected record. Add Show all notes to restore all notes. On reload show all notes. Preserve saved notes and all source behavior. Build and verify the result.'}
  ];

  async function api(path = '', body?: Data) {
    const response = await fetch('/api/workspace' + path, {cache: 'no-store', ...(body ? {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)} : {})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error ?? `Workspace returned ${response.status}`);
    return result;
  }
  async function refresh() { status = await api(); }
  async function choose(id: string) {
    project = await api('/' + id);
    home = false;
    localStorage.setItem('bonsai-workspace', id);
    preview = project?.preview ?? null;
    const latest = project?.attempts?.at(-1);
    attempt = latest?.id ?? '';
    events = [];
    if (attempt) await pollEvents();
  }
  async function pollEvents() {
    const id = attempt;
    if (!id) return;
    const result = await api('/' + id + '/events?after=' + (events.at(-1)?.sequence ?? 0));
    if (attempt !== id) return;
    events = [...events, ...result.events];
    for (const event of result.events) {
      if (event.kind === 'preview.ready' && project) {
        project = await api('/' + project.id);
        preview = project?.preview ?? null;
      }
      if (event.kind === 'patch.applied' || event.kind.startsWith('attempt.')) {
        if (project) project = await api('/' + project.id);
      }
    }
  }
  async function restore() {
    if (!project) return;
    busy = true; error = '';
    try {
      const result = await api('/' + project.id + '/preview', {});
      if (!result.ok) throw new Error(result.stderr ?? 'The saved revision did not build');
      preview = result;
    } catch (e) { error = String(e); }
    finally { busy = false; }
  }
  async function create() {
    busy = true; error = '';
    try { const value = await api('', {}); await refresh(); await choose(value.id); await restore(); }
    catch (e) { error = String(e); }
    finally { busy = false; }
  }
  async function submit(event: SubmitEvent) {
    event.preventDefault();
    if (!project || !prompt.trim() || busy || running || sourceBusy) return;
    busy = true; error = '';
    try {
      const result = await api('/' + project.id + '/attempts', {request: prompt.trim(), base_revision: project.head, case: selectedCase});
      attempt = result.attempt_id; events = []; prompt = ''; selectedCase = 'baseline';
      project = await api('/' + project.id); await refresh();
    } catch (e) { error = String(e); }
    finally { busy = false; }
  }
  async function cancel() {
    try { await api('/' + attempt + '/cancel', {}); await refresh(); await pollEvents(); }
    catch (e) { error = String(e); }
  }
  function useSuggestion(suggestion: typeof suggestions[number]) { prompt = suggestion.prompt; selectedCase = suggestion.case; }
  onMount(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    async function init() {
      try {
        await refresh();
        // Opening the workspace never selects a benchmark fixture implicitly.
      } catch (e) { error = String(e); }
      finally { loading = false; }
      if (!stopped) void poll();
    }
    async function poll() {
      try { await refresh(); await pollEvents(); }
      catch (e) { if (!stopped) error = String(e); }
      if (!stopped) timer = setTimeout(poll, 1200);
    }
    void init();
    return () => { stopped = true; clearTimeout(timer); };
  });
</script>

<main class="workspace">
  <header class="heading">
    <div><p class="eyebrow">BONSAI / WORKSPACE</p><h1>Build on what you know.</h1><p class="subtitle">Your data, an existing project, and each change kept in context.</p></div>
    <div class="header-actions"><span class="model"><span class:active={running} class="dot"></span>Bonsai 2 · local</span><button onclick={() => home = true} disabled={busy || running || loading}><Plus size={15}/> Your data</button></div>
  </header>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  {#if loading}<p role="status">Opening Workspace…</p>
  {:else if home || !project}
    <section class="start-layout" aria-label="Workspace starting point">
      <div class="start-intro"><p class="eyebrow">START WITH YOUR DATA</p><h2>What do you want to understand?</h2><p>Bring a question and your files. Work with Bonsai to understand the evidence, choose a view, and refine it together.</p><p class="scope-note">Files and a question → shared understanding → confirm a view → explore and refine.</p>
      <details class="saved-projects"><summary>Saved projects ({status?.workspaces?.length ?? 0})</summary><p>Open a saved visualization to continue editing. Older source explorers are retained as test projects.</p>{#each status?.workspaces ?? [] as item (item.id)}<button onclick={() => choose(item.id).catch(e => error = String(e))} disabled={busy || running}>{item.title}</button>{/each}<button onclick={create} disabled={busy || running}>Create another test explorer</button></details></div>
      <div class="data-start"><WorkspaceData onProject={(id) => { tab = 'preview'; choose(id).catch(e => error = String(e)); }}/></div>
    </section>
  {:else}
    <div class="project-bar"><label>Project <select value={project.id} onchange={(event) => choose(event.currentTarget.value).catch(e => error = String(e))} disabled={running || busy}>{#each status?.workspaces ?? [] as item (item.id)}<option value={item.id}>{item.title}</option>{/each}</select></label><span>{project.fixture?.kind === 'desktop' ? 'Your uploaded data' : 'Test project'}</span><span class="revision">Revision {project.head.slice(0, 10)}</span></div>
    <div class="panes">
      <section class="conversation" aria-label="Workspace conversation">
        <div class="conversation-body">
          <div class="context-card"><p class="eyebrow">{project.fixture?.kind === 'desktop' ? 'YOUR SAVED PROJECT' : 'SAVED TEST PROJECT'}</p><h2>{project.title}</h2><p>{project.fixture?.kind === 'desktop' ? 'A model-planned Semiotic visualization of your uploaded records. Ask for a focused change and inspect the result.' : 'This cached explorer is a harness test fixture.'}</p></div>
          {#each requests as request (request.id)}<article class="request"><p>{request.request}</p><small>{request.status}</small></article>{/each}
          {#if content}<article class="response"><p class="eyebrow">BONSAI</p><p>{content}</p></article>{/if}
          {#if activity.length}<div class="activity" aria-label="Attempt activity">{#each activity as event (event.sequence)}<div><span class="event-dot"></span><span>{event.kind.replaceAll('.', ' ')}{event.payload.name ? ' · ' + event.payload.name : ''}</span>{#if event.payload.ok === false}<strong>Needs repair</strong>{/if}</div>{/each}</div>{/if}
          {#if lastEvent?.kind === 'attempt.failed'}<p class="error">{lastEvent.payload.error ?? 'Attempt did not finish. Saved revisions are available.'}</p>{/if}
          {#if lastEvent?.kind === 'attempt.completed'}<p class="verified">Build and authored browser checks passed.</p>{/if}
        </div>
        <div class="composer">
          {#if project.fixture?.kind !== 'desktop'}<div class="suggestions">{#each suggestions as suggestion (suggestion.case)}<button disabled={running || busy} onclick={() => useSuggestion(suggestion)}>{suggestion.label}</button>{/each}</div>{/if}
          <form onsubmit={submit}><label class="sr-only" for="workspace-prompt">Describe the next change</label><textarea id="workspace-prompt" bind:value={prompt} placeholder="What should this project do next?" disabled={running || busy || sourceBusy}></textarea><div><span>{sourceBusy ? 'Source generation is using Bonsai…' : running ? 'Editing saved project…' : 'Edits · builds · browser checks'}</span>{#if running}<button type="button" onclick={cancel} aria-label="Stop attempt"><Square size={16}/></button>{:else}<button class="send" type="submit" disabled={!prompt.trim() || busy || sourceBusy} aria-label="Send request"><ArrowUp size={18}/></button>{/if}</div></form>
          <small>Every attempt keeps its source, diagnostics, and MLflow evidence.</small>
        </div>
      </section>
      <section class="output" aria-label="Workspace output">
        <nav aria-label="Workspace views"><button class:chosen={tab === 'preview'} onclick={() => tab = 'preview'}><Monitor size={15}/> Preview</button><button class:chosen={tab === 'code'} onclick={() => tab = 'code'}><Code2 size={15}/> Source</button><button class:chosen={tab === 'trace'} onclick={() => tab = 'trace'}><Workflow size={15}/> Evidence</button><button class:chosen={tab === 'data'} onclick={() => tab = 'data'}><Layers size={15}/> Data</button>{#if preview}<a href={preview.url} target="_blank" rel="noreferrer" aria-label="Open preview in a new tab"><ExternalLink size={15}/></a>{/if}</nav>
        {#if tab === 'preview'}
          {#if preview}<div class="preview-caption">{preview.revision === project.head ? 'Current revision' : 'Earlier successful build'} · {preview.revision.slice(0, 10)}</div><iframe title="Generated project preview" src={preview.url + '?revision=' + preview.revision} sandbox="allow-scripts allow-same-origin"></iframe>
          {:else}<div class="preview-empty"><Monitor size={32}/><h2>Your project preview</h2><p>Build the saved revision to open it here. This step does not call the model.</p><button onclick={restore} disabled={busy || running}>{busy ? 'Building…' : 'Build saved revision'}</button></div>{/if}
        {:else if tab === 'data'}<WorkspaceData onProject={(id) => { tab = 'preview'; choose(id).catch(e => error = String(e)); }}/>
        {:else if tab === 'code'}<div class="source-title">App.svelte <span>{project.head.slice(0, 10)}</span></div><pre class="source"><code>{project.files['App.svelte']}</code></pre>
        {:else}<div class="evidence"><h2>Evidence for this attempt</h2><p>The complete attempt links model exchanges, patches, build diagnostics, and browser checks.</p>{#if trace}<a href={trace.mlflow_url} target="_blank" rel="noreferrer">Open complete MLflow attempt <ExternalLink size={14}/></a>{:else}<p>No model attempt recorded yet.</p>{/if}{#each activity as event (event.sequence)}<details><summary>{event.sequence}. {event.kind}</summary><pre>{JSON.stringify(event.payload, null, 2)}</pre></details>{/each}</div>{/if}
      </section>
    </div>
  {/if}
</main>

<style>
  .start-layout{display:grid;grid-template-columns:minmax(260px, .8fr) minmax(0, 1.2fr);gap:40px;align-items:start;padding:28px 0}.start-intro h2{font-size:28px;letter-spacing:-.7px;font-weight:500;margin:12px 0}.start-intro>p:not(.eyebrow),.saved-projects p{font-size:13px;line-height:1.7;color:var(--muted-foreground);max-width:460px}.scope-note{padding:16px;border-left:2px solid var(--border);margin:26px 0}.data-start{border:1px solid var(--border);border-radius:15px;background:var(--card);min-width:0}.saved-projects{border-top:1px solid var(--border);padding-top:20px;font-size:12px}.saved-projects summary{cursor:pointer}.saved-projects button{display:block;margin:10px 0;max-width:100%;text-align:left;overflow-wrap:anywhere}@media(max-width:750px){.start-layout{grid-template-columns:1fr;gap:20px;padding:12px 0}.start-intro h2{font-size:25px}}

  .workspace{height:100dvh;overflow:auto;padding:30px 32px 20px;color:var(--foreground);background:radial-gradient(ellipse at 80% 0%,#b893891a,transparent 60%);display:flex;flex-direction:column;gap:18px}
  .heading,.header-actions,.project-bar,.output nav,.composer form>div{display:flex;align-items:center;justify-content:space-between;gap:16px}.heading{flex-wrap:wrap}.eyebrow{font-size:10px;letter-spacing:.15em;color:var(--muted-foreground);margin:0 0 9px}.heading h1{font-size:30px;font-weight:500;letter-spacing:-1px;margin:0}.subtitle{font-size:13px;color:var(--muted-foreground);margin:8px 0 0}
  button,select{font:inherit;color:inherit;border:1px solid var(--border);border-radius:9px;background:var(--card);padding:9px 12px;cursor:pointer}button{display:inline-flex;align-items:center;justify-content:center;gap:7px;font-size:12px}button:disabled{opacity:.5;cursor:default}button:focus-visible,textarea:focus-visible,select:focus-visible,a:focus-visible{outline:2px solid var(--ring);outline-offset:3px}.model{display:flex;align-items:center;gap:8px;font-size:11px;white-space:nowrap}.dot{width:7px;height:7px;border-radius:50%;background:#6c7d5a}.dot.active{box-shadow:0 0 0 4px #6c7d5a22}.project-bar{font-size:11px;color:var(--muted-foreground);justify-content:flex-start}.project-bar label{display:flex;align-items:center;gap:10px}.project-bar select{max-width:260px}.revision{margin-left:auto;font-family:monospace}
  .panes{display:grid;grid-template-columns:minmax(290px,360px) minmax(0,1fr);flex:1;min-height:590px;border:1px solid var(--border);border-radius:15px;overflow:hidden;background:var(--card)}.conversation{display:flex;flex-direction:column;min-width:0;border-right:1px solid var(--border)}.conversation-body{padding:22px;overflow:auto;max-height:calc(100dvh - 440px);min-height:270px;flex:1}.context-card h2{font-size:16px;margin:0 0 9px}.context-card p:not(.eyebrow){font-size:12px;line-height:1.6;color:var(--muted-foreground)}.request{margin-top:22px;background:var(--secondary);padding:14px;border-radius:12px}.request p,.response p{white-space:pre-wrap;font-size:12px;line-height:1.7;margin:0}.request small{font-size:10px;color:var(--muted-foreground)}.response{margin-top:23px}.response .eyebrow{margin-bottom:8px}.activity{display:grid;gap:9px;margin-top:22px;font-size:10px;color:var(--muted-foreground)}.activity>div{display:flex;align-items:center;gap:8px}.event-dot{width:5px;height:5px;background:var(--ring);border-radius:50%;flex-shrink:0}.activity strong{color:#9b542d;font-weight:500}.composer{padding:16px;border-top:1px solid var(--border)}.suggestions{display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap}.suggestions button{font-size:10px;padding:6px 8px;background:transparent}.composer form{border:1px solid var(--border);border-radius:12px;background:var(--background);padding:12px}.composer textarea{background:transparent;resize:vertical;border:0;min-height:70px;width:100%;font:inherit;font-size:12px;line-height:1.6;color:inherit}.composer form>div span,.composer>small{font-size:9px;color:var(--muted-foreground)}.composer>small{display:block;margin-top:10px}.send{background:var(--primary);color:var(--primary-foreground)}.composer .send{padding:6px}
  .output{min-width:0;display:flex;flex-direction:column;overflow:hidden}.output nav{justify-content:flex-start;padding:10px 14px;border-bottom:1px solid var(--border);gap:5px}.output nav button{border:0;background:transparent;color:var(--muted-foreground)}.output nav .chosen{background:var(--secondary);color:var(--foreground)}.output nav a{margin-left:auto;color:var(--muted-foreground);padding:8px}.output iframe{border:0;flex:1;width:100%;min-height:500px;background:white}.preview-caption,.source-title{font-size:10px;color:var(--muted-foreground);padding:10px 18px;border-bottom:1px solid var(--border)}.source-title{display:flex;justify-content:space-between}.source{padding:18px;margin:0;overflow:auto;font-size:11px;line-height:1.7;max-height:calc(100dvh - 260px);background:var(--code-background)}.preview-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;gap:14px;padding:40px;color:var(--muted-foreground);flex:1}.preview-empty h2{color:var(--foreground);font-size:20px;margin:0}.preview-empty p{font-size:13px;max-width:460px;line-height:1.7;margin:0}.evidence{padding:24px;overflow:auto;max-height:calc(100dvh - 260px)}.evidence h2{font-size:18px}.evidence p,.evidence a{font-size:12px;line-height:1.7}.evidence a{display:flex;gap:8px;align-items:center;margin-bottom:20px}.evidence details{border-top:1px solid var(--border);padding:12px 0;font-size:11px}.evidence pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:10px}.error{padding:12px;background:#ac49251a;border:1px solid #ac492544;border-radius:9px;font-size:12px;overflow-wrap:anywhere}.verified{font-size:12px;color:#637f47;margin-top:18px}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
  @media(max-width:1050px){.workspace{padding:24px 18px}.panes{grid-template-columns:minmax(260px,320px) minmax(0,1fr)}.heading h1{font-size:26px}.header-actions{gap:10px}}
  @media(max-width:750px){.workspace{height:auto;min-height:100dvh;padding:64px 12px 22px}.heading{gap:18px}.panes{grid-template-columns:1fr}.conversation{border-right:0;border-bottom:1px solid var(--border)}.conversation-body{max-height:380px;min-height:200px}.project-bar{flex-wrap:wrap;gap:8px}.revision{margin-left:0}.source,.evidence{max-height:600px}.output iframe{min-height:660px}.header-actions{width:100%;justify-content:space-between}.preview-empty{min-height:350px;padding:25px}.output nav{padding:9px 7px;gap:0}}
</style>
