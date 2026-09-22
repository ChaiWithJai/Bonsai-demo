<script lang="ts">
  let {jobId,title}=$props<{jobId:string;title:string}>();
  let requested=$state(false);
  let loaded=$state(false);
  let failed=$state(false);
  let attempt=$state(0);
  function showPreview() {failed=false;loaded=false;attempt+=1;requested=true;}
</script>
<section aria-label="Proposed chart preview">
  <button type="button" onclick={showPreview} disabled={requested && !loaded && !failed}>{failed ? 'Retry chart preview' : requested ? 'Refresh chart preview' : 'Preview proposed chart'}</button>
  {#if requested}
    {#if failed}<p role="alert">The chart preview could not load. Try again or ask Bonsai to revise the view.</p>{:else}
      {#if !loaded}<p role="status">Preparing chart preview…</p>{/if}
      <img src={'/api/workspace/source-jobs/'+jobId+'/proposal-preview?attempt='+attempt} alt={'Proposed chart: '+title} onload={()=>loaded=true} onerror={()=>failed=true}/>
    {/if}
  {/if}
  <p class="caption">Review the layout before building. Record selection and annotations are available in the built view.</p>
</section>
<style>
  section{margin:16px 0}button{padding:11px 14px;border:1px solid var(--border);border-radius:8px;background:var(--background);color:inherit;cursor:pointer}button:disabled{opacity:.5;cursor:default}img{display:block;width:100%;height:auto;margin:12px 0;border:1px solid var(--border);border-radius:8px;background:white}.caption{font-size:11px;color:var(--muted-foreground);line-height:1.6}p[role=alert]{font-size:12px}
</style>
