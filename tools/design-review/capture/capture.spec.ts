import {test,expect} from '@playwright/test';
import path from 'node:path';
import fs from 'node:fs/promises';
test('Workspace screens',async({page},info)=>{
 const shots=path.resolve(import.meta.dirname,'../shots');await fs.mkdir(shots,{recursive:true});
 await page.goto('/#/workspace');
 await expect(page.getByRole('heading',{name:'Build on what you know.'})).toBeVisible();
 await expect(page.getByRole('status',{name:'Opening Workspace…'})).toHaveCount(0);
 await page.getByText(/Saved projects/).click();
 await page.locator('.saved-projects button').first().click();
 await expect(page.getByLabel('Describe the next change')).toBeVisible();
 const restore=page.getByRole('button',{name:'Build saved revision'});
 if(await restore.isVisible())await restore.click();
 await expect(page.locator('iframe')).toBeVisible();
 await expect(page.frameLocator('iframe').getByTestId('record-row')).toHaveCount(14);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 if(info.project.name==='mobile') {
  await page.locator('iframe').scrollIntoViewIfNeeded();
  await expect(page.frameLocator('iframe').getByRole('heading',{name:'Bonsai repository observations'})).toBeVisible();
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 }
 await page.screenshot({path:path.join(shots,'01-workspace-preview.'+info.project.name+'.png'),fullPage:true});
 await page.getByRole('button',{name:'Source',exact:true}).click();
 await expect(page.locator('pre.source')).toContainText('onMount');
 await page.screenshot({path:path.join(shots,'02-workspace-source.'+info.project.name+'.png'),fullPage:true});
 await page.getByRole('button',{name:'Evidence',exact:true}).click();
 await page.screenshot({path:path.join(shots,'03-workspace-evidence.'+info.project.name+'.png'),fullPage:true});
 await page.getByRole('button',{name:'Drill into runtimes',exact:true}).click();
 await expect(page.getByLabel('Describe the next change')).toHaveValue(/runtime/);
 // Compose only. Captures never start inference.
 await page.reload();
 await expect(page.getByRole('heading',{name:'What do you want to understand?'})).toBeVisible();
 await expect(page.locator('iframe')).toHaveCount(0);
});

test('Workspace uploaded data and persisted review',async({page},info)=>{
 test.skip(!process.env.WORKSPACE_DATA_TEST_URL, 'Archived fixture server is intentionally stopped');
 await page.goto(process.env.WORKSPACE_DATA_TEST_URL + '/#/workspace');
 await page.getByText(/Saved projects/).click();
 await page.locator('.saved-projects button').first().click();
 await page.getByRole('button',{name:'Data',exact:true}).click();
 await page.getByLabel('Saved source').selectOption('9dda1f05e8cd19fa874f8ff8efb24704e5e582d14356b2c4fcadd5bbd033f4f6');
 await expect(page.getByRole('heading',{name:'synthetic-review.json'})).toBeVisible();
 await page.getByText('Review records and export corrections',{exact:true}).click();
 await expect(page.getByText(/1 records reviewed in this extraction version/)).toBeVisible();
 await page.getByLabel('Source record').selectOption('9dda1f05e8cd19fa874f8ff8efb24704e5e582d14356b2c4fcadd5bbd033f4f6:0');
 await expect(page.getByText(/Latest review: correct by Workspace automated browser check \(test\)/)).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 const response=await page.request.get('http://127.0.0.1:5258/api/workspace/sources/9dda1f05e8cd19fa874f8ff8efb24704e5e582d14356b2c4fcadd5bbd033f4f6');
 const source=await response.json();
 expect(source.records.map((r:any)=>r.data.value)).toEqual([0,null]);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/04-workspace-data.'+info.project.name+'.png'),fullPage:true});
});

test('Workspace starts with user data rather than a fixture preview',async({page},info)=>{
 const before=await (await page.request.get('/api/workspace')).json();
 await page.addInitScript(()=>localStorage.setItem('bonsai-workspace','9133f03e28d9407395f0f45829a780f9'));
 await page.goto('/#/workspace');
 await expect(page.getByRole('heading',{name:'What do you want to understand?'})).toBeVisible();
 await expect(page.getByRole('heading',{name:'Bring your files and a question.'})).toBeVisible();
 await expect(page.getByText(/Files and a question/)).toBeVisible();
 await expect(page.locator('iframe')).toHaveCount(0);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/05-workspace-start.'+info.project.name+'.png'),fullPage:true});
 const after=await (await page.request.get('/api/workspace')).json();
 expect(after.workspaces).toEqual(before.workspaces);
 expect(after.running_attempts).toEqual([]);
});

test('PDF upload shows page records and extraction coverage',async({page},info)=>{
 const source='02f32dd8bdd1d72b2e5293c89d06b739e19f789ad35820614bdcaec3f6ac3777';
 const original=await page.request.get('/api/workspace/sources/'+source+'/file');
 expect(original.ok()).toBe(true);
 await page.goto('/#/workspace');
 await page.locator('input[type=file]').setInputFiles({name:'S82065.pdf',mimeType:'application/pdf',buffer:await original.body()});
 await expect(page.getByRole('heading',{name:'S82065.pdf',exact:true})).toBeVisible();
 await expect(page.getByText('79 of 79 pages contain extracted text · 0 OCR pages',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'Understand these files',exact:true})).toBeVisible();
 const sourceResponse=await page.request.get('/api/workspace/sources/'+source);
 const data=await sourceResponse.json();
 expect(data.sha256).toBe('2ab8e898b0f0208138af7e71629e05925b333afe8d13e49953bfad6dfbc1cb93');
 expect(data.records).toHaveLength(79);
 expect(data.records.map((r:any)=>r.locator.page)).toEqual(Array.from({length:79},(_,i)=>i+1));
 expect(data.records[0].data.text).toContain('Five Bottlenecks, Five Fixes');
 await page.locator('.records details').first().locator('summary').click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/06-workspace-pdf.'+info.project.name+'.png'),fullPage:true});
});

