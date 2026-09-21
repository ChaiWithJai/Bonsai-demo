<script lang="ts">
  import type { SourceData, SourceRecord } from '$lib/workspace-data-types';
  let {source, selected = $bindable('')} = $props<{source:SourceData;selected?:string}>();
  const regions=$derived(source.records.filter((row:SourceRecord)=>Array.isArray(row.locator.bbox_normalized_bottom_left)));
  const current=$derived(regions.find((row:SourceRecord)=>row.id===selected));
  function regionStyle(value:unknown) {
    const [x,y,w,h]=value as number[];
    return `left:${x*100}%;top:${(1-y-h)*100}%;width:${w*100}%;height:${h*100}%`;
  }
</script>
<section class="image-evidence" aria-label="Image evidence">
  <h3>Check the text against the image</h3>
  <p>Select a passage or its outline to see where it came from. Use the review below to correct recognition errors.</p>
  <div class="image-stage">
    <img src={'/api/workspace/sources/'+source.source_id+'/file'} alt={'Original image: '+source.filename}/>
    {#each regions as row,i (row.id)}
      <button class="region" class:chosen={selected===row.id} style={regionStyle(row.locator.bbox_normalized_bottom_left)} aria-label={'Highlight passage '+(i+1)+': '+String(row.data.text)} aria-pressed={selected===row.id} onclick={()=>selected=row.id}></button>
    {/each}
  </div>
  <div class="passages" aria-label="Recognized passages">
    {#each regions as row,i (row.id)}
      <button class:chosen={selected===row.id} aria-pressed={selected===row.id} onclick={()=>selected=row.id}><span>{i+1}</span><span>{String(row.data.text)}</span></button>
    {/each}
  </div>
  {#if current}<p role="status">Selected passage {current.locator.region}. It is selected in the record review below.</p>{/if}
</section>
<style>
  .image-evidence{margin:22px 0}h3{font-size:16px;margin:0 0 10px}p{font-size:12px;line-height:1.6;color:var(--muted-foreground)}.image-stage{position:relative;width:100%;background:#fff;border:1px solid var(--border);border-radius:8px;overflow:hidden}.image-stage img{display:block;width:100%;height:auto}.region{position:absolute;padding:0;min-height:0;border:1px solid #94702e;background:#e9b94916;cursor:pointer}.region:hover,.region:focus-visible,.region.chosen{outline:2px solid #80621e;background:#f5c84c55;z-index:1}.passages{display:grid;gap:6px;max-height:320px;overflow:auto;margin-top:12px}.passages button{display:flex;gap:12px;text-align:left;padding:11px;border:1px solid var(--border);border-radius:7px;background:var(--background);color:inherit;cursor:pointer;font:inherit;line-height:1.5;overflow-wrap:anywhere}.passages button span:first-child{color:var(--muted-foreground);font-size:11px}.passages button.chosen{border-color:#94702e;background:#94702e12}button:focus-visible{outline:2px solid #94702e;outline-offset:2px}
</style>
