import test from 'node:test';
import assert from 'node:assert/strict';
import {renderChart} from '../scripts/workspace-tools/render_chart.mjs';

test('saved line plans render separate series, including zero observations', () => {
  const props={width:900,height:520,xAccessor:'x',yAccessor:'y',colorBy:'group',data:[
    {x:1,y:0,group:'Orchard',all:'All'}, {x:1,y:7,group:'Meadow',all:'All'},
    {x:2,y:2,group:'Orchard',all:'All'}, {x:2,y:6,group:'Meadow',all:'All'},
    {x:3,y:3,group:'Orchard',all:'All'}, {x:3,y:4,group:'Meadow',all:'All'}]};
  const before=structuredClone(props);
  const result=renderChart({component:'LineChart',props});
  assert.equal(result.evidence.markCountByType.line,2);
  assert.equal(result.evidence.legendItems,2);
  assert.ok(result.evidence.yDomain[0]<=0);
  assert.deepEqual(props,before);
  const explicit=renderChart({component:'LineChart',props:{...props,lineBy:'all'}});
  assert.equal(explicit.evidence.markCountByType.line,1);
});