test('Bonsai interpretation is reviewed before a view is built',async({page},info)=>{
 test.skip(!process.env.WORKSPACE_PROPOSAL_JOB,'Requires a completed live proposal');
 const response=await page.request.get('/api/workspace/source-jobs/'+process.env.WORKSPACE_PROPOSAL_JOB);
 const job=await response.json();expect(job.status).toBe('awaiting_confirmation');expect(job.workspace_id).toBeUndefined();
 const before=await (await page.request.get('/api/workspace')).json();
 await page.goto('/#/workspace');
 const card=page.getByRole('region',{name:'Bonsai proposal'}).first();
 await expect(card.getByRole('heading',{name:'Here’s what I’m seeing'})).toBeVisible();
 await expect(card.getByRole('button',{name:'Yes, build this view'})).toBeEnabled();
 await card.getByLabel('Clarify or change this proposal').fill('Keep the source pages available alongside the proposed groups.');
 await expect(card.getByRole('button',{name:'Discuss this change'})).toBeEnabled();
 await card.locator('details').first().locator('summary').click();
 await expect(card.locator('pre').first()).toContainText('page');
 await card.scrollIntoViewIfNeeded();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/07-workspace-proposal.'+info.project.name+'.png'),fullPage:true});
 const after=await (await page.request.get('/api/workspace')).json();expect(after.workspaces).toEqual(before.workspaces);
 // Never submit a human confirmation during visual review.
});

test('Multiple existing files can be attached and removed without inference',async({page},info)=>{
 const ids=['02f32dd8bdd1d72b2e5293c89d06b739e19f789ad35820614bdcaec3f6ac3777','dd7cb2673ec7514249df506a13da200714aef7f0fb2b83bb0e9fc000fa9ba3e0'];
 const before=await (await page.request.get('/api/workspace/source-jobs')).json();
 const files=[];
 for(const id of ids){
  const source=await (await page.request.get('/api/workspace/sources/'+id)).json();
  const original=await page.request.get('/api/workspace/sources/'+id+'/file');
  files.push({name:source.filename,mimeType:'application/octet-stream',buffer:await original.body()});
 }
 await page.goto('/#/workspace');
 await page.getByLabel('What should this visualization help you understand?').fill('Browser check only: review attachment handling without running the model.');
 await page.locator('input[type=file]').setInputFiles(files);
 const attachments=page.getByLabel('Attached files');
 await expect(attachments.locator('button.remove')).toHaveCount(2);
 await expect(page.getByRole('button',{name:'Understand these files',exact:true})).toBeEnabled();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/08-workspace-attachments.'+info.project.name+'.png'),fullPage:true});
 await attachments.getByRole('button',{name:'Remove '+files[1].name,exact:true}).click();
 await expect(attachments.locator('button.remove')).toHaveCount(1);
 await expect(page.getByRole('heading',{name:files[0].name,exact:true})).toBeVisible();
 await attachments.getByRole('button',{name:'Remove '+files[0].name,exact:true}).click();
 await expect(attachments).toHaveCount(0);
 await expect(page.getByRole('button',{name:'Understand these files',exact:true})).toHaveCount(0);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 const after=await (await page.request.get('/api/workspace/source-jobs')).json();
 expect(after).toEqual(before);
});

test('Image upload extracts readable regions and exposes its limits',async({page},info)=>{
 const imagePath=path.resolve(import.meta.dirname,'../../../.cache/workspace-pdf-20260921/page-1.png');
 test.skip(!await fs.stat(imagePath).catch(()=>null),'Requires the real PDF page render');
 await page.goto('/#/workspace');
 await page.locator('input[type=file]').setInputFiles({name:'S82065-page-1.png',mimeType:'image/png',buffer:await fs.readFile(imagePath)});
 await expect(page.getByText('6 readable text regions',{exact:true})).toBeVisible();
 await expect(page.getByText(/Chart values, diagram relationships, and non-text content are not interpreted/)).toBeVisible();
 const image=page.getByRole('img',{name:'Original image: S82065-page-1.png'});
 await expect(image).toBeVisible();
 await expect.poll(()=>image.evaluate((node:HTMLImageElement)=>node.complete && node.naturalWidth>0)).toBe(true);
 const passages=page.getByLabel('Recognized passages');
 await passages.getByRole('button').first().click();
 const outline=page.getByRole('button',{name:'Highlight passage 1: Five Bottlenecks, Five Fixes:'});
 await expect(outline).toHaveAttribute('aria-pressed','true');
 await expect(page.getByLabel('Source record')).toHaveValue(/:region:1$/);
 const box=await outline.boundingBox();const frame=await image.boundingBox();
 expect(box!.y).toBeGreaterThan(frame!.y);expect(box!.y).toBeLessThan(frame!.y+frame!.height*.3);
 await outline.focus();await page.keyboard.press('Tab');await page.keyboard.press('Enter');
 await expect(passages.getByRole('button').nth(1)).toHaveAttribute('aria-pressed','true');
 await expect(page.getByLabel('Source record')).toHaveValue(/:region:2$/);
 await page.getByLabel('Decision').selectOption('correct');
 await expect(page.getByLabel('Corrected text')).toHaveValue('How We Avoid Leaving Training');
 await page.getByRole('region',{name:'Image evidence'}).scrollIntoViewIfNeeded();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/09-workspace-image.'+info.project.name+'.png'),fullPage:true});
});

