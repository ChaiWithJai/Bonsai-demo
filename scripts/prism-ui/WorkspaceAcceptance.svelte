<script lang="ts">
  type Check = {target: {role?: string; name?: string; test_id?: string}; action: string; value: number | boolean | null};
  let {checks = $bindable<Check[]>([]), disabled = false}: {checks?: Check[]; disabled?: boolean} = $props();
  function setKind(index: number, kind: string) {
    checks = checks.map((check, i) => i !== index ? check : kind === 'records'
      ? {target: {test_id: 'record-row'}, action: 'count', value: 0}
      : kind === 'click' || kind === 'pressed'
      ? {target:{role:'button',name:''},action:kind,value:kind === 'click' ? null : true}
      : {target: {role: kind, name: ''}, action: 'visible', value: true});
  }
</script>
<details class="expectations">
  <summary>Expected results{#if checks.length} <span>({checks.length})</span>{/if}</summary>
  <p>Add steps in the order they should run. Include at least one expected outcome. Bonsai will see them, and failed checks will return to the repair loop.</p>
  {#each checks as check, i (i)}
    <div class="check-row">
      <label>Check {i + 1}
        <select disabled={disabled} value={check.target.test_id ? 'records' : ['click','pressed'].includes(check.action) ? check.action : check.target.role} onchange={event => setKind(i, event.currentTarget.value)}>
          <option value="heading">Heading is visible</option><option value="button">Button is visible</option><option value="textbox">Input is visible</option><option value="records">Number of records</option><option value="click">Click a button</option><option value="pressed">Button selection state</option>
        </select>
      </label>
      {#if check.action === 'count'}
        <label>Expected count<input type="number" min="0" max="100000" step="1" required disabled={disabled} value={Number(check.value)} oninput={event => checks = checks.map((item,j) => j === i ? {...item,value:event.currentTarget.valueAsNumber} : item)}/></label>
      {:else}
        <label>Exact label<input type="text" maxlength="200" required disabled={disabled} bind:value={check.target.name} placeholder={check.target.role === 'heading' ? 'Release timeline' : check.target.role === 'button' ? 'Clear filters' : 'Search records'}/></label>
      {/if}
      {#if check.action==='pressed'}<label>Expected selection<select disabled={disabled} value={String(check.value)} onchange={event=>checks=checks.map((item,j)=>j===i ? {...item,value:event.currentTarget.value==='true'} : item)}><option value="true">Selected</option><option value="false">Not selected</option></select></label>{/if}
      <button type="button" disabled={disabled} aria-label={'Remove check '+(i+1)} onclick={() => checks = checks.filter((_,j) => j !== i)}>Remove</button>
    </div>
  {/each}
  <button type="button" disabled={disabled || checks.length >= 20} onclick={() => checks = [...checks,{target:{role:'heading',name:''},action:'visible',value:true}]}>Add expected result</button>
  <small>Checks run on desktop and mobile. Your review still covers interpretation and design quality.</small>
</details>
<style>
  .expectations{font-size:12px;border:1px solid var(--border);border-radius:9px;padding:10px;margin-bottom:12px}.expectations[open]{max-height:280px;overflow-y:auto}summary{cursor:pointer;font-weight:500}p{line-height:1.5;color:var(--muted-foreground)}.check-row{display:grid;gap:8px;padding:12px 0;border-top:1px solid var(--border)}label{display:grid;gap:5px}input,select{box-sizing:border-box;min-width:0;width:100%;font:inherit;color:inherit;background:var(--card);border:1px solid var(--border);border-radius:6px;padding:8px}button{font:inherit;color:inherit;background:var(--card);border:1px solid var(--border);border-radius:6px;padding:8px;cursor:pointer;justify-self:start}small{display:block;margin-top:10px;line-height:1.5;color:var(--muted-foreground)}button:disabled{opacity:.5;cursor:default}button:focus-visible,select:focus-visible,input:focus-visible,summary:focus-visible{outline:2px solid var(--ring);outline-offset:2px}
</style>
