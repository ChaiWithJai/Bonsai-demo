<script lang="ts">
  let { sourceId, page } = $props<{ sourceId: string; page: number }>();
  let open = $state(false);
  let failed = $state(false);
  let loaded = $state(false);
</script>
<div class="pdf-page">
  <button type="button" aria-expanded={open} onclick={() => { open = !open; }}>
    {open ? 'Hide original page' : 'View original page'} {page}
  </button>
  {#if open}
    <p>Original PDF · page {page}. Compare the layout and labels with the extracted text.</p>
    {#if failed}
      <p role="alert">This page could not be rendered. Open the original PDF to inspect it.</p>
      <button type="button" onclick={() => { failed = false; loaded = false; }}>Retry page preview</button>
    {:else}
      {#if !loaded}<p role="status">Loading original page…</p>{/if}
      <a href={'/api/workspace/sources/' + sourceId + '/pages/' + page} target="_blank" rel="noreferrer" aria-label={'Open full-size image of page ' + page}>
        <img src={'/api/workspace/sources/' + sourceId + '/pages/' + page} alt={'Original PDF page ' + page} onload={() => { loaded = true; }} onerror={() => { failed = true; }}/>
      </a>
    {/if}
    <a href={'/api/workspace/sources/' + sourceId + '/file#page=' + page} target="_blank" rel="noreferrer">Open page {page} in the original PDF</a>
  {/if}
</div>
<style>
  .pdf-page{margin:12px 0}.pdf-page button{font:inherit;font-size:12px;border:1px solid var(--border);border-radius:8px;background:var(--card);color:var(--foreground);padding:8px 12px;cursor:pointer}.pdf-page p,.pdf-page>a{font-size:12px;line-height:1.6}.pdf-page img{display:block;width:100%;height:auto;background:white;border:1px solid var(--border);border-radius:8px;margin:12px 0}.pdf-page a{color:inherit}.pdf-page button:focus-visible,.pdf-page a:focus-visible{outline:2px solid var(--ring);outline-offset:3px}
</style>
