import fs from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { validateProps, diagnoseConfig } from 'semiotic/ai/core';
import { renderChartWithEvidence } from 'semiotic/server';

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
  const plot=result.evidence.plot;
  const interaction = {width:result.evidence.width,height:result.evidence.height,nodes:[...positions.values()].map(node=>({...node,x:node.x+(plot?.x??0),y:node.y+(plot?.y??0)}))};
  return {...result, interaction, diagnostics, renderer: 'semiotic@3.10.3'};
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
