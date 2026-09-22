<script lang="ts">
  let {config}=$props<{config?:{profile:string;seed:number}|null}>();
  const labels:Record<string,string>={
    'legacy-greedy':'Greedy · thinking off',
    'bonsai2-instruct':'Instruct sampling · thinking off',
    'bonsai2-bounded':'Reasoning · 512-token allowance',
    'bonsai2-medium':'Reasoning · medium effort'
  };
</script>
<details aria-label="Recorded model configuration">
  <summary>Recorded model configuration</summary>
  {#if config}<p>{labels[config.profile] ?? config.profile} · Seed {config.seed}</p><p class="context">Saved for this result. Changing the composer settings applies to a new request.</p>{:else}<p>Configuration was not recorded for this result. Open its MLflow evidence for any available runtime details.</p>{/if}
</details>
<style>
  details{font-size:12px;margin:12px 0}summary{cursor:pointer;padding:6px 0}p{line-height:1.6;margin:6px 0}.context{color:var(--muted-foreground);font-size:11px}
</style>
