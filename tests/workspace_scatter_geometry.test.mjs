import test from 'node:test';
import assert from 'node:assert/strict';
import {renderChart,checkScatterGeometry} from '../scripts/workspace-tools/render_chart.mjs';

function spec(xs=[1,3],extra={}) {
  return {component:'Scatterplot',props:{width:900,height:520,xAccessor:'x',yAccessor:'y',
    data:xs.map((x,i)=>({record_id:`row-${i}`,x,y:i*8})),...extra}};
}
for(const [name,xs,extra] of [
  ['numeric',[1,3],{}],
  ['dated',[1790035200000,1790294400000],{xScaleType:'time'}],
  ['same x',[2,2],{}],
]) test(`${name} scatter keeps complete circles and matching evidence targets`,()=>{
  const input=spec(xs,extra),before=structuredClone(input);
  const result=renderChart(input);
  assert.equal(result.geometry_contract.status,'passed');
  assert.equal(result.geometry_contract.circle_count,2);
  assert.equal(result.interaction.points.length,2);
  assert.equal(result.rendering_adjustments.length,1);
  assert.deepEqual(input,before);
  assert.throws(()=>checkScatterGeometry(result.svg,result.evidence.plot,
    result.interaction.points.map(p=>({...p,x:p.x+1}))),/positions/);
});
test('explicit safe extent is preserved; clipped explicit extent is rejected',()=>{
  const result=renderChart(spec([1,3],{xExtent:[0,4]}));
  assert.deepEqual(result.evidence.xDomain,[0,4]);
  assert.deepEqual(result.rendering_adjustments,[]);
  assert.throws(()=>renderChart(spec([1,3],{xExtent:[1,3]})),/clipped/);
});
