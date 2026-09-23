<script lang="ts">
  let { isEmpty = false, onChooseFeature }: {
    isEmpty: boolean;
    onChoosePrompt?: (prompt: string) => void;
    onChooseFeature?: (prompt: string) => void;
  } = $props();
  const features = [{"title": "Bond math", "detail": "Bring your working. Explore the cash flows.", "prompt": "Help me work through bond math using the notes or whiteboard image I attach. First structure the face value, coupon, yield, remaining payments, and payment frequency. Leave missing or unreadable values unresolved. Show what you understood and ask me to confirm before calculating. Use calculate_bond for checked arithmetic after confirmation, and treasury_yields when I request current Treasury context. Keep the explanation and review in this conversation.", "tool": true}, {"title": "Document review", "detail": "Compare financial or legal evidence.", "prompt": "Help me review the financial or legal documents I attach. First ask which review I need. Compare the claims against the source passages, preserve dates, units and exceptions, and show unresolved questions. Ask for my review before drawing a conclusion. Use jev_evidence_check only when I explicitly request a cloud check. Keep the evidence and review in this conversation.", "tool": true}];
  async function choose(prompt: string) {
    await onChooseFeature?.(prompt);
    requestAnimationFrame(() => document.querySelector<HTMLTextAreaElement>('.conversation-chat-form textarea')?.focus());
  }
</script>

{#if isEmpty}
  <section class="prism-welcome" aria-label="New chat">
    <img class="prism-wordmark" src="/prism-brand/prism-logo.svg" alt="Prism ML" />
    <h1>What would you like to understand?</h1>
    <p>Add a file or start with a question.</p>
    <div class="examples" aria-label="Example prompts">
      <button type="button" onclick={() => choose(features[1].prompt)}>Compare documents</button>
      <button type="button" onclick={() => choose(features[0].prompt)}>Work through bond math</button>
    </div>
  </section>
{/if}

<style>
  .prism-welcome {text-align:center; width:min(760px,100%); margin-bottom:22px}
  .prism-wordmark {margin:0 auto 18px; width:105px; height:28px}
  .prism-welcome h1 {font-size:clamp(23px,3vw,32px); letter-spacing:-.035em; margin-bottom:10px}
  p {font-size:14px; color:var(--muted-foreground)}
  .examples {display:flex; justify-content:center; flex-wrap:wrap; gap:8px; margin-top:18px}
  button {font-size:12px; padding:7px 12px; border:1px solid var(--border); border-radius:20px; cursor:pointer; color:var(--muted-foreground); background:transparent}
  button:hover {color:var(--foreground); background:var(--card)}
  button:focus-visible {outline:2px solid var(--ring); outline-offset:2px}
</style>