test('Audio upload exposes timestamped transcript and playback',async({page},info)=>{
 const fixture=path.resolve(import.meta.dirname,'../../../../bonsai-generative-ui/.local/media-example/team-notes.wav');
 test.skip(!await fs.stat(fixture).catch(()=>null),'Requires the labeled synthetic speech fixture');
 await page.goto('/#/workspace');
 await page.locator('input[type=file]').setInputFiles({name:'synthetic-team-notes.wav',mimeType:'audio/wav',buffer:await fs.readFile(fixture)});
 const evidence=page.getByRole('region',{name:'Audio evidence'});
 await expect(evidence).toBeVisible({timeout:30000});
 const audio=evidence.locator('audio');
 await expect.poll(()=>audio.evaluate((node:HTMLAudioElement)=>node.readyState>=1)).toBe(true);
 await evidence.getByRole('button').nth(1).click();
 await expect.poll(()=>audio.evaluate((node:HTMLAudioElement)=>node.currentTime)).toBeGreaterThanOrEqual(5.5);
 await audio.evaluate((node:HTMLAudioElement)=>node.pause());
 await expect(page.getByLabel('Source record')).toHaveValue(/:segment:2$/);
 await page.getByLabel('Decision').selectOption('correct');
 await expect(page.getByLabel('Corrected text')).toHaveValue(/separate repository creation dates/);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await evidence.scrollIntoViewIfNeeded();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/10-workspace-audio.'+info.project.name+'.png'),fullPage:true});
 // No review is saved and no model proposal or human confirmation is submitted.
});

test('Video evidence seeks to the selected sampled frame',async({page},info)=>{
 const source='8cc403d0bfcc8e7140778b17ad52451ea587f47563192cf324535cb9242df2d3';
 await page.goto('/#/workspace');
 await page.getByLabel('Saved source').selectOption(source);
 const evidence=page.getByRole('region',{name:'Video evidence'});
 await expect(evidence).toBeVisible();const video=evidence.locator('video');
 await expect.poll(()=>video.evaluate((node:HTMLVideoElement)=>node.readyState>=1)).toBe(true);
 await evidence.getByRole('button',{name:/^15.0s/}).first().click();
 await expect.poll(()=>video.evaluate((node:HTMLVideoElement)=>node.currentTime)).toBeGreaterThanOrEqual(14.9);
 await expect(page.getByLabel('Source record')).not.toHaveValue('');
 await expect(page.getByText(/One frame every 15 seconds; audio and unsampled motion were not read/)).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await evidence.scrollIntoViewIfNeeded();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/11-workspace-video.'+info.project.name+'.png'),fullPage:true});
});

test('Compare saved repair attempts',async({page},info)=>{
 await page.goto('/#/workspace');
 await page.getByText(/Saved projects/).click();
 await page.locator('.saved-projects button').filter({hasText:'Model Variant Node View'}).click();
 await page.getByRole('button',{name:'Evidence',exact:true}).click();
 await page.getByRole('button',{name:'Compare attempts',exact:true}).click();
 await expect(page.getByText('Task metadata differs or is missing.',{exact:false})).toBeVisible();
 await expect(page.locator('.comparison-results article')).toHaveCount(2);
 await expect(page.locator('.comparison-results').getByRole('heading',{name:'failed',exact:true})).toBeVisible();
 await expect(page.locator('.comparison-results').getByRole('heading',{name:'completed',exact:true})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/12-comparison.'+info.project.name+'.png'),fullPage:true});
});

test('Interface review is explicit and test feedback is excluded',async({page},info)=>{
 await page.goto('/#/workspace');
 await page.getByText(/Saved projects/).click();
 await page.locator('.saved-projects button').filter({hasText:'Model Variant Node View'}).click();
 await page.getByRole('button',{name:'Evidence',exact:true}).click();
 await page.getByLabel('Reviewer name',{exact:true}).fill('Automated development check');
 await page.getByLabel('Review origin',{exact:true}).selectOption('test');
 await page.getByLabel('Review notes',{exact:true}).fill('Browser verification only; not human acceptance.');
 await page.getByRole('button',{name:'Save interface review',exact:true}).click();
 await expect(page.getByRole('status').filter({hasText:'Automated development check (test)'})).toBeVisible();
 await page.getByRole('button',{name:'Export interface reviews to MLflow',exact:true}).click();
 await expect(page.getByText('0 accepted human-reviewed examples.',{exact:false})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/13-interface-review.'+info.project.name+'.png'),fullPage:true});
});

test('Word document upload preserves text and declares coverage',async({page},info)=>{
 await page.goto('/#/workspace');
 await page.locator('input[type=file]').setInputFiles(path.resolve(import.meta.dirname,'../../../.cache/workspace-checks/development-notes.docx'));
 await expect(page.getByRole('heading',{name:'development-notes.docx',exact:true})).toBeVisible();
 await expect(page.getByText('1 records · document · extracted',{exact:true})).toBeVisible();
 await expect(page.getByText(/1 embedded media files not read/)).toBeVisible();
 await page.getByText('Document block 1 · paragraph',{exact:true}).click();
 await expect(page.locator('.records pre').filter({hasText:'Development fixture: model A has 12 observations'})).toBeVisible();
 expect(await page.locator('.data').evaluate(el=>el.scrollWidth<=el.clientWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/14-docx.'+info.project.name+'.png'),fullPage:true});
});

test('Table proposal explains record inspection without chart axes',async({page},info)=>{
 const response=await page.request.get('/api/workspace/source-jobs/4fcf01b7f98f4b39b6d78f19bdc330fc');
 const job=await response.json();expect(job.proposal.plan.view.component).toBe('RecordTable');
 // Display-only replay of the saved proposal. No confirmation or server state change.
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[{...job,status:'awaiting_confirmation',workspace_id:undefined}]}}));
 await page.goto('/#/workspace');
 const proposal=page.getByRole('region',{name:'Bonsai proposal'});
 await expect(proposal.getByText('Inspect source records',{exact:true})).toBeVisible();
 await expect(proposal.getByText(/Read the structured fields in a searchable table/)).toBeVisible();
 await expect(proposal).not.toContainText('undefined compared with');
 await proposal.scrollIntoViewIfNeeded();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/15-table-proposal.'+info.project.name+'.png'),fullPage:true});
});

