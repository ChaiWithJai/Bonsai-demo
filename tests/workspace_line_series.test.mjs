import test from 'node:test';
import assert from 'node:assert/strict';
import {renderChart,checkLineSeries} from '../scripts/workspace-tools/render_chart.mjs';

test('saved line plans render separate series, including zero observations', () => {
  const props={width:900,height:520,xAccessor:'x',yAccessor:'y',colorBy:'group',data:[
    {x:1,y:0,group:'Orchard',all:'All'}, {x:1,y:7,group:'Meadow',all:'All'},
    {x:2,y:2,group:'Orchard',all:'All'}, {x:2,y:6,group:'Meadow',all:'All'},
    {x:3,y:3,group:'Orchard',all:'All'}, {x:3,y:4,group:'Meadow',all:'All'}]};
  const before=structuredClone(props);
  const result=renderChart({component:'LineChart',props});
  assert.equal(result.evidence.markCountByType.line,2);
  assert.equal(result.evidence.legendItems,2);
  assert.equal(result.source_contract.expected_series,2);
  assert.equal(result.source_contract.status,'passed');
  assert.ok(result.evidence.yDomain[0]<=0);
  assert.deepEqual(props,before);
  const explicit=renderChart({component:'LineChart',props:{...props,lineBy:'all'}});
  assert.equal(explicit.evidence.markCountByType.line,1);
});

test('series gate rejects the observed one-line two-team failure', () => {
  const props={lineBy:'group',data:[{group:'Orchard'},{group:'Meadow'}]};
  assert.throws(()=>checkLineSeries(props,{markCountByType:{line:1}}),/expected 2 separate lines.*rendered 1/);
  assert.throws(()=>checkLineSeries(props,{}),/rendered unknown/);
  assert.equal(checkLineSeries(props,{markCountByType:{line:2}}).status,'passed');
  assert.equal(checkLineSeries({data:[],lineBy:()=>0},{}).status,'not_assessed');
});
