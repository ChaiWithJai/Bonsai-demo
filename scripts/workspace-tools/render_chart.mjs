import fs from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { validateProps, diagnoseConfig } from 'semiotic/ai/core';
import { renderChartWithEvidence } from 'semiotic/server';

// This checks the compiled flat-data contract, not factual interpretation or
// the geometry of each line. Keep the limited scope in the persisted evidence.
export function checkLineSeries(props, evidence) {
  if (!Array.isArray(props.data) || typeof props.lineBy !== 'string') {
    return {status:'not_assessed', scope:'Flat data grouped by a named field only'};
  }
  const groups=new Set(props.data.map(row=>row[props.lineBy]));
  const expected=groups.size;
  const observed=evidence.markCountByType?.line;
  if (!Number.isInteger(observed) || observed !== expected) {
    throw new Error(`Line series mismatch: expected ${expected} separate lines from ${props.lineBy}, rendered ${observed ?? 'unknown'}`);
  }
  return {status:'passed', scope:'Rendered line count matches compiled series count; not semantic accuracy', expected_series:expected, rendered_series:observed};
}

export function renderChart(spec) {
  if (!['Scatterplot','LineChart','ForceDirectedGraph'].includes(spec.component)) throw new Error('Unsupported desktop component');
  const validation = validateProps(spec.component, spec.props);
  if (!validation.valid) throw new Error(validation.errors.join('; '));
  const diagnostics = diagnoseConfig(spec.component, spec.props);
  if (!diagnostics.ok) throw new Error(JSON.stringify(diagnostics));
  let props = spec.props;
  // Older saved plans named the series through colorBy but omitted lineBy.
  // Color alone creates a legend without separating the rendered lines.
  if (spec.component === 'LineChart' && !props.lineBy && props.colorBy) {
    props = {...props, lineBy: props.colorBy};
  }
  const positions = new Map();
  // Semiotic 3.10.3's static force layout passes identity-only nodes to labels.
  // Resolve display metadata by the stable ID, keeping the saved JSON unchanged.
  if (spec.component === 'ForceDirectedGraph') {
    const nodes = new Map(props.nodes.map(node => [node.id, node]));
    const colors = ['#506a51', '#a16d42', '#586f91'];
    const categories = [...new Set(props.nodes.map(node => node.field))];
    const palette = Object.fromEntries(categories.map((name, i) => [name, colors[i % colors.length]]));
    props = {...props, showLabels: true, colorScheme: palette,
      nodeLabel: node => {
        const label = nodes.get(node.id)?.label ?? node.id;
        positions.set(node.id,{id:node.id,label,x:node.x,y:node.y});
        return label.length > 44 ? `${label.slice(0,41)}…` : label;
      },
      nodeStyle: node => ({fill: palette[nodes.get(node.id)?.field] ?? colors[0]})};
  }
  const result = renderChartWithEvidence(spec.component, props);
  if (result.evidence.empty) throw new Error('Semiotic rendered no data marks');
  const source_contract = spec.component === 'LineChart' ? checkLineSeries(props,result.evidence) : {status:'not_assessed',scope:'Line series only'};
  const plot=result.evidence.plot;
  const points=[];
  if (['LineChart','Scatterplot'].includes(spec.component) && plot &&
      ['linear','time'].includes(props.xScaleType ?? 'linear') &&
      (props.yScaleType ?? 'linear') === 'linear' &&
      typeof props.xAccessor === 'string' && typeof props.yAccessor === 'string') {
    const [xmin,xmax]=result.evidence.xDomain;
    const [ymin,ymax]=result.evidence.yDomain;
    if (xmax>xmin && ymax>ymin) for (const row of props.data) {
      if (row[props.xAccessor] == null || row[props.yAccessor] == null) continue;
      const x=Number(row[props.xAccessor]),y=Number(row[props.yAccessor]);
      if (typeof row.record_id !== 'string' || !Number.isFinite(x) || !Number.isFinite(y)) continue;
      points.push({record_id:row.record_id,x:plot.x+(x-xmin)/(xmax-xmin)*plot.width,
        y:plot.y+(ymax-y)/(ymax-ymin)*plot.height});
    }
  }
  const interaction = {width:result.evidence.width,height:result.evidence.height,points,nodes:[...positions.values()].map(node=>({...node,x:node.x+(plot?.x??0),y:node.y+(plot?.y??0)}))};
  return {...result, interaction, diagnostics, source_contract, renderer: 'semiotic@3.10.3'};
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    const spec = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
    const result = renderChart(spec);
    await fs.mkdir(process.argv[3], {recursive: true});
    await fs.writeFile(`${process.argv[3]}/chart.svg`, result.svg);
    await fs.writeFile(`${process.argv[3]}/render-evidence.json`, JSON.stringify({...result, svg:undefined},null,2));
    console.log(JSON.stringify(result.evidence));
  } catch(error) {console.error(error.message); process.exitCode=1;}
}