test('Readable mixed records preserve values and selection',async({page},info)=>{
 const response=await page.request.get('/api/workspace/e13a4a3d2c214a688339afcd92ddb5fd');
 const project=await response.json();
 expect(project.attempts.at(-1).status).toBe('completed');
 expect(project.preview.revision).toBe(project.head);
 await page.goto(project.preview.url);
 const records=page.getByTestId('record-row');
 await expect(records).toHaveCount(project.fixture.compiled.rows.length);
 for(let i=0;i<project.fixture.compiled.rows.length;i++) {
  const row=records.nth(i), data=project.fixture.compiled.rows[i].data;
  const values=await row.locator('dd').allTextContents();
  expect(values).toEqual(Object.values(data).map(value=>value===null?'null':String(value)));
  const raw=row.locator('details').filter({has:page.locator('summary',{hasText:'Raw data'})});
  await expect(raw).not.toHaveAttribute('open','');
  await raw.locator('summary').click();
  expect(JSON.parse(await row.getByTestId('record-data').innerText())).toEqual(data);
  await raw.locator('summary').click();
 }
 const statementColumn=project.fixture.compiled.chart.props.columns.indexOf('statement');
 expect(await page.locator('tbody tr').first().locator('td').nth(statementColumn).evaluate(el=>el.getBoundingClientRect().width)).toBeGreaterThan(200);
 const first=records.first();
 if(info.project.name==='desktop') {
  const statement=first.locator('dd').filter({hasText:project.fixture.compiled.rows[0].data.statement});
  expect(await statement.evaluate(el=>el.getBoundingClientRect().width)).toBeGreaterThan(200);
 }
 const inspect=first.getByRole('button',{name:'Inspect '+project.fixture.compiled.rows[0].id,exact:true});
 await inspect.click();
 await expect(inspect).toHaveAttribute('aria-pressed','true');
 await expect(page.getByLabel('Evidence note',{exact:true})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/16-readable-records.'+info.project.name+'.png'),fullPage:true});
});

test('Workspace distinguishes request checks from baseline verification',async({page},info)=>{
 for(const [id,expected] of [
  ['e13a4a3d2c214a688339afcd92ddb5fd','Build, baseline checks, and supplied request checks passed. Ready for your review.'],
  ['a38c58f2fa114f029c5c8ee8f03a356b','Build and baseline checks passed. The requested behavior still needs review.']
 ]) {
  const project=await (await page.request.get('/api/workspace/'+id)).json();
  expect(project.attempts.at(-1).status).toBe('completed');
  await page.route('**/api/workspace',async route=>{
   const response=await route.fetch();const state=await response.json();
   await route.fulfill({json:{...state,workspaces:state.workspaces.filter((p:any)=>p.id===id)}});
  });
  await page.goto('/#/workspace');
  await page.locator('.saved-projects summary').click();
  await page.locator('.saved-projects').getByRole('button',{name:project.title,exact:true}).click();
  await expect(page.getByText(expected,{exact:true})).toBeVisible();
  await page.getByText(expected,{exact:true}).scrollIntoViewIfNeeded();
  if(id==='e13a4a3d2c214a688339afcd92ddb5fd')await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/17-request-verification.'+info.project.name+'.png'),fullPage:true});
  await page.unroute('**/api/workspace');
 }
});

test('Composer reviews expected results and preserves a rejected draft',async({page},info)=>{
 const id='e13a4a3d2c214a688339afcd92ddb5fd';
 const project=await (await page.request.get('/api/workspace/'+id)).json();
 await page.goto('/#/workspace');
 await page.locator('.saved-projects summary').click();
 await page.locator('.saved-projects').getByRole('button',{name:project.title,exact:true}).click();
 await page.getByLabel('Describe the next change').fill('Use the heading Mixed source evidence.');
 await page.locator('.expectations summary').click();
 await page.getByRole('button',{name:'Add expected result',exact:true}).click();
 await expect(page.getByRole('button',{name:'Send request',exact:true})).toBeDisabled();
 await page.getByLabel('Exact label',{exact:true}).fill('Mixed source evidence');
 await page.getByRole('button',{name:'Add expected result',exact:true}).click();
 await page.getByRole('combobox',{name:'Check 2',exact:true}).selectOption('records');
 await page.getByLabel('Expected count',{exact:true}).fill('3');
 await expect(page.getByRole('button',{name:'Send request',exact:true})).toBeEnabled();
 await page.locator('.expectations').scrollIntoViewIfNeeded();
 await page.locator('.expectations').evaluate(el=>el.scrollTop=0);
 if(info.project.name==='desktop')await expect(page.getByRole('button',{name:'Send request',exact:true})).toBeInViewport();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/18-expected-results.'+info.project.name+'.png'),fullPage:true});
 let submitted:any;
 await page.route('**/api/workspace/'+id+'/attempts',async route=>{
  submitted=route.request().postDataJSON();
  await route.fulfill({status:409,json:{error:'Development check: draft retained'}});
 });
 await page.getByRole('button',{name:'Send request',exact:true}).click();
 await expect(page.getByText('Development check: draft retained',{exact:false})).toBeVisible();
 expect(submitted.request_checks).toEqual([
  {target:{role:'heading',name:'Mixed source evidence'},action:'visible',value:true},
  {target:{test_id:'record-row'},action:'count',value:3}
 ]);
 expect(submitted.base_revision).toBe(project.head);
 await expect(page.getByLabel('Exact label',{exact:true})).toHaveValue('Mixed source evidence');
 await expect(page.getByLabel('Describe the next change')).toHaveValue('Use the heading Mixed source evidence.');
 await page.getByRole('button',{name:'Remove check 1',exact:true}).click();
 await expect(page.getByLabel('Expected count',{exact:true})).toHaveValue('3');
});

test('Live composer sends fixed expected results to Bonsai',async({page},info)=>{
 test.skip(process.env.BONSAI_LIVE_ACCEPTANCE !== '1' || info.project.name !== 'desktop','Explicit development inference only');
 test.setTimeout(240000);
 await page.setExtraHTTPHeaders({'X-Eval-Actor':'codex-development-verification'});
 const id='e13a4a3d2c214a688339afcd92ddb5fd';
 const project=await (await page.request.get('/api/workspace/'+id)).json();
 await page.goto('/#/workspace');
 await page.locator('.saved-projects summary').click();
 await page.locator('.saved-projects').getByRole('button',{name:project.title,exact:true}).click();
 await page.getByLabel('Describe the next change').fill('Change the main heading to exactly Mixed source evidence. Preserve all records, source links, fields, notes and interactions. Build and check the result.');
 await page.locator('.expectations summary').click();
 await page.getByRole('button',{name:'Add expected result',exact:true}).click();
 await page.getByLabel('Exact label',{exact:true}).fill('Mixed source evidence');
 await page.getByRole('button',{name:'Add expected result',exact:true}).click();
 await page.getByRole('combobox',{name:'Check 2',exact:true}).selectOption('records');
 await page.getByLabel('Expected count',{exact:true}).fill('3');
 const response=page.waitForResponse(r=>r.url().endsWith('/'+id+'/attempts')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Send request',exact:true}).click();
 const sent=await response;expect(sent.ok()).toBe(true);const attempt=await sent.json();
 await fs.writeFile(path.resolve(import.meta.dirname,'../../../.cache/workspace-checks/live-composer-attempt.json'),JSON.stringify(attempt,null,2));
 await expect(page.getByRole('region',{name:'Checks for this attempt'})).toContainText('Mixed source evidence');
 await expect.poll(async()=>{
  const current=await (await page.request.get('/api/workspace/'+id)).json();
  return current.attempts.find((a:any)=>a.id===attempt.attempt_id)?.status;
 },{timeout:210000,intervals:[1000,3000,5000]}).toBe('completed');
 await expect(page.getByText('Build, baseline checks, and supplied request checks passed. Ready for your review.',{exact:true})).toBeVisible();
 await page.reload();
 await page.locator('.saved-projects summary').click();
 await page.locator('.saved-projects').getByRole('button',{name:project.title,exact:true}).click();
 await expect(page.getByRole('region',{name:'Checks for this attempt'})).toContainText('Number of records: 3');
 await page.getByRole('region',{name:'Checks for this attempt'}).scrollIntoViewIfNeeded();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/19-live-expected-results.desktop.png'),fullPage:true});
});

test('Workbook upload preserves cell locations and missing formula results',async({page},info)=>{
 await page.goto('/#/workspace');
 await page.locator('input[type=file]').setInputFiles(path.resolve(import.meta.dirname,'../../../.cache/workspace-checks/development-workbook.xlsx'));
 await expect(page.getByText('9 nonempty cells · 2 worksheets · 2 formulas',{exact:true})).toBeVisible();
 await expect(page.getByText(/1 formulas have no saved result/)).toBeVisible();
 await page.getByText('Workbook sheets',{exact:true}).click();
 await expect(page.getByText('Notes · hidden · 1 cells',{exact:true})).toBeVisible();
 await page.getByText('Observations · B3',{exact:true}).click();
 const missing=page.locator('.records pre').filter({hasText:'=1+1'});
 await expect(missing).toContainText('"value": null');
 await expect(missing).toContainText('formula_result_unavailable');
 await page.getByText('Observations · B2',{exact:true}).click();
 await expect(page.locator('.records pre').filter({hasText:'"cell": "B2"'})).toContainText('"value": 0');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/20-workbook-intake.'+info.project.name+'.png'),fullPage:true});
});

test('Failed upload retains the original and offers explicit retry',async({page},info)=>{
 await page.goto('/#/workspace');
 const raw=Buffer.from('model,count\nDevelopment failure fixture,1,unexpected\n');
 await page.locator('input[type=file]').setInputFiles({name:'development-retained-failure.csv',mimeType:'text/csv',buffer:raw});
 await expect(page.getByRole('alert')).toContainText('different width');
 await expect(page.getByText('The original file is saved. Retry after fixing the extraction issue, or attach a corrected file.',{exact:true})).toBeVisible();
 const download=page.getByRole('link',{name:'Download original file',exact:true});
 expect(await (await page.request.get((await download.getAttribute('href'))!)).body()).toEqual(raw);
 const retry=page.getByRole('button',{name:'Retry extraction',exact:true});
 await expect(retry).toBeEnabled();
 const response=page.waitForResponse(r=>r.url().endsWith('/extract')&&r.request().method()==='POST');
 await retry.click();
 const result=await (await response).json();
 expect(result.status).toBe('extraction_failed');expect(result.record_count).toBe(0);
 await expect(retry).toBeEnabled();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/21-retained-upload-failure.'+info.project.name+'.png'),fullPage:true});
});

test('Structured proposal links quotes to their original sources',async({page},info)=>{
 const job=await (await page.request.get('/api/workspace/source-jobs/60df4f14c15746fd9a34b2232c9abc8c')).json();
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[{...job,status:'awaiting_confirmation',workspace_id:undefined}]}}));
 await page.goto('/#/workspace');
 const proposal=page.getByRole('region',{name:'Bonsai proposal'});
 await expect(proposal).toBeVisible();
 const records=proposal.locator('.structured-records article');
 for(let i=0;i<job.proposal.structure.records.length;i++) {
  const record=records.nth(i);await record.locator('summary').click();
  for(let j=0;j<job.proposal.structure.records[i].evidence.length;j++) {
   const item=job.proposal.structure.records[i].evidence[j];
   const citation=record.locator('.citation').nth(j);
   await expect(citation.locator('blockquote')).toHaveText(item.quote);
   const href=await citation.getByRole('link').getAttribute('href');
   expect(href).toContain('/sources/'+item.record_id.split(':')[0]+'/file');
   const source=job.source_examples.find((r:any)=>r.id===item.record_id);
   if(typeof source.locator.start_seconds==='number')expect(href).toContain('#t='+source.locator.start_seconds);
   expect((await page.request.get(href!.split('#')[0])).ok()).toBe(true);
  }
 }
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await proposal.locator('.citation a').last().scrollIntoViewIfNeeded();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/22-proposal-source-links.'+info.project.name+'.png'),fullPage:true});
});

