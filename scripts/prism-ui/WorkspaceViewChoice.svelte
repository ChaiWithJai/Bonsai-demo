<script lang="ts">
  let {fields,busy=false,onSelect}:{fields:{name:string;type:string}[];busy?:boolean;onSelect:(view:Record<string,unknown>)=>void}=$props();
  let component=$state('');let x=$state('');let y=$state('');let color=$state('');let groups=$state<string[]>([]);let columns=$state<string[]>([]);
  const numeric=$derived(fields.filter(field=>field.type==='number'));
  const coordinates=$derived(fields.filter(field=>field.type==='number'||field.type==='date'));
  const ready=$derived(component==='RecordTable' ? columns.length>0 && columns.length<=20 : component==='ForceDirectedGraph' ? groups.length>0 && groups.length<=3 : Boolean(component && x && y));
  function apply(){
    if(busy||!ready)return;
    onSelect(component==='RecordTable' ? {component,columns} : component==='ForceDirectedGraph' ? {component,groupBy:groups} : {component,x,y,color:color||null});
  }
</script>
<details class="saved-view-choice">
 <summary>Change the view using this data</summary>
 <p>Keep the saved records and citations. Select a chart and its fields, then review a new proposal before building. This makes no model call.</p>
 <label>Visualization<select bind:value={component} disabled={busy}><option value="">Choose a view</option><option value="RecordTable">Table</option><option value="Scatterplot">Scatterplot</option><option value="LineChart">Line chart</option><option value="ForceDirectedGraph">Groups and connections</option></select></label>
 {#if component==='RecordTable'}<label>Table columns<select multiple bind:value={columns} disabled={busy} size={Math.min(fields.length,6)}>{#each fields as field (field.name)}<option value={field.name}>{field.name.replaceAll('_',' ')}</option>{/each}</select></label><p>Choose up to 20 columns. All fields remain saved in the records.</p>
 {:else if component==='ForceDirectedGraph'}<label>Group by<select multiple bind:value={groups} disabled={busy} size={Math.min(fields.length,6)}>{#each fields as field (field.name)}<option value={field.name}>{field.name.replaceAll('_',' ')}</option>{/each}</select></label><p>Choose up to three fields. These are groups based on field values, not learned similarity clusters.</p>
 {:else if component}<div class="axes"><label>Horizontal axis<select bind:value={x} disabled={busy}><option value="">Choose date or number</option>{#each coordinates as field (field.name)}<option value={field.name}>{field.name.replaceAll('_',' ')}</option>{/each}</select></label><label>Vertical axis<select bind:value={y} disabled={busy}><option value="">Choose a number</option>{#each numeric as field (field.name)}<option value={field.name}>{field.name.replaceAll('_',' ')}</option>{/each}</select></label></div><label>Color groups<select bind:value={color} disabled={busy}><option value="">One group</option>{#each fields as field (field.name)}<option value={field.name}>{field.name.replaceAll('_',' ')}</option>{/each}</select></label><p>Missing coordinates remain in the records. Chart validation may require a different mapping; line charts cannot bridge missing values.</p>{/if}
 <button onclick={apply} disabled={busy||!ready}>Review selected view</button>
</details>
<style>
 details{border:1px solid var(--border);border-radius:10px;padding:12px 16px;margin:16px 0;font-size:12px;line-height:1.6}summary{cursor:pointer;font-weight:600}label{display:grid;gap:6px;margin:12px 0}select{box-sizing:border-box;width:100%;min-width:0;padding:10px;font:inherit;color:inherit;background:var(--background);border:1px solid var(--border);border-radius:7px}.axes{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}p{color:var(--muted-foreground)}button{font:inherit;padding:10px 14px;border:1px solid var(--border);border-radius:7px;background:var(--background);color:inherit;cursor:pointer}button:disabled{opacity:.5;cursor:default}button:focus-visible,select:focus-visible,summary:focus-visible{outline:2px solid var(--ring);outline-offset:3px}@media(max-width:600px){.axes{grid-template-columns:1fr;gap:0}}
</style>
