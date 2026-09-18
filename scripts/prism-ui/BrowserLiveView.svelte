<script lang="ts">
  import { page } from '$app/state';
  import { conversationsStore, mcpStore } from '$lib/stores';
  import { Monitor, ChevronDown, ChevronUp, Pause, Play } from '@lucide/svelte';
  import { onMount } from 'svelte';

  let endpoint = $state('');
  let expanded = $state(true);
  let paused = $state(false);
  let view = $state<Record<string, any> | null>(null);
  let failure = $state('');
  let visible = $state(true);
  const session = $derived(page.params.id ?? '');
  const enabled = $derived(mcpStore.getServers().some(server => server.url === endpoint &&
    conversationsStore.preferences.getMcpServerOverride(server.id)?.enabled));

  onMount(() => {
    fetch('/bonsai-recording-status').then(response => response.json()).then(data => {
      endpoint = data.browseros_endpoint || '';
    }).catch(() => {});
    const update = () => { visible = document.visibilityState === 'visible'; };
    update();
    document.addEventListener('visibilitychange', update);
    return () => document.removeEventListener('visibilitychange', update);
  });

  $effect(() => {
    const id = session;
    view = null;
    failure = '';
    if (!id || !enabled || !expanded || paused || !visible) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function poll() {
      try {
        const response = await fetch(`/api/browser-view/${encodeURIComponent(id)}`, {
          cache: 'no-store', signal: controller.signal
        });
        if (!response.ok) throw new Error(`Browser view unavailable (${response.status})`);
        const result = await response.json();
        if (!cancelled) { view = result; failure = ''; }
      } catch (error) {
        if (!cancelled) failure = error instanceof Error ? error.message : 'Browser view unavailable';
      } finally {
        if (!cancelled) timer = setTimeout(poll, 2000);
      }
    }
    void poll();
    return () => { cancelled = true; controller.abort(); clearTimeout(timer); };
  });
  const safeImage = $derived(typeof view?.image_data_url === 'string' && /^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(view.image_data_url) ? view.image_data_url : '');
</script>

{#if session && enabled}
  <aside class="browser-live" aria-label="BrowserOS live view">
    <header>
      <button class="browser-live-toggle" onclick={() => { expanded = !expanded; }} aria-expanded={expanded}>
        <Monitor size={16}/><strong>BrowserOS · Agent view</strong>
        {#if expanded}<ChevronDown size={15}/>{:else}<ChevronUp size={15}/>{/if}
      </button>
      {#if expanded}<button class="browser-live-pause" onclick={() => { paused = !paused; }} aria-label={paused ? 'Resume browser view' : 'Pause browser view'}>{#if paused}<Play size={14}/>{:else}<Pause size={14}/>{/if}</button>{/if}
    </header>
    {#if expanded}
      <div class="browser-live-body">
        {#if paused}<p>Browser view paused.</p>
        {:else if failure}<p role="status">{failure}</p>
        {:else if safeImage}
          <img src={safeImage} alt="Current viewport of the page used by the agent"/>
          <div class="browser-live-caption"><strong>{view?.title || `Page ${view?.page_id}`}</strong><span>{view?.url || ''}</span></div>
          <small>Live snapshots · refreshed every 2 seconds · {view?.captured_at ? new Date(view.captured_at * 1000).toLocaleTimeString() : ''}</small>
        {:else}<p role="status">{view?.message || 'Waiting for an agent browser action in this conversation.'}</p>{/if}
        <small>Shows the page used by this chat. No desktop capture.</small>
      </div>
    {/if}
  </aside>
{/if}

<style>
  .browser-live { position:fixed; right:1rem; top:4.5rem; z-index:45; width:min(380px,calc(100vw - 6rem)); border:1px solid var(--border); border-radius:16px; background:var(--background); color:var(--foreground); box-shadow:0 12px 35px #0002; overflow:hidden; }
  header { display:flex; align-items:center; padding:8px; gap:4px; }
  button { cursor:pointer; border-radius:8px; padding:8px; }
  button:hover { background:var(--muted); }
  .browser-live-toggle { display:flex; align-items:center; gap:8px; flex:1; text-align:left; font-size:12px; }
  .browser-live-toggle strong { flex:1; }
  .browser-live-body { padding:0 12px 12px; }
  img { width:100%; max-height:48vh; object-fit:contain; background:#f4f1ed; border-radius:8px; }
  p { font-size:12px; line-height:1.5; padding:10px 0; }
  small { display:block; font-size:10px; opacity:.65; margin-top:6px; }
  .browser-live-caption { display:flex; flex-direction:column; gap:3px; font-size:11px; margin-top:8px; }
  .browser-live-caption span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; opacity:.65; }
</style>