test('Workstreams opens conversations and starts with a clear file message',async({page},info)=>{
 await page.goto('/#/workspace');
 const sidebar=page.getByRole('complementary',{name:'Workstreams',exact:true});
 await expect(sidebar.getByRole('heading',{name:'Workstreams',exact:true})).toBeVisible();
 await expect(page.getByRole('heading',{name:'What are we working on?',exact:true})).toBeVisible();
 await expect(page.getByLabel('Message Bonsai',{exact:true})).toBeVisible();
 await expect(page.locator('iframe')).toHaveCount(0);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/23-workstreams-start.'+info.project.name+'.png'),fullPage:true});
 await page.getByLabel('Search workstreams',{exact:true}).fill('S82065');
 await sidebar.getByRole('button').filter({hasText:'S82065.pdf'}).click();
 await expect(page.getByRole('region',{name:'Bonsai proposal'})).toBeVisible();
 await expect(page.getByRole('button',{name:'Yes, build this view'})).toBeEnabled();
 // Read-only inspection: never confirm the real PDF.
 await sidebar.getByRole('button',{name:'New workstream',exact:true}).click();
 await expect(page.getByRole('region',{name:'Bonsai proposal'})).toHaveCount(0);
 await page.getByLabel('Search workstreams',{exact:true}).fill('Development Workbook');
 await sidebar.getByRole('button').filter({hasText:'Development Workbook Evidence Audit'}).click();
 await expect(page.getByLabel('Describe the next change')).toBeVisible();
 await expect(page.getByRole('button',{name:'Evidence',exact:true})).toBeVisible();
 const restoreView=page.getByRole('button',{name:'Build saved revision',exact:true});
 if(await restoreView.isVisible())await restoreView.click();
 await expect(page.locator('iframe')).toBeVisible({timeout:45000});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/24-workstreams-conversation.'+info.project.name+'.png'),fullPage:true});
});

