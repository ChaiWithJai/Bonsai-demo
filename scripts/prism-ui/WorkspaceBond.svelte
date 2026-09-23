<script lang="ts">
  import { onMount } from 'svelte';
  type Data = Record<string, any>;
  let session = $state<Data | null>(null);
  let panel = $state('working');
  let working = $state('');
  let face = $state(1000);
  let coupon = $state(5);
  let yieldPercent = $state(5);
  let periods = $state(20);
  let frequency = $state(2);
  let prediction = $state('');
  let shock = $state(25);
  let selectedPayment = $state(1);
  let busy = $state(false);
  let error = $state('');
  const actions = $derived(session?.actions ?? []);
  const calculations = $derived(actions.filter((a:Data)=>a.operation==='calculate_bond' && a.status==='completed'));
  const latest = $derived(calculations.at(-1));
  const treasury = $derived(actions.findLast((a:Data)=>a.operation==='fetch_treasury' && a.status==='completed'));
  const payment = $derived(latest?.result.payments.find((p:Data)=>p.period===selectedPayment));
  const previous = $derived(calculations.length > 1 ? calculations.at(-2) : null);
  const money = (n:number) => new Intl.NumberFormat('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}).format(n);
  async function api(path:string, body?:Data) {
    const response = await fetch('/api/workspace/learning'+path, body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {cache:'no-store'});
    const data = await response.json();
    if(!response.ok) throw new Error(data.error ?? 'Learning action failed');
    return data;
  }
  async function restore() {
    const id=localStorage.getItem('bonsai-bond-learning');
    if(id) {
      session=await api('/'+id);
      const saved=session?.actions.findLast((a:Data)=>a.operation==='calculate_bond' && a.status==='completed');
      if(saved) {face=saved.request.inputs.face;coupon=saved.request.inputs.coupon_rate*100;yieldPercent=Number((saved.request.inputs.annual_yield*100).toFixed(8));periods=saved.request.inputs.periods;frequency=saved.request.inputs.frequency;working=saved.request.working ?? '';}
    }
  }
  onMount(()=>{restore().catch(e=>error=String(e));});
  async function act(body:Data) {
    busy=true;error='';
    try {
      if(!session) {session=await api('',{kind:'bond_math'});localStorage.setItem('bonsai-bond-learning',session!.id);}
      const result=await api('/'+session!.id+'/actions',body);
      session=await api('/'+session!.id);
      if(result.status==='failed') throw new Error(result.error);
      return result;
    } catch(e) {error=String(e);return null;} finally {busy=false;}
  }
  async function calculate(event:SubmitEvent) {
    event.preventDefault();
    const result=await act({operation:'calculate_bond',confirmed:true,working,
      inputs:{face,coupon_rate:coupon/100,annual_yield:yieldPercent/100,periods,frequency}});
    if(result) {selectedPayment=1;panel='payments';}
  }
  async function reprice() {
    if(!latest || !prediction.trim()) return;
    const result=await act({operation:'calculate_bond',confirmed:true,working,prediction,
      comparison_base_action_id:latest.id,shock_basis_points:shock,
      inputs:{...latest.request.inputs,annual_yield:latest.request.inputs.annual_yield+shock/10000}});
    if(result) {yieldPercent=Number((result.request.inputs.annual_yield*100).toFixed(8));prediction='';}
  }
</script>

<section class="bond" aria-label="Bond math learning workstream">
  <div class="intro"><p class="eyebrow">LEARN THROUGH YOUR WORKING</p><h2>Where does a bond’s price come from?</h2><p>Confirm the cash flows. Follow each payment into today’s value. Predict a change before revealing it.</p></div>
  <nav aria-label="Bond learning views">{#each [['working','Your working'],['payments','Cash flows'],['market','Treasury context'],['evidence','Activity']] as item (item[0])}<button class:active={panel===item[0]} aria-pressed={panel===item[0]} onclick={()=>panel=item[0]}>{item[1]}</button>{/each}</nav>
  {#if error}<p role="alert" class="error">{error}</p>{/if}
  {#if busy}<p role="status">Saving this step and its evidence…</p>{/if}
  {#if panel==='working'}
    <form onsubmit={calculate}>
      <label>Your whiteboard working, in text<textarea bind:value={working} placeholder="Write your equation, assumptions, and the step you want to understand." rows="4"></textarea></label>
      <p class="muted">These inputs are entered by you. This screen does not yet extract a whiteboard image.</p>
      <div class="inputs">
        <label>Face value<input type="number" min="0.01" step="any" required bind:value={face}/></label>
        <label>Annual coupon (%)<input type="number" min="0" step="any" required bind:value={coupon}/></label>
        <label>Annual yield (%)<input type="number" step="any" required bind:value={yieldPercent}/></label>
        <label>Remaining payments<input type="number" min="1" max="1200" step="1" required bind:value={periods}/></label>
        <label>Payments per year<select bind:value={frequency}><option value={1}>1 · annual</option><option value={2}>2 · semiannual</option><option value={4}>4 · quarterly</option><option value={12}>12 · monthly</option></select></label>
      </div>
      <p>Valued on a coupon date, with regular payments and no accrued interest. Amounts use the same currency units as face value.</p>
      <button class="primary" disabled={busy}>Confirm assumptions & calculate</button>
    </form>
  {:else if panel==='payments'}
    {#if latest}
      <div class="result"><span>Present value</span><strong data-testid="bond-price">{money(latest.result.price)}</strong><span>{Number((latest.request.inputs.annual_yield*100).toFixed(4))}% yield · {latest.request.inputs.periods} payments</span></div>
      <h3>Choose a payment</h3><div class="payments" aria-label="Payment schedule">{#each latest.result.payments as p:Data (p.period)}<button class:active={selectedPayment===p.period} aria-pressed={selectedPayment===p.period} onclick={()=>selectedPayment=p.period}><span>Year {p.years}</span><strong>{money(p.cash_flow)}</strong><small>PV {money(p.present_value)}</small></button>{/each}</div>
      {#if payment}<div class="equation" aria-live="polite"><h3>Payment {payment.period}</h3><p>{money(payment.cash_flow)} × {payment.discount_factor.toFixed(6)} = <strong>{money(payment.present_value)} today</strong></p><p>Coupon {money(payment.coupon)} + principal {money(payment.principal)}. Discounted for {payment.years} years.</p></div>{/if}
      <form onsubmit={(event)=>{event.preventDefault();reprice();}} class="exercise"><h3>Predict, then test</h3><label>Change yield by (basis points)<input type="number" min="-500" max="500" step="1" required bind:value={shock}/></label><label>What do you expect to happen?<input required bind:value={prediction} placeholder="I expect price to fall because…"/></label><button class="primary" disabled={busy || !prediction.trim()}>Reveal the repriced bond</button></form>
      {#if previous && latest.request.comparison_base_action_id===previous.id}<div class="equation"><h3>Your last prediction</h3><p>{latest.request.prediction}</p><p>Exact change: {money(latest.result.price-previous.result.price)}. Duration estimate: {money(-previous.result.dv01_approx*latest.request.shock_basis_points)}.</p><p>Approximation error: {money((latest.result.price-previous.result.price)+previous.result.dv01_approx*latest.request.shock_basis_points)}.</p></div>{/if}
    {:else}<p>Start with your working and confirm the inputs to reveal the payment schedule.</p><button onclick={()=>panel='working'}>Enter your working</button>{/if}
  {:else if panel==='market'}
    <h3>Latest published Treasury context</h3><p>Daily par yields provide context. They are not spot discount rates or executable quotes for this bond.</p><button disabled={busy} onclick={()=>act({operation:'fetch_treasury',year:new Date().getFullYear()})}>Fetch Treasury observations</button>
    {#if treasury}<p>Observation: <strong>{treasury.result.latest_observation.observation_date}</strong> · fetched {new Date(treasury.result.fetched_at).toLocaleString()}</p><div class="rates">{#each Object.entries(treasury.result.latest_observation.yields_percent) as [tenor,value] (tenor)}<div><span>{tenor.replace('BC_','').replace('MONTH',' month').replace('YEAR',' year')}</span><strong>{value===null ? 'Unavailable' : value+'%'}</strong></div>{/each}</div><a href={treasury.result.source_url} target="_blank" rel="noreferrer">Treasury source XML</a><p class="muted">The fetched rates do not change your confirmed assumptions.</p>{/if}
  {:else}
    <h3>Saved steps</h3>{#if !actions.length}<p>Your calculations and source fetches will appear here.</p>{/if}
    {#each [...actions].reverse() as action:Data (action.id)}<article><strong>{action.operation.replaceAll('_',' ')}</strong><p>{action.status} · {new Date(action.created_at).toLocaleString()}</p>{#if action.error}<p class="error">{action.error}</p>{/if}{#if action.trace_error}<p class="error">{action.trace_error}</p>{/if}{#if action.mlflow_url}<a href={action.mlflow_url} target="_blank" rel="noreferrer">Inspect MLflow evidence</a>{/if}<details><summary>Inputs and result</summary><pre>{JSON.stringify(action,null,2)}</pre></details></article>{/each}
  {/if}
</section>

<style>
  .bond{max-width:1050px;margin:0 auto;padding:24px;color:var(--color-text,#242b33)}.intro{max-width:650px}.eyebrow{font-size:11px;letter-spacing:.12em;color:#63765d}h2{font-size:27px;line-height:1.2;margin:10px 0}h3{font-size:17px;margin:18px 0 10px}p{line-height:1.6}nav{display:flex;gap:5px;border-bottom:1px solid #d5d1c9;margin:24px 0;overflow:auto}button{padding:10px 14px;border:1px solid #d5d1c9;border-radius:9px;background:#f6f4ef;cursor:pointer}nav button{border:0;border-radius:0;background:none;white-space:nowrap}.active{box-shadow:inset 0 -2px #63765d;background:#e4e9df}button:disabled{opacity:.5;cursor:wait}.primary{background:#26352c;color:white;border-color:#26352c}label{display:grid;gap:7px;font-size:13px}input,select,textarea{width:100%;padding:11px;border:1px solid #cfcac1;border-radius:8px;background:#faf9f5;color:inherit;box-sizing:border-box}.inputs{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:20px 0}.muted{font-size:12px;color:#696961}.result{display:flex;flex-direction:column;gap:5px;padding:20px;background:#e5ebdf;border-radius:12px}.result strong{font-size:38px;font-variant-numeric:tabular-nums}.payments{display:flex;gap:8px;overflow:auto;padding-bottom:10px}.payments button{display:grid;gap:4px;min-width:112px;flex-shrink:0}.payments small{color:#65665e}.equation,article{border:1px solid #d5d1c9;border-radius:10px;padding:16px;margin:16px 0}.equation h3{margin-top:0}.exercise{display:grid;gap:14px;max-width:600px}.rates{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:20px 0}.rates div{display:grid;gap:8px;padding:14px;background:#f6f4ef;border-radius:8px}.error{color:#923b30}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px;max-height:400px;overflow:auto}a{text-decoration:underline}@media(max-width:600px){.bond{padding:14px}.inputs,.rates{grid-template-columns:repeat(2,1fr)}h2{font-size:23px}nav{margin:18px 0}}
</style>
