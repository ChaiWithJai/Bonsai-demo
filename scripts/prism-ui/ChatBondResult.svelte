<script lang="ts">
  let { raw, args }: { raw?: string; args?: string } = $props();
  type Inputs = {face:number; coupon_rate:number; annual_yield:number; periods:number; frequency:number};
  function decode() {
    try {
      const data = JSON.parse(raw ?? '');
      const inputs: Inputs = JSON.parse(args ?? '');
      if (data.status !== 'completed' || data.result?.calculation_version !== 'coupon-date-v1') return null;
      if (!Object.values(inputs).every(Number.isFinite) || inputs.face <= 0 || inputs.coupon_rate < 0 || ![1,2,4,12].includes(inputs.frequency) || !Number.isInteger(inputs.periods) || inputs.periods < 1 || inputs.periods > 1200 || 1+inputs.annual_yield/inputs.frequency <= 0) return null;
      return {data, inputs};
    } catch { return null; }
  }
  const saved = $derived(decode());
  let selected = $state(1);
  let shift = $state(0);
  const money = (n:number) => n.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
  const scenario = $derived.by(() => {
    if (!saved) return null;
    const i=saved.inputs, yieldRate=i.annual_yield+shift/10000, base=1+yieldRate/i.frequency;
    if(base<=0) return null;
    const payments=Array.from({length:i.periods},(_,index)=>{
      const period=index+1, cash=i.face*i.coupon_rate/i.frequency+(period===i.periods?i.face:0);
      return {period,years:period/i.frequency,cash,discount:base**(-period),pv:cash*base**(-period)};
    });
    const price=payments.reduce((sum,p)=>sum+p.pv,0);
    return Number.isFinite(price)?{price,payment:payments[Math.min(selected,i.periods)-1],yieldRate}:null;
  });
</script>

{#if saved && scenario}
  <section class="bond-result" aria-label="Explore bond cash flows">
    <header><span>Bond cash flows</span><strong>{money(scenario.price)}</strong><small>Present value · same currency as face</small></header>
    <p>{saved.inputs.periods} payments · {saved.inputs.frequency} per year · {(scenario.yieldRate*100).toFixed(2)}% annual yield</p>
    <label>Inspect payment {selected} of {saved.inputs.periods}<input type="range" min="1" max={saved.inputs.periods} step="1" bind:value={selected} aria-label="Inspect payment" /></label>
    <div class="equation" aria-live="polite"><span>Year {scenario.payment.years}</span><p>{money(scenario.payment.cash)} × {scenario.payment.discount.toFixed(6)} = <strong>{money(scenario.payment.pv)} today</strong></p><small>{selected===saved.inputs.periods?'Final coupon and principal':'Coupon payment'} discounted to today.</small></div>
    <details><summary>What if yield changes?</summary>
      <p>Predict the direction, then move the slider.</p>
      <label>Yield change: {shift>0?'+':''}{shift} basis points<input type="range" min="-200" max="200" step="25" bind:value={shift} aria-label="Yield change in basis points" /></label>
      <p aria-live="polite">Price change: <strong>{money(scenario.price-saved.data.result.price)}</strong></p>
      <button type="button" onclick={()=>shift=0}>Reset yield</button>
      <small>Illustrative browser calculation. The saved tool result and your confirmed inputs stay unchanged.</small>
    </details>
    <small>Regular coupon-date valuation. No accrued interest, irregular coupons or embedded options.</small>
  </section>
{/if}

<style>
  .bond-result{margin:14px 0;padding:18px;border:1px solid var(--border);border-radius:14px;background:var(--card);max-width:100%;font-variant-numeric:tabular-nums}
  header{display:grid;gap:3px}header>span{font-size:13px}header strong{font-size:30px;font-weight:600}p{font-size:13px;line-height:1.6;margin:10px 0}small{display:block;color:var(--muted-foreground);font-size:11px;line-height:1.5}
  label{display:grid;gap:10px;font-size:12px;margin:16px 0}input{width:100%;accent-color:#6c8061}.equation{padding:12px;background:var(--background);border-radius:9px}.equation>span{font-size:12px;color:var(--muted-foreground)}details{margin:16px 0;padding:12px 0;border-block:1px solid var(--border)}summary{cursor:pointer;font-size:13px}button{font-size:12px;border:1px solid var(--border);border-radius:8px;padding:7px 10px;margin-bottom:10px;cursor:pointer}input:focus-visible,button:focus-visible,summary:focus-visible{outline:2px solid var(--ring);outline-offset:3px}
</style>
