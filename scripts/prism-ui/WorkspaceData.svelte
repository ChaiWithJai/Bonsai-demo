<script lang="ts">
  import type { SourceData, SourceSummary } from '$lib/workspace-data-types';
  import { onMount } from 'svelte';
  import WorkspaceRecordReview from '$lib/WorkspaceRecordReview.svelte';
  let sources = $state<SourceSummary[]>([]);
  let source = $state<SourceData | null>(null);
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
    try { source = await request('/' + id); }
    catch (e) { error = String(e); }
  }
  async function upload(event: Event & {currentTarget: HTMLInputElement}) {
    const file = event.currentTarget.files?.[0];
    if (!file) return;
    busy = true; error = '';
    try {
      if (file.size > 25 * 1024 * 1024) throw new Error('Choose a file of at most 25 MiB');
      source = await request('', {method: 'POST', headers: {'Content-Type': 'application/octet-stream', 'X-Source-Filename': encodeURIComponent(file.name)}, body: file});
      await refresh();
    } catch (e) { error = String(e); }
    finally { busy = false; }
  }
  onMount(() => { refresh().catch(e => error = String(e)); });
</script>

<section class="data" aria-label="Desktop sources">
  <h2>Your source data</h2>
  <p>Keep the original file, inspect its records, and preserve corrections for the next model iteration.</p>
  <label class="upload">{busy ? 'Reading source…' : 'Add a desktop file'}<input type="file" accept=".csv,.tsv,.json,.jsonl,.txt,.md,.png,.jpg,.jpeg,.webp,.pdf,.wav,.mp3,.m4a,.mp4,.mov,.webm" onchange={upload} disabled={busy}/></label>
  <p class="fine">Up to 25 MiB. Tables and text are extracted locally. Media files are preserved; media extraction is not connected in this tab yet.</p>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  {#if sources.length}
    <label>Saved source<select value={source?.source_id ?? ''} onchange={event => choose(event.currentTarget.value)}><option value="" disabled>Choose a source</option>{#each sources as item (item.source_id)}<option value={item.source_id}>{item.filename} · {item.record_count} records</option>{/each}</select></label>
  {/if}
  {#if source}
    <article class="source-summary"><h3>{source.filename}</h3><p>{source.record_count} records · {source.kind} · {source.status.replaceAll('_', ' ')}</p><a href={'/api/workspace/sources/' + source.source_id + '/file'} download={source.filename}>Download original file</a><p class="fine">SHA256 {source.sha256}</p></article>
    {#if source.status === 'extracted'}
      <p class="fine">Previewing the first {source.records.length} of {source.record_count} records. Source IDs and locations are retained. This upload does not replace the current generated project.</p>
      <div class="records">{#each source.records.slice(0, 10) as row (row.id)}<details><summary>{JSON.stringify(row.locator)}</summary><pre>{JSON.stringify(row.data, null, 2)}</pre></details>{/each}</div>
      {#key source.source_id}<WorkspaceRecordReview {source} onSaved={() => source ? choose(source.source_id) : Promise.resolve()}/>{/key}
    {:else}<p>Original media is saved. Extracted records and review will appear once the media workflow is connected.</p>{/if}
  {/if}
</section>

<style>
  .data{padding:24px;overflow:auto;min-width:0;height:100%;font-size:13px}.data h2{font-size:20px;margin:0 0 10px}.data p{line-height:1.6}.fine{color:var(--muted-foreground);font-size:11px;overflow-wrap:anywhere}.upload{display:block;padding:16px;border:1px dashed var(--border);border-radius:10px;margin:18px 0}.upload input{display:block;margin-top:10px;max-width:100%}label{display:block}select{display:block;max-width:100%;width:100%;padding:10px;margin:8px 0;background:var(--background);border:1px solid var(--border);border-radius:8px}.source-summary{padding:14px;border:1px solid var(--border);border-radius:10px;margin-top:18px}.source-summary h3{margin:0;font-size:14px}.records details{border-bottom:1px solid var(--border);padding:10px 0}.records pre{white-space:pre-wrap;overflow-wrap:anywhere}.error{color:#ac3434}a{text-decoration:underline}
</style>
