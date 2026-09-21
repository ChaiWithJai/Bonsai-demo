// Authored acceptance checks. Model source cannot change this entrypoint.
import {chromium, expect} from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
const [url, taskPath, output, testCase] = process.argv.slice(2);
const task = JSON.parse(await fs.readFile(taskPath, 'utf8'));
const rows = task.inputs.contract.rows;
const browser = await chromium.launch();
const page = await browser.newPage({viewport:{width:1440,height:1000},extraHTTPHeaders:{'X-Eval-Actor':'workspace-automated-check'}});
page.setDefaultTimeout(5000);
const errors=[];
page.on('pageerror', error=>errors.push(String(error)));
const report={case:testCase, passed:false, source_records:rows.length, scope:'Authored data and interaction assertions; not a human quality judgment'};
try {
 await page.goto(url);
 await expect(page.getByTestId('record-row')).toHaveCount(rows.length);
 const identities=await page.getByTestId('record-row').evaluateAll(nodes=>nodes.map(n=>n.dataset.recordId).sort());
 expect(identities).toEqual(rows.map(r=>r.id).sort());
 for(const row of rows){
  const element=page.getByTestId('record-row').filter({has:page.getByRole('button',{name:'Inspect '+row.id,exact:true})});
  await expect(element.getByTestId('record-value')).toHaveText(row.value===null?'Missing':String(row.value));
  await expect(element.getByRole('link')).toHaveAttribute('href',row.source_url);
 }
 await page.getByRole('button',{name:'1.7B (3)',exact:true}).click();
 await expect(page.getByTestId('record-row')).toHaveCount(3);
 if(testCase==='W1'||testCase==='W2'){
  await page.getByLabel('Runtime',{exact:true}).selectOption('MLX');
  await expect(page.getByTestId('record-row')).toHaveCount(1);
  await expect(page.getByTestId('record-row')).toHaveAttribute('data-record-id','prism-ml/Bonsai-1.7B-mlx-1bit');
  report.runtime_drilldown=true;
 }
 await page.getByRole('button',{name:'Clear filters',exact:true}).click();
 await expect(page.getByTestId('record-row')).toHaveCount(rows.length);
 const notes=[];
 for(const record of rows.slice(0,2)){
  await page.getByRole('button',{name:'Inspect '+record.id,exact:true}).click();
  const note='Workspace automated check '+Date.now()+' '+record.id;
  await page.getByLabel('Evidence note',{exact:true}).fill(note);
  const [response]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/annotations')&&r.request().method()==='POST'),page.getByRole('button',{name:'Save note',exact:true}).click()]);
  expect(response.status()).toBe(201);
  const saved=await response.json();
  expect(saved.record_snapshot).toEqual(record);
  expect(saved.review_origin).toBe('workspace-automated-check');
  await expect(page.getByText(note,{exact:true})).toBeVisible();
  notes.push(note);
 }
 if(testCase==='W2'){
  await expect(page.getByText(notes[0],{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Show all notes',exact:true}).click();
  for(const note of notes)await expect(page.getByText(note,{exact:true})).toBeVisible();
  report.selected_note_filter=true;
 }
 await page.reload();
 await expect(page.getByTestId('record-row')).toHaveCount(rows.length);
 for(const note of notes)await expect(page.getByText(note,{exact:true})).toBeVisible();
 await page.screenshot({path:path.join(output,'desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=390)).toBe(true);
 await page.screenshot({path:path.join(output,'mobile.png'),fullPage:true});
 expect(errors).toEqual([]);
 report.passed=true;report.note_persistence=true;report.record_ids=identities;
}catch(error){
 report.error=String(error);process.exitCode=1;
 await page.screenshot({path:path.join(output,'failure.png'),fullPage:true}).catch(()=>{});
}finally{
 report.runtime_errors=errors;
 await browser.close();
 await fs.writeFile(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
}
console.log(JSON.stringify(report));
