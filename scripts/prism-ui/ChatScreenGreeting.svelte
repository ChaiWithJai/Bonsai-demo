<script lang="ts">
  let { isEmpty = false, onChoosePrompt }: {
    isEmpty: boolean;
    onChoosePrompt?: (prompt: string) => void;
  } = $props();
  const workflows = [
    {number: '01', title: 'Hand off an account', detail: 'People, promises and the next step.', prompt: 'Help me prepare an account handoff. First ask which account, the outgoing and incoming owners, and the handoff date. Then use only the email threads and resources I authorize. Separate confirmed facts from gaps; include source links, open commitments, and next actions. Draft only; do not send messages.'},
    {number: '02', title: 'Find a reason to reconnect', detail: 'A timely signal. A thoughtful follow-up.', prompt: 'Help me re-engage an existing account. First ask which account and which prior thread to use. Verify one recent public announcement, connect it cautiously to our actual relationship, then draft three short nurturing touches with relative timing and stop-on-reply rules. Do not invent previous conversations or schedule or send anything.'},
    {number: '03', title: 'Bring the context together', detail: 'Turn scattered sources into a useful brief.', prompt: 'Help me assemble an account brief from sources I authorize. First identify the account and available sources. Organize people, relationship history, useful resource links, unresolved questions, and recommended next steps. Cite the source for each factual claim and label proposals clearly.'}
  ];
</script>

{#if isEmpty}
  <section class="prism-welcome" aria-label="Bonsai workspace">
    <img class="prism-wordmark" src="/prism-brand/prism-logo.svg" alt="Prism ML" />
    <p class="prism-eyebrow">BONSAI · YOUR WORK, IN CONTEXT</p>
    <p class="prism-intro">what can i take off your plate?</p>
    <div class="prism-workflows">
      {#each workflows as workflow}
        <button type="button" class="prism-workflow" onclick={() => onChoosePrompt?.(workflow.prompt)}>
          <span class="prism-workflow-number">{workflow.number}<span aria-hidden="true">↗</span></span>
          <strong>{workflow.title}</strong>
          <span>{workflow.detail}</span>
        </button>
      {/each}
    </div>
  </section>
{/if}
