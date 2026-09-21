<script lang="ts">
  let {jobId}: {jobId:string} = $props();
  let review = $state<any>(null);
  let author = $state('');
  let reviewerKind = $state('human');
  let note = $state('');
  let error = $state('');
  let busy = $state(false);
  async function api(suffix:string, body?:object) {
    const response=await fetch('/api/workspace/source-jobs/'+jobId+suffix,body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {cache:'no-store'});
    const result=await response.json();
    if(!response.ok)throw new Error(result.error ?? 'Review request failed');
    return result;
  }
  async function load() {
    busy=true;error='';
    try {review=await api('/reviews');}catch(e){error=String(e);}finally{busy=false;}
  }
  async function judge(action:string) {
    if(!review || busy)return;
    busy=true;error='';
    try {
      await api('/reviews',{proposal_sha256:review.proposal_sha256,source_snapshot_sha256:review.source_snapshot_sha256,input_sha256:review.input_sha256,
        previous_event_id:review.latest?.event_id ?? null,author,reviewer_kind:reviewerKind,action,note});
      review=await api('/reviews');note='';
    }catch(e){error=String(e);}finally{busy=false;}
  }
</script>
<details class="proposal-review" ontoggle={event=>{if(event.currentTarget.open && !review && !busy)void load();}}>
  <summary>Review interpretation for the example dataset</summary>
  <p>Judge the proposed structure against its source passages and uncertainties. This review is separate from permission to build the view.</p>
  {#if review}
    {#if review.latest}<p role="status">Saved {review.latest.action} judgment by {review.latest.author} ({review.latest.reviewer_kind}).</p><blockquote>{review.latest.note}</blockquote>{:else}<p>No judgment saved for this version.</p>{/if}
    {#if !review.eligible_version}<p>A revised proposal is available. Review that version instead.</p>{:else}
      <label>Proposal reviewer<input bind:value={author} maxlength="100" disabled={busy}/></label>
      <label>Proposal reviewer kind<select bind:value={reviewerKind} disabled={busy}><option value="human">Human</option><option value="codex">Codex</option><option value="test">Test</option></select></label>
      <label>Interpretation review note<textarea bind:value={note} maxlength="4000" disabled={busy} placeholder="Are the classifications and relationships supported? What is missing or uncertain?"></textarea></label>
      <div class="judgments">{#each [['accept','Accept interpretation'],['reject','Reject interpretation'],['defer','Defer judgment']] as [action,label] (action)}<button disabled={busy || !author.trim() || !note.trim()} onclick={()=>judge(action)}>{label}</button>{/each}</div>
    {/if}
    <a href={'/api/workspace/source-jobs/'+jobId+'/review-export'} download={'proposal-review-'+jobId+'.json'}>Download reviewed example bundle</a>
    <p class="fine">Only the latest human acceptance of the current version is eligible. Test and Codex judgments are excluded. Reviewer identity is self-declared; no training runs here.</p>
  {:else if busy}<p role="status">Loading review…</p>{/if}
  {#if error}<p role="alert">{error}</p><button disabled={busy} onclick={load}>Reload review</button>{/if}
</details>
<style>
  .proposal-review{border-top:1px solid var(--border);margin-top:16px;padding-top:12px;font-size:12px}summary{cursor:pointer}p{line-height:1.6}label{display:grid;gap:6px;margin:10px 0}input,textarea,select{box-sizing:border-box;max-width:100%;width:100%;font:inherit;background:var(--background);color:inherit;border:1px solid var(--border);border-radius:6px;padding:8px}textarea{min-height:90px}.judgments{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}button{font:inherit;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:inherit;cursor:pointer}button:disabled{opacity:.5;cursor:default}blockquote{margin:12px 0;border-left:2px solid var(--border);padding-left:12px;white-space:pre-wrap;overflow-wrap:anywhere}.fine{color:var(--muted-foreground)}a{text-decoration:underline}[role=alert]{color:#ac3434}button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,summary:focus-visible{outline:2px solid var(--ring);outline-offset:2px}
</style>
