import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium,expect} from '@playwright/test';
const [url,taskPath,output] = process.argv.slice(2);
const compiled = JSON.parse(await fs.readFile(taskPath,'utf8'));
const browser = await chromium.launch();
const page = await browser.newPage({viewport:{width:1440,height:1000},extraHTTPHeaders:{'X-Eval-Actor':'workspace-automated-check'}});
page.setDefaultTimeout(5000);
const errors=[];page.on('pageerror',e=>errors.push(String(e)));
const report={passed:false,scope:'Source fidelity, chart loading, filtering and note persistence; not human design quality'};
try {
 await page.goto(url);
 await expect(page.getByTestId('record-row')).toHaveCount(compiled.rows.length);
 const ids=await page.getByTestId('record-row').evaluateAll(nodes=>nodes.map(n=>n.dataset.recordId).sort());
 expect(ids).toEqual(compiled.rows.map(r=>r.id).sort());
 const rendered=await page.getByTestId('record-data').allTextContents();
 expect(rendered.map(t=>JSON.parse(t))).toEqual(compiled.rows.map(r=>r.data));
 if(compiled.chart.component==='RecordTable') {
  await expect(page.getByRole('table')).toBeVisible();
  const values=await page.locator('tbody tr').evaluateAll(rows=>rows.map(row=>[...row.querySelectorAll('td')].slice(0,-1).map(cell=>cell.textContent)));
  expect(values).toEqual(compiled.rows.map(row=>compiled.chart.props.columns.map(column=>row.data[column]==null?'Missing':String(row.data[column]))));
 } else {
  await expect(page.locator('.chart img')).toBeVisible();
  expect(await page.locator('.chart img').evaluate(el=>el.complete&&el.naturalWidth>0)).toBe(true);
 }
 if(compiled.chart.component==='ForceDirectedGraph') {
  const first=compiled.chart.props.nodes[0];
  await page.getByRole('button',{name:'Explore '+first.label,exact:true}).click();
  await expect(page.getByTestId('record-row')).toHaveCount(compiled.node_membership[first.id].length);
  await page.getByRole('button',{name:'Clear filters',exact:true}).click();
  await page.getByLabel('Group',{exact:true}).selectOption(first.id);
  await expect(page.getByTestId('record-row')).toHaveCount(compiled.node_membership[first.id].length);
  await page.getByRole('button',{name:'Clear filters',exact:true}).click();
 }
 await page.getByLabel('Search records',{exact:true}).fill('__NO_MATCH_'+Date.now());
 await expect(page.getByTestId('record-row')).toHaveCount(0);
 await page.getByRole('button',{name:'Clear filters',exact:true}).click();
 await expect(page.getByTestId('record-row')).toHaveCount(compiled.rows.length);
 const passages=compiled.rows[0].locator?.source_evidence ?? [];
 if(passages.some(p=>/^[a-f0-9]{64}:/.test(p.record_id))) {
  const row=page.getByTestId('record-row').first();
  await row.locator('summary').filter({hasText:'Supporting source passages'}).click();
  for(const passage of passages.filter(p=>/^[a-f0-9]{64}:/.test(p.record_id))) {
   const sid=passage.record_id.split(':')[0];
   const links=row.getByRole('link').filter({hasText:'Open original'});
   const hrefs=await links.evaluateAll(nodes=>nodes.map(node=>node.getAttribute('href')));
   expect(hrefs.some(href=>href.includes('/sources/'+sid+'/file'))).toBe(true);
  }
 }
 const record=compiled.rows[0];
 await page.getByRole('button',{name:'Inspect '+record.id,exact:true}).click();
 const note='Automated source workflow check '+Date.now();
 await page.getByLabel('Evidence note',{exact:true}).fill(note);
 const [response]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/annotations')&&r.request().method()==='POST'),page.getByRole('button',{name:'Save note',exact:true}).click()]);
 expect(response.status()).toBe(201);const saved=await response.json();
 expect(saved.record_snapshot).toEqual(record);expect(saved.review_origin).toBe('workspace-automated-check');
 await page.reload();await expect(page.getByText(note,{exact:true})).toBeVisible();
 await page.screenshot({path:path.join(output,'desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.join(output,'mobile.png'),fullPage:true});
 expect(errors).toEqual([]);report.passed=true;report.record_ids=ids;report.note_persistence=true;
} catch(error) {
 report.error=String(error);process.exitCode=1;await page.screenshot({path:path.join(output,'failure.png'),fullPage:true}).catch(()=>{});
} finally {
 report.runtime_errors=errors;await browser.close();await fs.writeFile(path.join(output,'report.json'),JSON.stringify(report,null,2));
}
console.log(JSON.stringify(report));