test('Workstream retains original request and proposal after reload',async({page},info)=>{
 const job=await (await page.request.get('/api/workspace/source-jobs/9626cb0ca71647b5be329b7766bbd695')).json();
 for(let pass=0;pass<2;pass++) {
  await page.goto('/#/workspace');
  const sidebar=page.getByRole('complementary',{name:'Workstreams',exact:true});
  await page.getByLabel('Search workstreams',{exact:true}).fill('Development Workbook');
  await sidebar.getByRole('button').filter({hasText:'Development Workbook Evidence Audit'}).click();
  const history=page.getByRole('region',{name:'Original workstream conversation'});
  await expect(history).toContainText(job.request);
  await expect(history).toContainText(job.proposal.interpretation.rationale);
  await expect(history.getByRole('link',{name:'Proposal evidence'})).toHaveAttribute('href',job.mlflow_url);
 }
 await page.getByRole('button',{name:'Data',exact:true}).click();
 await expect(page.getByRole('heading',{name:'development-workbook.xlsx',exact:true})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.getByRole('button',{name:'Preview',exact:true}).click();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/25-workstream-history.'+info.project.name+'.png'),fullPage:true});
});

test('Role composer preserves draft across tabs and sends attached data',async({page},info)=>{
 await page.goto('/#/workspace');
 const sidebar=page.getByRole('complementary',{name:'Workstreams',exact:true});
 await sidebar.getByRole('button',{name:'Data analyst',exact:true}).click();
 const tabs=page.getByRole('navigation',{name:'Workstream sections'});
 await expect(tabs.getByRole('button',{name:'Conversation',exact:true})).toHaveAttribute('aria-pressed','true');
 const message=page.getByLabel('Message Data analyst',{exact:true});
 const intent='Compare the observed values and preserve missing evidence.';
 await message.fill(intent);
 await expect(page.getByRole('button',{name:'Send ↑',exact:true})).toBeDisabled();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/26-role-composer.'+info.project.name+'.png'),fullPage:true});
 await page.locator('input[type=file]').setInputFiles({name:'role-composer-development.json',mimeType:'application/json',buffer:Buffer.from('[{"label":"A","value":0},{"label":"B","value":12}]')});
 await expect(page.getByRole('button',{name:'Send ↑',exact:true})).toBeEnabled();
 await tabs.getByRole('button',{name:/Files/}).click();
 await expect(page.getByRole('heading',{name:'role-composer-development.json',exact:true})).toBeVisible();
 await tabs.getByRole('button',{name:'Activity',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Runtime activity',exact:true})).toBeVisible();
 await tabs.getByRole('button',{name:'Conversation',exact:true}).click();
 await expect(message).toHaveValue(intent);
 await expect(page.locator('.source-summary')).not.toBeVisible();
 let payload:any;
 await page.route('**/api/workspace/sources/*/generate',async route=>{payload=route.request().postDataJSON();await route.fulfill({status:409,json:{error:'Development check: no inference submitted'}});});
 await page.getByRole('button',{name:'Send ↑',exact:true}).click();
 await expect(page.getByRole('alert')).toContainText('no inference submitted');
 expect(payload.request).toBe('Role: Data analyst\n\n'+intent);
 await expect(message).toHaveValue(intent);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/27-role-attached-message.'+info.project.name+'.png'),fullPage:true});
});

test('Revised workstream renders requested title and preserved evidence',async({page},info)=>{
 const job=await (await page.request.get('/api/workspace/source-jobs/6e83f104314444c88a3cb5b93fe79240')).json();
 expect(job.status).toBe('completed');
 await page.goto('/#/workspace');
 await page.getByLabel('Search workstreams',{exact:true}).fill('Observations and team requirements');
 await page.getByRole('complementary',{name:'Workstreams',exact:true}).getByRole('button').filter({hasText:'Observations and team requirements'}).click();
 const history=page.getByRole('region',{name:'Original workstream conversation'});
 await expect(history).toContainText('Use the title Observations and team requirements.');
 const frame=page.frameLocator('iframe');
 await expect(frame.getByRole('heading',{name:'Observations and team requirements',exact:true})).toBeVisible();
 await expect(frame.getByTestId('record-row')).toHaveCount(3);
 await expect(frame.getByText('Development fixture: model A has 12 observations.',{exact:true}).first()).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/28-revised-workstream.'+info.project.name+'.png'),fullPage:true});
});

test('Shared file tool preserves message and edit drafts stay with their workstream',async({page})=>{
 await page.goto('/#/workspace');
 const sidebar=page.getByRole('complementary',{name:'Workstreams',exact:true});
 const draft=page.getByLabel('Message Research analyst',{exact:true});
 await draft.fill('Keep this draft while I search my attached files.');
 await sidebar.getByRole('button',{name:'Search attached files',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Files for this workstream',exact:true})).toBeVisible();
 await expect(draft).toHaveValue('Keep this draft while I search my attached files.');
 await page.getByRole('navigation',{name:'Workstream sections'}).getByRole('button',{name:'Conversation',exact:true}).click();
 await sidebar.getByRole('button',{name:'Search attached files',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Files for this workstream',exact:true})).toBeVisible();
 await sidebar.getByRole('button',{name:'New workstream',exact:true}).click();
 await expect(page.getByRole('navigation',{name:'Workstream sections'}).getByRole('button',{name:'Conversation',exact:true})).toHaveAttribute('aria-pressed','true');
 const search=page.getByLabel('Search workstreams',{exact:true});
 await search.fill('Development Workbook');
 await sidebar.getByRole('button').filter({hasText:'Development Workbook Evidence Audit'}).click();
 await page.getByLabel('Describe the next change').fill('Draft for the workbook only.');
 await search.fill('Observations and team requirements');
 await sidebar.getByRole('button').filter({hasText:'Observations and team requirements'}).click();
 await expect(page.getByLabel('Describe the next change')).toHaveValue('');
 await page.getByLabel('Describe the next change').fill('A separate observations draft.');
 await search.fill('Development Workbook');
 await sidebar.getByRole('button').filter({hasText:'Development Workbook Evidence Audit'}).click();
 await expect(page.getByLabel('Describe the next change')).toHaveValue('Draft for the workbook only.');
});

test('Proposal visibly discloses an attachment omitted from context',async({page},info)=>{
 const job=await (await page.request.get('/api/workspace/source-jobs/6e83f104314444c88a3cb5b93fe79240')).json();
 // Display-only omission scenario. No stored evidence is rewritten.
 job.status='awaiting_confirmation';delete job.workspace_id;
 job.source_coverage={records_shown:1,records_total:3,coverage:'partial source coverage',member_coverage:[
  {source_id:'shown',filename:'included-development.txt',records_shown:1,records_total:1,represented:true},
  {source_id:'omitted',filename:'omitted-development.txt',records_shown:0,records_total:2,represented:false}]};
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[job]}}));
 await page.goto('/#/workspace');
 await page.getByRole('complementary',{name:'Workstreams',exact:true}).getByRole('button').filter({hasText:'2 attached files'}).click();
 const coverage=page.getByRole('region',{name:'Files included in this proposal'});
 await expect(coverage).toContainText('omitted-development.txt');
 await expect(coverage).toContainText('0 of 2 records included');
 await expect(coverage).toContainText('This proposal cannot establish findings about this file.');
 await expect(coverage).toContainText('Coverage describes the input, not verified understanding.');
 await coverage.scrollIntoViewIfNeeded();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await coverage.screenshot({path:path.resolve(import.meta.dirname,'../shots/29-proposal-coverage.'+info.project.name+'.png')});
});

test('Generated view keeps coverage behind an inspectable disclosure',async({page},info)=>{
 test.skip(!process.env.COVERAGE_PREVIEW_URL,'Requires isolated starter preview');
 await page.goto(process.env.COVERAGE_PREVIEW_URL!);
 const summary=page.getByText('Source coverage · 3 of 5 records supplied to Bonsai',{exact:true});
 await expect(summary).toBeVisible();
 const warning=page.getByText(/Not included in model context; this view cannot establish findings/);
 await expect(warning).not.toBeVisible();
 await summary.click();
 await expect(warning).toBeVisible();
 await expect(page.getByText(/omitted-development.txt/)).toBeVisible();
 await expect(page.getByTestId('record-row')).toHaveCount(3);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await summary.locator('..').screenshot({path:path.resolve(import.meta.dirname,'../shots/30-generated-coverage.'+info.project.name+'.png')});
 await summary.click();await expect(warning).not.toBeVisible();
});

test('Intake draft restores question and attachments across reload and role changes',async({page})=>{
 await page.goto('/#/workspace');
 const sidebar=page.getByRole('complementary',{name:'Workstreams',exact:true});
 await sidebar.getByRole('button',{name:'Data analyst',exact:true}).click();
 const message=page.getByLabel('Message Data analyst',{exact:true});
 const question='Group my records by release date and keep the original evidence.';
 await message.fill(question);
 await expect(page.getByText('Draft saved in this browser.',{exact:true})).toBeVisible();
 await page.reload();
 await sidebar.getByRole('button',{name:'Data analyst',exact:true}).click();
 await expect(message).toHaveValue(question);
 await page.locator('input[type=file]').setInputFiles({name:'draft-retention-development.json',mimeType:'application/json',buffer:Buffer.from('[{"release":"March","count":12}]')});
 await expect(page.getByRole('button',{name:'Send ↑',exact:true})).toBeEnabled();
 await sidebar.getByRole('button',{name:'Evidence reviewer',exact:true}).click();
 await expect(page.getByLabel('Message Evidence reviewer',{exact:true})).toHaveValue('');
 await sidebar.getByRole('button',{name:'Data analyst',exact:true}).click();
 await expect(message).toHaveValue(question);
 await expect(page.locator('.composer-files')).toContainText('draft-retention-development.json');
 await page.reload();
 await sidebar.getByRole('button',{name:'Data analyst',exact:true}).click();
 await expect(message).toHaveValue(question);
 await expect(page.locator('.composer-files')).toContainText('draft-retention-development.json');
 await expect(page.getByRole('button',{name:'Send ↑',exact:true})).toBeEnabled();
 await page.getByRole('button',{name:'Clear draft',exact:true}).click();
 await expect(message).toHaveValue('');
 await expect(page.locator('.composer-files')).toHaveCount(0);
 await page.reload();
 await sidebar.getByRole('button',{name:'Data analyst',exact:true}).click();
 await expect(message).toHaveValue('');
 await expect(page.locator('.composer-files')).toHaveCount(0);
});

test('Unavailable draft storage is disclosed without blocking the composer',async({page})=>{
 await page.addInitScript(()=>{
   const original=Storage.prototype.setItem;
   Storage.prototype.setItem=function(key:string,value:string){
     if(key.startsWith('bonsai-workstream-draft:'))throw new DOMException('Storage unavailable','QuotaExceededError');
     return original.call(this,key,value);
   };
 });
 await page.goto('/#/workspace');
 await page.getByRole('complementary',{name:'Workstreams',exact:true}).getByRole('button',{name:'Data analyst',exact:true}).click();
 const message=page.getByLabel('Message Data analyst',{exact:true});
 await message.fill('Keep my question usable when browser storage is unavailable.');
 await expect(page.getByText('Draft could not be saved in this browser. Keep this page open.',{exact:true})).toBeVisible();
 await page.getByRole('navigation',{name:'Workstream sections'}).getByRole('button',{name:'Files',exact:true}).click();
 await expect(message).toHaveValue('Keep my question usable when browser storage is unavailable.');
});

test('Generated view combines node selection and inclusive date windows',async({page},info)=>{
 test.skip(!process.env.DATE_PREVIEW_URL,'Requires isolated date exploration fixture');
 await page.goto(process.env.DATE_PREVIEW_URL!);
 await expect(page.getByTestId('record-row')).toHaveCount(5);
 await page.getByText('Explore by date',{exact:true}).click();
 await page.getByLabel('Group',{exact:true}).selectOption({label:'size: 27B (3)'});
 await expect(page.getByTestId('record-row')).toHaveCount(3);
 await page.getByLabel('From date',{exact:true}).fill('2026-07-01');
 await page.getByLabel('Through date',{exact:true}).fill('2026-07-01');
 await expect(page.getByTestId('record-row')).toHaveCount(1);
 await expect(page.getByTestId('record-row')).toHaveAttribute('data-record-id','development:2');
 await page.getByLabel('Include records without this date (1)',{exact:true}).check();
 await expect(page.getByTestId('record-row')).toHaveCount(2);
 await page.getByRole('button',{name:'Inspect development:2',exact:true}).click();
 const noteText='Development note on the release boundary: '+info.project.name;
 await page.getByLabel('Evidence note',{exact:true}).fill(noteText);
 await page.getByRole('button',{name:'Save note',exact:true}).click();
 await expect(page.getByText(noteText,{exact:true})).toBeVisible();
 await page.getByLabel('From date',{exact:true}).fill('2026-09-01');
 await expect(page.getByRole('alert')).toHaveText('From date must be on or before Through date.');
 await expect(page.getByTestId('record-row')).toHaveCount(0);
 await page.getByLabel('Through date',{exact:true}).fill('2026-09-30');
 await expect(page.getByTestId('record-row')).toHaveCount(2);
 await expect(page.getByText('The record selected for your note is outside the current filters.',{exact:true})).toBeVisible();
 await expect(page.getByText(/The chart shows the full dataset/)).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/31-date-exploration.'+info.project.name+'.png'),fullPage:true});
 await page.getByRole('button',{name:'Clear filters',exact:true}).click();
 await expect(page.getByTestId('record-row')).toHaveCount(5);
 await expect(page.getByLabel('From date',{exact:true})).toHaveValue('');
 await expect(page.getByLabel('Through date',{exact:true})).toHaveValue('');
});

test('Generated view zooms nodes without losing selection or overflowing the page',async({page},info)=>{
 test.skip(!process.env.DATE_PREVIEW_URL,'Requires isolated node exploration fixture');
 await page.goto(process.env.DATE_PREVIEW_URL!);
 const viewport=page.getByRole('region',{name:'Scrollable chart',exact:true});
 const chart=page.getByRole('region',{name:'Data visualization',exact:true});
 await expect(page.getByRole('button',{name:'Zoom out',exact:true})).toBeDisabled();
 await page.getByRole('button',{name:'Zoom in',exact:true}).click();
 await page.getByRole('button',{name:'Zoom in',exact:true}).click();
 expect(await chart.evaluate(element=>element.getBoundingClientRect().width)).toBe(1350);
 expect(await viewport.evaluate(element=>element.scrollWidth>element.clientWidth)).toBe(true);
 const node=page.getByRole('button',{name:'Explore size: 27B',exact:true});
 await node.scrollIntoViewIfNeeded();
 await node.click();
 await expect(page.getByText('Selected group: size: 27B',{exact:true})).toBeVisible();
 await expect(page.getByTestId('record-row')).toHaveCount(3);
 const data=await page.request.get(process.env.DATE_PREVIEW_URL!+'api/desktop').then(response=>response.json());
 const position=data.interaction.nodes.find((item:any)=>item.label==='size: 27B');
 const imageBox=await chart.locator('img').boundingBox();
 const nodeBox=await node.boundingBox();
 expect(Math.abs(nodeBox!.x+nodeBox!.width/2-imageBox!.x-position.x*1.5)).toBeLessThan(1);
 expect(Math.abs(nodeBox!.y+nodeBox!.height/2-imageBox!.y-position.y*1.5)).toBeLessThan(1);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/32-node-zoom.'+info.project.name+'.png'),fullPage:true});
 await page.getByRole('button',{name:'Fit chart',exact:true}).click();
 expect(await viewport.evaluate(element=>element.scrollWidth<=element.clientWidth+1)).toBe(true);
 await expect(page.getByTestId('record-row')).toHaveCount(3);
 await page.getByRole('button',{name:'Clear filters',exact:true}).click();
 await expect(page.getByTestId('record-row')).toHaveCount(5);
});
