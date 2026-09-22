<script lang="ts">
  import { untrack } from 'svelte';
  import type { SourceData, ReviewExport } from '$lib/workspace-data-types';
  let { source, onSaved, initialRecordId = '' }: {source: SourceData; onSaved: () => Promise<void>;initialRecordId?:string} = $props();
  let recordId = $state(untrack(()=>initialRecordId));
  let author = $state('');
  let reviewerKind = $state('human');
  let action = $state('accept');
  let correction = $state(untrack(()=>['image','audio'].includes(source.kind) ? String(source.records.find(row=>row.id===initialRecordId)?.data.text ?? '') : JSON.stringify(source.records.find(row=>row.id===initialRecordId)?.data ?? {},null,2)));
  let note = $state('');
  let error = $state('');
  let status = $state('');
  let busy = $state(false);
  let exported = $state<ReviewExport | null>(null);
  const record = $derived(source.records.find(row => row.id === recordId));
  const previous = $derived(source.review.latest[recordId]);
  function chooseRecord(event: Event & {currentTarget: HTMLSelectElement}) {
    recordId = event.currentTarget.value;
    const row = source.records.find(item => item.id === recordId);
    correction = row ? (['image','audio'].includes(source.kind) ? String(row.data.text ?? '') : JSON.stringify(row.data, null, 2)) : '';
    note = ''; error = ''; status = ''; exported = null;
  }
  async function request(path: string, body: Record<string, unknown>) {
    const response = await fetch(path, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Could not save review');
    return result;
  }
  async function saveReview() {
    busy = true; error = ''; status = ''; exported = null;
    try {
      await request('/api/workspace/sources/' + source.source_id + '/review', {source_id:source.source_id,snapshot_id:source.review.snapshot_id,
        record_id:recordId,previous_event_id:previous?.event_id ?? null,author,reviewer_kind:reviewerKind,
        action,note,corrected_data:action === 'correct' ? (['image','audio'].includes(source.kind) ? {...record?.data,text:correction} : JSON.parse(correction)) : null});
      await onSaved();
      status = 'Review saved. Original extraction and earlier reviews are preserved.';
    } catch(e) {error = String(e);}
    finally {busy = false;}
  }
  async function exportReviews() {
    busy = true; error = '';
    try {exported = await request('/api/workspace/sources/' + source.source_id + '/export', {source_id:source.source_id});}
    catch(e) {error = String(e);}
    finally {busy = false;}
  }
</script>

<details class="record-review" open={Boolean(record)}>
  <summary>Review records and export corrections</summary>
  <p>Check the original source, then accept, correct or reject a record. Reviews are separate from the extraction and current chart.</p>
  <label for="review-record">Source record</label>
  <select id="review-record" value={recordId} onchange={chooseRecord}>
    <option value="">Choose a record on this page</option>
    {#each source.records as row, index (row.id)}<option value={row.id}>Record {(source.record_offset ?? 0) + index + 1} · {['image','audio'].includes(source.kind) ? (source.kind==='audio' ? String(row.locator.start_seconds)+'s' : 'Passage '+row.locator.region) : JSON.stringify(row.locator)}</option>{/each}
  </select>
  <p class="fine">Showing {source.records.length} records starting at {(source.record_offset ?? 0)+1}. {Object.keys(source.review.latest).length} records reviewed in this extraction version.</p>
  {#if record}
    {#if ['image','audio'].includes(source.kind)}<blockquote>{String(record.data.text)}</blockquote>{:else}<pre>{JSON.stringify(record.data, null, 2)}</pre>{/if}
    {#if previous}<p>Latest review: {previous.action} by {previous.author} ({previous.reviewer_kind}). {previous.note}</p>{/if}
    <label for="review-author">Reviewer name</label><input id="review-author" bind:value={author} maxlength="100" />
    <label for="review-kind">Reviewer type</label><select id="review-kind" bind:value={reviewerKind}><option value="human">Human review</option><option value="codex">Codex provisional review</option><option value="test">Automated test</option></select>
    <label for="review-action">Decision</label><select id="review-action" bind:value={action}><option value="accept">Accept source values</option><option value="correct">Correct values</option><option value="reject">Reject record</option></select>
    {#if action === 'correct'}<label for="review-correction">{['image','audio'].includes(source.kind) ? 'Corrected text' : 'Corrected record JSON'}</label><textarea id="review-correction" bind:value={correction} rows="8" spellcheck="false"></textarea>{/if}
    <label for="review-note">Evidence and reason</label><textarea id="review-note" bind:value={note} rows="3" maxlength="4000" placeholder="Refer to the page, frame, speech interval or source link that supports your decision."></textarea>
    <button onclick={saveReview} disabled={busy || !author.trim() || !note.trim()}>Save record review</button>
  {/if}
  {#if error}<p role="alert">{error}</p>{/if}
  {#if status}<p role="status">{status}</p>{/if}
  <button onclick={exportReviews} disabled={busy}>Export correction dataset</button>
  {#if exported}<p><a href={exported.url} download="record-reviews.json">Download review dataset</a> · <a href={exported.run_url} target="_blank" rel="noreferrer">MLflow export</a></p><p>{exported.training_candidates} human-declared training candidates. No training has run.</p>{/if}
  <p class="fine">Exports retain every review. Training candidates include only the latest human-declared accepted or corrected records from this extraction version. Reviewer names are self-declared locally. Codex feedback, tests, rejected and unreviewed records are excluded.</p>
</details>

<style>
  .record-review {margin:1rem 0;padding:1rem;border:1px solid #cfd8c8;border-radius:10px;min-width:0;}
  summary {font-weight:600;cursor:pointer;}
  label {display:block;margin:1rem 0 .4rem;font-size:.85rem;font-weight:600;}
  input,select,textarea {box-sizing:border-box;max-width:100%;width:100%;padding:.7rem;border:1px solid #c8d2c3;border-radius:6px;font:inherit;background:white;color:#203b2b;}
  pre {white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f4ed;padding:.7rem;max-height:300px;overflow:auto;}
  button {display:block;margin:1rem 0;padding:.7rem 1rem;border:1px solid #9aa993;border-radius:6px;background:#eef4e8;color:#203b2b;cursor:pointer;}
  button:disabled {opacity:.5;cursor:default;}
  p {line-height:1.5;overflow-wrap:anywhere;}
  .fine {font-size:.8rem;color:#53634f;}
  [role='alert'] {color:#a52626;}
  a {color:#275b31;}
</style>
