<script>
  import { onMount } from 'svelte';
  let model = $state(null);
  let selected = $state(null);
  let group = $state('');
  let search = $state('');
  let note = $state('');
  let notes = $state([]);
  let error = $state('');
  const visible = $derived((model?.rows ?? []).filter(row => (!group || model.node_membership[group]?.includes(row.id)) && JSON.stringify(row.data).toLowerCase().includes(search.toLowerCase())));
  function locationLabel(locator) {
    if(locator.structured_record)return 'Structured record '+locator.structured_record;
    if(locator.page)return 'Page '+locator.page;
    if(locator.time_seconds !== undefined)return 'Video at '+Number(locator.time_seconds).toFixed(1)+'s';
    if(locator.start_seconds !== undefined)return 'Audio at '+Number(locator.start_seconds).toFixed(1)+'s';
    if(locator.line)return 'Line '+locator.line;
    if(locator.record)return 'Record '+locator.record;
    return 'Source record';
  }
  async function api(path, body) {
    const response = await fetch(path, body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Request failed');
    return result;
  }
  onMount(() => { Promise.all([api('/api/desktop'),api('/api/annotations')]).then(([data,saved])=>{model=data;notes=saved;}).catch(e=>error=String(e)); });
  async function save() {
    try { const saved=await api('/api/annotations',{record_id:selected.id,note});notes=[...notes,saved];note=''; }
    catch(e){error=String(e);}
  }
</script>
<main>
  {#if error}<p role="alert">{error}</p>{/if}
  {#if model}
    <header><p class="eyebrow">BONSAI / YOUR DATA</p><h1>{model.plan.title}</h1><p>{model.plan.summary}</p><p class="provenance">{model.rows.length} {model.record_origin === 'model_structured_unreviewed' ? 'model-structured records' : 'source records'} · {model.chart.component === 'RecordTable' ? 'Source record table' : 'Semiotic ' + model.chart.component} {#if model.chart.component !== 'RecordTable'}· {model.excluded_record_ids.length} records without plotted coordinates{/if}</p></header>
    {#if model.chart.component === 'RecordTable'}
      <!-- Keyboard users must be able to focus and scroll a wide source table. -->
      <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
      <div class="table-scroll" tabindex="0" role="region" aria-label="Source record table"><table><thead><tr>{#each model.chart.props.columns as column (column)}<th scope="col">{column.replaceAll("_", " ")}</th>{/each}<th scope="col">Evidence</th></tr></thead><tbody>{#each visible as row (row.id)}<tr data-table-record-id={row.id}>{#each model.chart.props.columns as column (column)}<td>{row.data[column] == null ? 'Missing' : String(row.data[column])}</td>{/each}<td><button onclick={()=>selected=row} aria-label={'Review table record '+row.id}>Review</button></td></tr>{/each}</tbody></table></div>
      <p class="provenance">Showing {model.chart.props.columns.length} overview fields. All fields and source passages remain in record details below.</p>
    {:else}
    <section class="chart" aria-label="Data visualization"><img src="/api/chart.svg" alt={model.plan.title}/>{#each model.interaction?.nodes ?? [] as node (node.id)}<button class="node-target" class:chosen={group === node.id} style:left={(node.x / model.interaction.width * 100) + '%'} style:top={(node.y / model.interaction.height * 100) + '%'} aria-label={'Explore '+node.label} title={node.label} onclick={()=>group=node.id}></button>{/each}</section>
    {/if}
    <p class="provenance">{model.grouping_origin}. Model field types and view choices need review.</p>
    <div class="filters"><label>Search records<input bind:value={search} type="search"/></label>{#if model.chart.component === 'ForceDirectedGraph'}<label>Group<select aria-label="Group" bind:value={group}><option value="">All records</option>{#each model.chart.props.nodes as node (node.id)}<option value={node.id}>{node.label} ({model.node_membership[node.id].length})</option>{/each}</select></label>{/if}<button onclick={()=>{group='';search='';}}>Clear filters</button></div>
    <div class="panes"><section aria-label="Source records"><h2>Records <small>{visible.length}</small></h2>{#each visible as row (row.id)}<article data-testid="record-row" data-record-id={row.id}><button onclick={()=>selected=row} aria-label={'Inspect '+row.id}>{String(row.data.model ?? row.data.title ?? locationLabel(row.locator))}</button><pre data-testid="record-data">{JSON.stringify(row.data,null,2)}</pre>{#if row.locator.source_evidence}<details><summary>Supporting source passages</summary>{#each row.locator.source_evidence as passage,i (i)}<blockquote>{passage.quote}</blockquote>{/each}</details>{/if}</article>{/each}</section>
    <aside><h2>Evidence notes</h2>{#if selected}<p>Selected: {locationLabel(selected.locator)}</p><form onsubmit={event=>{event.preventDefault();save();}}><label>Evidence note<textarea bind:value={note} required maxlength="4000"></textarea></label><button disabled={!note.trim()}>Save note</button></form>{:else}<p>Select a record to attach a note.</p>{/if}{#each notes as saved (saved.id)}<article><p>{saved.note}</p><small>{locationLabel(saved.record_snapshot.locator)} · {saved.review_origin}</small></article>{/each}</aside></div>
  {:else}<p role="status">Loading source records…</p>{/if}
</main>
<style>
  .table-scroll{max-width:100%;overflow-x:auto;border:1px solid #d9ddd6;border-radius:10px}table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;padding:12px;border-bottom:1px solid #d9ddd6;vertical-align:top;overflow-wrap:anywhere}th{font-size:12px}td:last-child{min-width:90px}

  :global(body){margin:0;background:#f4f1eb;color:#29352f;font:14px system-ui,sans-serif}*{box-sizing:border-box}main{max-width:1280px;margin:auto;padding:32px}h1{font-size:30px;font-weight:500;letter-spacing:-1px}h2{font-size:18px;font-weight:500}p{line-height:1.6}.eyebrow{font-size:10px;letter-spacing:.18em}.provenance,small{font-size:11px;color:#68736c}.chart{position:relative;background:white;border:1px solid #d9ddd6;border-radius:14px;padding:0}.node-target{position:absolute;width:24px;height:24px;min-width:0;padding:0;border:1px solid transparent;border-radius:50%;background:transparent;transform:translate(-50%,-50%)}.node-target:hover,.node-target.chosen{border:2px solid #a16d42;background:#a16d4222}.chart img{display:block;width:100%;height:auto}.filters{display:flex;gap:14px;flex-wrap:wrap;align-items:end;margin:24px 0}.filters label{flex:1;min-width:150px}input,select,textarea{display:block;width:100%;padding:10px;margin-top:8px;background:white;border:1px solid #d1d8ce;border-radius:7px;color:inherit;font:inherit}button{max-width:100%;overflow-wrap:anywhere;white-space:normal;background:#e5eadd;border:1px solid #cbd5c5;padding:10px 14px;border-radius:7px;color:inherit;cursor:pointer}button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:2px solid #566f42;outline-offset:2px}.panes{display:grid;grid-template-columns:1.3fr 1fr;gap:24px;align-items:start}.panes>section,.panes>aside{min-width:0}article{padding:14px;border:1px solid #d9ddd6;border-radius:10px;background:#faf9f5;margin-bottom:10px}blockquote{overflow-wrap:anywhere;margin:12px 0;padding-left:12px;border-left:2px solid #cbd5c5;font-size:12px;white-space:pre-wrap}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px}aside{position:sticky;top:15px}textarea{min-height:90px}form button{margin:10px 0}article p{white-space:pre-wrap;overflow-wrap:anywhere}@media(max-width:650px){main{padding:18px}.panes{grid-template-columns:1fr}aside{position:static}h1{font-size:24px}.chart{padding:0}}
</style>
