<script>
  import { onMount } from 'svelte';
  let model = $state(null);
  let selected = $state(null);
  const selectedMedia = $derived.by(() => {
    const seen=new Set();
    return (selected?.locator.source_evidence ?? []).flatMap(passage=>{
      const link=model?.evidence_links?.[passage.record_id];
      const locator=passage.locator ?? {};
      const filename=String(locator.source_filename ?? '');
      const seconds=locator.time_seconds ?? locator.start_seconds;
      const kind=['audio','video'].includes(locator.source_kind) ? locator.source_kind : /\.(mp4|mov|webm)$/i.test(filename) || locator.time_seconds!==undefined ? 'video' : /\.(wav|mp3|m4a)$/i.test(filename) || locator.start_seconds!==undefined ? 'audio' : '';
      if(!link || !kind || typeof seconds!=='number' || !Number.isFinite(seconds) || seconds<0)return [];
      const key=link.url.split('#')[0]+'#t='+seconds;
      if(seen.has(key))return [];seen.add(key);
      return [{key,url:link.url,kind,seconds,label:filename || 'Original source'}];
    });
  });
  function sourceHref(value) {
    if(typeof value!=='string' || !/^https?:\/\//i.test(value))return null;
    try {const url=new URL(value);return ['http:','https:'].includes(url.protocol) ? url.href : null;}
    catch {return null;}
  }
  let group = $state('');
  let chartScale = $state(0);
  let search = $state('');
  let dateField = $state('');
  let dateFrom = $state('');
  let dateTo = $state('');
  let includeUndated = $state(false);
  const dateFields = $derived((model?.plan.fields ?? []).filter(field => field.type === 'date'));
  const activeDateField = $derived(dateField || dateFields[0]?.name || '');
  const dateActive = $derived(Boolean(activeDateField && (dateFrom || dateTo)));
  const invalidRange = $derived(Boolean(dateFrom && dateTo && dateFrom > dateTo));
  const undatedCount = $derived((model?.rows ?? []).filter(row => row.data[activeDateField] == null).length);
  function inDateWindow(row) {
    if (!dateActive) return true;
    if (invalidRange) return false;
    const value = row.data[activeDateField];
    if (value == null) return includeUndated;
    return (!dateFrom || value >= dateFrom) && (!dateTo || value <= dateTo);
  }
  function clearFilters() { group='';search='';dateFrom='';dateTo='';includeUndated=false; }
  let note = $state('');
  let noteDrafts = $state({});
  let savingNote = $state(false);
  function selectRecord(row) {
    if(selected)noteDrafts[selected.id]=note;
    selected=row;note=noteDrafts[row.id] ?? '';
  }
  let notes = $state([]);
  let error = $state('');
  const visible = $derived((model?.rows ?? []).filter(row => (!group || model.node_membership[group]?.includes(row.id)) && JSON.stringify(row.data).toLowerCase().includes(search.toLowerCase()) && inDateWindow(row)));
  function locationLabel(locator) {
    if(locator.structured_record)return 'Structured record '+locator.structured_record;
    if(locator.page)return 'Page '+locator.page;
    if(locator.time_seconds !== undefined)return 'Video at '+Number(locator.time_seconds).toFixed(1)+'s';
    if(locator.start_seconds !== undefined)return 'Audio at '+Number(locator.start_seconds).toFixed(1)+'s';
    if(locator.line)return 'Line '+locator.line;
    if(locator.record)return 'Record '+locator.record;
    return 'Source record';
  }
  function recordTitle(row) {
    for(const key of ['title','name','model','stage','subject','id']) {
      const value=row.data[key];
      if(typeof value==='string' && value.trim())return value.length>120 ? value.slice(0,117)+'…' : value;
      if(key==='id' && typeof value==='number')return 'Record '+value;
    }
    return locationLabel(row.locator);
  }
  function fieldLabel(name) {
    const words = name.replaceAll('_', ' ').replace(/([a-z])([A-Z])/g, '$1 $2');
    return words.charAt(0).toUpperCase() + words.slice(1);
  }
  function fieldValue(value) {
    if (value == null) return 'Not provided';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }
  async function api(path, body) {
    const response = await fetch(path, body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Request failed');
    return result;
  }
  onMount(() => { Promise.all([api('/api/desktop'),api('/api/annotations')]).then(([data,saved])=>{model=data;notes=saved;}).catch(e=>error=String(e)); });
  async function save() {
    if(!selected || !note.trim() || savingNote)return;
    const recordId=selected.id;const text=note;
    savingNote=true;error='';
    try {
      const saved=await api('/api/annotations',{record_id:recordId,note:text});notes=[...notes,saved];
      if(noteDrafts[recordId]===text)delete noteDrafts[recordId];
      if(selected?.id===recordId && note===text)note='';
    } catch(e){error=String(e);}
    finally {savingNote=false;}
  }
</script>
<main>
  {#if error}<p role="alert">{error}</p>{/if}
  {#if model}
    <header><p class="eyebrow">BONSAI / YOUR DATA</p><h1>{model.plan.title}</h1><p>{model.plan.summary}</p><p class="provenance">{model.rows.length} {model.record_origin === 'model_structured_unreviewed' ? 'model-structured records' : 'source records'} · {model.chart.component === 'RecordTable' ? 'Source record table' : 'Semiotic ' + model.chart.component} {#if model.chart.component !== 'RecordTable'}· {model.excluded_record_ids.length} records without plotted coordinates{/if}</p></header>
    {#if model.planning_coverage}<details class="provenance"><summary>Source coverage · {model.planning_coverage.records_shown} of {model.planning_coverage.records_total} records supplied to Bonsai</summary><p>{model.planning_coverage.coverage}. This describes model input, not verified understanding.</p>{#each model.planning_coverage.member_coverage ?? [] as member (member.source_id)}<p><strong>{member.filename}</strong>: {member.records_shown} of {member.records_total ?? 'unknown'} records included.{#if !member.represented} Not included in model context; this view cannot establish findings about this file.{/if}</p>{/each}</details>{/if}
    {#if model.chart.component === 'RecordTable'}
      <!-- Keyboard users must be able to focus and scroll a wide source table. -->
      <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
      <div class="table-scroll" tabindex="0" role="region" aria-label="Source record table"><table><thead><tr>{#each model.chart.props.columns as column (column)}<th scope="col">{fieldLabel(column)}</th>{/each}<th scope="col">Evidence</th></tr></thead><tbody>{#each visible as row (row.id)}<tr data-table-record-id={row.id}>{#each model.chart.props.columns as column (column)}<td>{row.data[column] == null ? 'Missing' : String(row.data[column])}</td>{/each}<td><button onclick={()=>selectRecord(row)} aria-label={'Review table record '+row.id}>Review</button></td></tr>{/each}</tbody></table></div>
      <p class="provenance">Showing {model.chart.props.columns.length} overview fields. All fields and source passages remain in record details below.</p>
    {:else}
    <div class="chart-controls" aria-label="Chart controls"><button aria-label="Zoom out" disabled={chartScale===0} onclick={()=>chartScale=chartScale<=1 ? 0 : chartScale-.5}>−</button><span aria-live="polite">{chartScale ? Math.round(chartScale*100)+'%' : 'Fit'}</span><button aria-label="Zoom in" disabled={chartScale>=3} onclick={()=>chartScale=chartScale ? Math.min(3,chartScale+.5) : 1}>＋</button><button onclick={()=>chartScale=0}>Fit chart</button></div>
    <p class="provenance">Zoom in to read labels. Scroll inside the chart to explore it.</p>
    <!-- Keyboard users can scroll the chart without selecting a node. -->
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <div class="chart-viewport" role="region" aria-label="Scrollable chart" tabindex="0"><section class="chart" aria-label="Data visualization" style:width={chartScale ? (model.chart.props.width*chartScale)+'px' : '100%'}><img src="/api/chart.svg" alt={model.plan.title}/>{#each model.interaction?.nodes ?? [] as node (node.id)}<button class="node-target" class:chosen={group === node.id} style:left={(node.x / model.interaction.width * 100) + '%'} style:top={(node.y / model.interaction.height * 100) + '%'} aria-label={'Explore '+node.label} title={node.label} onclick={()=>group=node.id}></button>{/each}</section></div>
    {#if group}<p class="selected-context">Selected group: {model.chart.props.nodes?.find(node=>node.id===group)?.label}</p>{/if}
    {/if}
    <p class="provenance">{model.grouping_origin}. Model field types and view choices need review.</p>
    {#if model.grouping_root}<p class="provenance">Lines connect each evidence group to All records. They show membership, not causal links.</p>{/if}
    <div class="filters"><label>Search records<input bind:value={search} type="search"/></label>{#if model.chart.component === 'ForceDirectedGraph'}<label>Group<select aria-label="Group" bind:value={group}><option value="">All records</option>{#each model.chart.props.nodes as node (node.id)}<option value={node.id}>{node.label} ({model.node_membership[node.id].length})</option>{/each}</select></label>{/if}<button onclick={clearFilters}>Clear filters</button></div>
    {#if dateFields.length}<details class="date-explorer"><summary>Explore by date{dateActive ? ' · filter applied' : ''}</summary><div class="filters"><label>Date field<select value={activeDateField} onchange={event=>dateField=event.currentTarget.value}>{#each dateFields as field (field.name)}<option value={field.name}>{fieldLabel(field.name)}</option>{/each}</select></label><label>From date<input type="date" bind:value={dateFrom}/></label><label>Through date<input type="date" bind:value={dateTo}/></label></div><label class="undated-option"><input type="checkbox" bind:checked={includeUndated}/> Include records without this date ({undatedCount})</label><p class="provenance">Dates include both endpoints. Undated records stay visible until a date boundary is set.</p>{#if invalidRange}<p role="alert">From date must be on or before Through date.</p>{/if}</details>{/if}
    <p role="status">Showing {visible.length} of {model.rows.length} records matching your filters.</p>
    {#if model.chart.component !== 'RecordTable' && (group || search || dateActive)}<p class="provenance">The chart shows the full dataset. The record list follows your selected group, search, and date window.</p>{/if}
    {#if selected && !visible.some(row=>row.id===selected.id)}<p class="provenance">The record selected for your note is outside the current filters.</p>{/if}
    <div class="panes"><section aria-label="Source records"><h2>Records <small>{visible.length}</small></h2>{#each visible as row (row.id)}<article data-testid="record-row" data-record-id={row.id} class:selected={selected?.id === row.id}>
      <div class="record-heading"><h3>{recordTitle(row)}</h3><button onclick={()=>selectRecord(row)} aria-pressed={selected?.id === row.id} aria-label={'Inspect '+row.id}>{selected?.id === row.id ? 'Selected' : 'Add note'}</button></div>
      <dl class="record-fields">{#each Object.entries(row.data) as [field,value] (field)}<div><dt>{fieldLabel(field)}</dt><dd class:missing={value == null}>{#if sourceHref(value)}<a href={sourceHref(value)} target="_blank" rel="noreferrer">{fieldValue(value)}</a>{:else}{fieldValue(value)}{/if}</dd></div>{/each}</dl>
      <details class="raw-data"><summary>Raw data</summary><pre data-testid="record-data">{JSON.stringify(row.data,null,2)}</pre></details>{#if row.locator.source_evidence}<details><summary>Supporting source passages</summary>{#each row.locator.source_evidence as passage,i (i)}<blockquote>{passage.quote}</blockquote>{#if model.evidence_links?.[passage.record_id]}<a href={model.evidence_links[passage.record_id].url} target="_blank" rel="noreferrer">{model.evidence_links[passage.record_id].label}</a>{/if}{/each}</details>{/if}</article>{/each}</section>
    <aside>{#if selectedMedia.length}<section class="source-media" aria-label="Selected source media"><h2>Check the original</h2>{#each selectedMedia as media (media.key)}<article><h3>{media.label} · {media.seconds.toFixed(1)}s</h3>{#if media.kind==='video'}<!-- Original source; no caption track is created by extraction. --><!-- svelte-ignore a11y_media_has_caption --><video controls playsinline preload="metadata" src={media.url} onloadedmetadata={event=>{event.currentTarget.currentTime=media.seconds;}}></video>{:else}<audio controls preload="metadata" src={media.url} onloadedmetadata={event=>{event.currentTarget.currentTime=media.seconds;}}></audio>{/if}<a href={media.url} target="_blank" rel="noreferrer">Open original source</a></article>{/each}<p class="provenance">The player shows the original file at the cited time. Extracted observations and identities still need review.</p></section>{/if}<h2>Evidence notes</h2>{#if selected}<p class="selected-context">Adding a note to <strong>{recordTitle(selected)}</strong></p><form onsubmit={event=>{event.preventDefault();save();}}><label>Evidence note<textarea bind:value={note} required maxlength="4000"></textarea></label><button disabled={!note.trim() || savingNote}>{savingNote ? 'Saving note…' : 'Save note'}</button></form>{:else}<p>Select a record to attach a note.</p>{/if}{#each notes as saved (saved.id)}<article><p>{saved.note}</p><small>{recordTitle(saved.record_snapshot)} · {saved.review_origin}</small></article>{/each}</aside></div>
  {:else}<p role="status">Loading source records…</p>{/if}
</main>
<style>
  .chart-viewport{max-width:100%;max-height:540px;overflow:auto;border:1px solid #d9ddd6;border-radius:14px;background:white}.chart-viewport .chart{border:0;border-radius:0;max-width:none}.chart-controls{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.chart-controls span{min-width:45px;text-align:center;font-size:12px}.chart-controls button:disabled{opacity:.45;cursor:default}.chart-viewport:focus-visible{outline:2px solid #566f42;outline-offset:2px}
  .date-explorer{border:1px solid #d9ddd6;border-radius:10px;padding:12px 16px;margin-bottom:16px}.date-explorer .filters{margin:12px 0}.undated-option{display:flex;align-items:center;gap:8px;font-size:12px}.undated-option input{width:auto;margin:0}.date-explorer [role=alert]{color:#ac3434}
  .record-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.record-heading h3{margin:0;font-size:16px;font-weight:600;overflow-wrap:anywhere}.record-heading button{flex-shrink:0;white-space:nowrap}.record-fields{margin:18px 0}.record-fields>div{display:grid;grid-template-columns:minmax(100px,1fr) minmax(0,2fr);gap:16px;padding:9px 0;border-bottom:1px solid #e5e7e0}.record-fields dt{color:#68736c;font-size:12px;overflow-wrap:anywhere}.record-fields dd{margin:0;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere}.record-fields .missing{color:#68736c;font-style:italic}.raw-data{margin:12px 0}summary{cursor:pointer;padding:5px 0}article.selected{border-color:#566f42;box-shadow:0 0 0 1px #566f42}.selected-context{padding:12px;background:#e5eadd;border-radius:7px}.table-scroll table{min-width:900px}

  .table-scroll{max-width:100%;overflow-x:auto;border:1px solid #d9ddd6;border-radius:10px}table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;padding:12px;border-bottom:1px solid #d9ddd6;vertical-align:top;overflow-wrap:break-word}th{font-size:12px}td:last-child{min-width:100px}.table-scroll button{white-space:nowrap;min-width:72px}

  :global(body){margin:0;background:#f4f1eb;color:#29352f;font:14px system-ui,sans-serif}*{box-sizing:border-box}main{max-width:1280px;margin:auto;padding:32px}h1{font-size:30px;font-weight:500;letter-spacing:-1px}h2{font-size:18px;font-weight:500}p{line-height:1.6}.eyebrow{font-size:10px;letter-spacing:.18em}.provenance,small{font-size:11px;color:#68736c}.chart{position:relative;background:white;border:1px solid #d9ddd6;border-radius:14px;padding:0}.node-target{position:absolute;width:24px;height:24px;min-width:0;padding:0;border:1px solid transparent;border-radius:50%;background:transparent;transform:translate(-50%,-50%)}.node-target:hover,.node-target.chosen{border:2px solid #a16d42;background:#a16d4222}.chart img{display:block;width:100%;height:auto}.filters{display:flex;gap:14px;flex-wrap:wrap;align-items:end;margin:24px 0}.filters label{flex:1;min-width:150px}input,select,textarea{display:block;width:100%;padding:10px;margin-top:8px;background:white;border:1px solid #d1d8ce;border-radius:7px;color:inherit;font:inherit}button{max-width:100%;overflow-wrap:anywhere;white-space:normal;background:#e5eadd;border:1px solid #cbd5c5;padding:10px 14px;border-radius:7px;color:inherit;cursor:pointer}button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:2px solid #566f42;outline-offset:2px}.panes{display:grid;grid-template-columns:1.3fr 1fr;gap:24px;align-items:start}.panes>section,.panes>aside{min-width:0}article{padding:14px;border:1px solid #d9ddd6;border-radius:10px;background:#faf9f5;margin-bottom:10px}blockquote{overflow-wrap:anywhere;margin:12px 0;padding-left:12px;border-left:2px solid #cbd5c5;font-size:12px;white-space:pre-wrap}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px}aside{position:sticky;top:15px}textarea{min-height:90px}form button{margin:10px 0}article p{white-space:pre-wrap;overflow-wrap:anywhere}@media(max-width:650px){main{padding:18px}.panes{grid-template-columns:1fr}aside{position:static}h1{font-size:24px}.chart{padding:0}}
.source-media video,.source-media audio{display:block;width:100%;max-height:300px;margin:12px 0}.source-media h3{font-size:13px;overflow-wrap:anywhere}.source-media a{font-size:12px}.source-media article{padding:12px}
</style>
