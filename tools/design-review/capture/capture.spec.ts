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
 await proposal.locator('.record-review > summary').click();
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

test('Comparison discloses task changes and incomplete configuration',async({page},info)=>{
 const report=JSON.parse(await fs.readFile(path.resolve(import.meta.dirname,'../../../research/harness-alignment/CONFIGURATION-COMPARISON-AUDIT.json'),'utf8'));
 // Historical evidence plus an explicitly display-only missing-hardware scenario.
 report.configuration_complete=false;
 report.unverified_configuration={hardware_id:[0,1]};
 await page.route('**/api/workspace/*/comparison?*',route=>route.fulfill({json:report}));
 await page.goto('/#/workspace');
 await page.getByLabel('Search workstreams',{exact:true}).fill('Evidence Review: Requirements');
 await page.getByRole('complementary',{name:'Workstreams',exact:true}).getByRole('button').filter({hasText:'Evidence Review: Requirements vs. Measured Observations'}).click();
 await page.getByRole('button',{name:'Evidence',exact:true}).click();
 await page.getByRole('button',{name:'Compare attempts',exact:true}).click();
 await page.getByText('What changed between these attempts?',{exact:true}).click();
 await expect(page.getByText('Configuration evidence is incomplete.',{exact:true})).toBeVisible();
 await expect(page.getByText('hardware id: missing or unverified for attempt 1, 2.',{exact:true})).toBeVisible();
 await expect(page.getByText(/Task differences or missing fields:.*base_revision.*request_sha256/)).toBeVisible();
 await expect(page.getByText('Configuration differences: harness_revision.',{exact:true})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.locator('.comparison-context').screenshot({path:path.resolve(import.meta.dirname,'../shots/33-comparison-context.'+info.project.name+'.png')});
});

test('Proposal judgments are separate from build approval and exclude test labels',async({page},info)=>{
 const jid='6e83f104314444c88a3cb5b93fe79240';
 const response=await page.request.get('/api/workspace/source-jobs/'+jid);
 expect(response.ok()).toBe(true);
 const job=await response.json();
 expect(job.status).toBe('completed');
 await page.goto('/#/workspace');
 await page.getByLabel('Search workstreams',{exact:true}).fill('Observations and team requirements');
 await page.getByRole('complementary',{name:'Workstreams',exact:true}).getByRole('button').filter({hasText:'Observations and team requirements'}).click();
 await page.getByRole('button',{name:'Evidence',exact:true}).click();
 await page.getByText('Review source interpretation',{exact:true}).click();
 await expect(page.getByRole('region',{name:'Bonsai proposal',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'Yes, build this view',exact:true})).toHaveCount(0);
 await page.getByText('Review interpretation for the example dataset',{exact:true}).click();
 await page.getByLabel('Proposal reviewer',{exact:true}).fill('Codex browser verification');
 await page.getByRole('combobox',{name:'Proposal reviewer kind',exact:true}).selectOption('test');
 await page.getByLabel('Interpretation review note',{exact:true}).fill('Development UI check '+info.project.name+'; not a human acceptance.');
 await page.getByRole('button',{name:'Accept interpretation',exact:true}).click();
 await expect(page.getByText('Saved accept judgment by Codex browser verification (test).',{exact:true})).toBeVisible();
 const bundle=await page.request.get('/api/workspace/source-jobs/'+jid+'/review-export').then(r=>r.json());
 expect(bundle.example_count).toBe(0);
 expect(bundle.review_events.at(-1).reviewer_kind).toBe('test');
 const publicationResponse=page.waitForResponse(response=>response.request().method()==='POST' && response.url().endsWith('/'+jid+'/review-export'));
 await page.getByRole('button',{name:'Publish example bundle to MLflow',exact:true}).click();
 const publication=await (await publicationResponse).json();
 expect(publication.example_count).toBe(0);
 expect(publication.dataset_sha256).toBe(bundle.dataset_sha256);
 await expect(page.getByRole('link',{name:'Open dataset run',exact:true})).toHaveAttribute('href',publication.run_url);
 await fs.writeFile(path.resolve(import.meta.dirname,'../../../.cache/workspace-checks/proposal-publication-'+info.project.name+'.json'),JSON.stringify(publication,null,2));
 expect((await page.request.get('/api/workspace/source-jobs/'+jid).then(r=>r.json())).status).toBe('completed');
 await page.locator('.proposal-review').screenshot({path:path.resolve(import.meta.dirname,'../shots/34-proposal-review.'+info.project.name+'.png')});
});

test('Controlled edit preserves mixed evidence and composes type filtering with search',async({page},info)=>{
 test.skip(!process.env.CONTROLLED_PREVIEW_URL,'Requires a completed controlled-trial preview');
 const base=process.env.CONTROLLED_PREVIEW_URL!;
 await page.goto(base);
 const source=await page.request.get(base+'api/desktop').then(response=>response.json());
 await expect(page.getByTestId('record-row')).toHaveCount(3);
 for(const row of source.rows){
   const text=await page.locator('[data-record-id="'+row.id+'"]').getByTestId('record-data').textContent();
   expect(JSON.parse(text!)).toEqual(row.data);
 }
 const search=page.getByRole('searchbox',{name:'Search records',exact:true});
 await page.getByRole('button',{name:'Measured observations',exact:true}).click();
 await search.fill('repository');
 await expect(page.getByTestId('record-row')).toHaveCount(0);
 await page.getByRole('button',{name:'Spoken requirements',exact:true}).click();
 await expect(page.getByTestId('record-row')).toHaveCount(1);
 await expect(page.getByTestId('record-row')).toHaveAttribute('data-record-id',source.rows[2].id);
 await page.getByRole('button',{name:'Clear filters',exact:true}).click();
 await expect(search).toHaveValue('');
 await expect(page.getByTestId('record-row')).toHaveCount(3);
 const row=page.locator('[data-record-id="'+source.rows[0].id+'"]');
 await row.getByText('Supporting source passages',{exact:true}).click();
 const expected=Object.values(source.evidence_links) as {url:string;label:string}[];
 for(const link of await row.getByRole('link').all()){
   const href=await link.getAttribute('href');
   expect(expected.some(item=>item.url===href)).toBe(true);
 }
 await expect(row.getByRole('link')).not.toHaveCount(0);
 await row.getByRole('button',{name:'Inspect '+source.rows[0].id,exact:true}).click();
 const note='Controlled development check '+info.project.name+' '+Date.now();
 await page.getByRole('textbox',{name:'Evidence note',exact:true}).fill(note);
 await page.getByRole('button',{name:'Save note',exact:true}).click();
 await expect(page.getByText(note,{exact:true})).toBeVisible();
 await page.reload();
 await expect(page.getByText(note,{exact:true})).toBeVisible();
 const notes=await page.request.get(base+'api/annotations').then(response=>response.json());
 expect(notes.find((item:any)=>item.note===note).record_id).toBe(source.rows[0].id);
 if(process.env.CONTROLLED_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.CONTROLLED_SCREENSHOT_DIR,'view.'+info.project.name+'.png'),fullPage:true});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

test('Controlled edit records post-run filter selection semantics',async({page},info)=>{
 test.skip(!process.env.CONTROLLED_PREVIEW_URL || !process.env.CONTROLLED_SCREENSHOT_DIR,'Requires controlled-trial output folder');
 await page.goto(process.env.CONTROLLED_PREVIEW_URL!);
 await page.getByRole('button',{name:'Measured observations',exact:true}).click();
 const values:Record<string,string|null>={};
 for(const name of ['All records','Measured observations','Spoken requirements'])values[name]=await page.getByRole('button',{name,exact:true}).getAttribute('aria-pressed');
 const result={scope:'Post-run observational check; not a frozen success criterion',viewport:info.project.name,aria_pressed:values,
   selected_state_exposed:values['Measured observations']==='true' && values['All records']==='false' && values['Spoken requirements']==='false'};
 await fs.writeFile(path.join(process.env.CONTROLLED_SCREENSHOT_DIR!,'selection-semantics.'+info.project.name+'.json'),JSON.stringify(result,null,2));
 await page.screenshot({path:path.join(process.env.CONTROLLED_SCREENSHOT_DIR!,'selected-filter.'+info.project.name+'.png'),fullPage:true});
});

test('Workstream role navigation and focused composer',async({page},info)=>{
 await page.goto('/#/workspace');
 if(info.project.name==='mobile')await page.getByRole('button',{name:'Workstreams Choose a role or conversation'}).click();
 const role=page.getByRole('button',{name:'Data analyst',exact:true});
 await role.click();
 await expect(page.getByRole('button',{name:'Data analyst',exact:true,includeHidden:true})).toHaveAttribute('aria-pressed','true');
 const message=page.getByLabel('Message Data analyst',{exact:true});
 await expect(message).toBeEnabled();
 await page.getByRole('button',{name:'Compare evidence',exact:true}).click();
 await expect(message).toHaveValue(/Compare the evidence/);
 await page.getByRole('button',{name:'Files',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Files for this workstream'})).toBeVisible();
 await expect(message).toBeHidden();
 await page.getByRole('button',{name:'Activity',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Runtime activity'})).toBeVisible();
 await page.getByRole('button',{name:'Conversation',exact:true}).click();
 await expect(message).toHaveValue(/Compare the evidence/);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/35-workstream-composer.'+info.project.name+'.png'),fullPage:true});
});

test('Bonsai discusses intent before attachment and retains the reply',async({page},info)=>{
 test.skip(process.env.BONSAI_INTAKE_LIVE!=='1' || info.project.name!=='desktop','Explicit sequential development inference only');
 test.setTimeout(300000);
 await page.goto('/#/workspace');
 await page.getByRole('button',{name:'Data analyst',exact:true}).click();
 const message=page.getByLabel('Message Data analyst',{exact:true});
 await expect(message).toBeEnabled();
 await message.fill('I want to compare planned release dates with actual release dates. I have not attached any files yet. What evidence should I bring?');
 const sent=page.waitForResponse(r=>r.url().endsWith('/source-jobs/intake') && r.request().method()==='POST');
 await page.getByRole('button',{name:'Send ↑',exact:true}).click();
 const response=await sent;expect(response.ok()).toBe(true);const job=await response.json();
 const folder=path.resolve('.cache/intake-live-proof');await fs.mkdir(folder,{recursive:true});
 await fs.writeFile(path.join(folder,'started.json'),JSON.stringify(job,null,2));
 const conversation=page.getByRole('region',{name:'Conversation before attachment'});
 await expect(conversation.locator('.intake-reply')).toBeVisible({timeout:260000});
 const reply=await conversation.locator('.intake-reply').innerText();expect(reply.length).toBeGreaterThan(20);
 await page.reload();
 await page.getByRole('button',{name:'Data analyst',exact:true}).click();
 await expect(page.locator('.intake-reply')).toHaveText(reply);
 await expect(page.getByLabel('Message Data analyst',{exact:true})).toBeEnabled();
 const terminal=await (await page.request.get('/api/workspace/source-jobs/'+job.id)).json();
 expect(terminal.status).toBe('completed');expect(terminal.evidence_error).toBeUndefined();
 await fs.writeFile(path.join(folder,'completed.json'),JSON.stringify(terminal,null,2));
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/36-intake-conversation.desktop.png'),fullPage:true});
});

test('Prior intake discussion reaches attached source proposal',async({page},info)=>{
 test.skip(process.env.BONSAI_INTAKE_HANDOFF!=='1' || info.project.name!=='desktop','Explicit development proposal only');
 test.setTimeout(300000);
 const folder=path.resolve('.cache/intake-live-proof');
 const prior=JSON.parse(await fs.readFile(path.join(folder,'completed.json'),'utf8'));
 await page.addInitScript(({id})=>localStorage.setItem('bonsai-workstream-draft:v1:Data%20analyst:new',JSON.stringify({version:1,intent:'',intakeJobId:id,attached:[],sourceId:'',applyReviews:false})),{id:prior.id});
 await page.goto('/#/workspace');await page.getByRole('button',{name:'Data analyst',exact:true}).click();
 await expect(page.locator('.intake-reply')).toBeVisible();
 await page.locator('input[type=file]').setInputFiles({name:'development-release-dates.csv',mimeType:'text/csv',buffer:Buffer.from('release_id,planned_date,actual_date,status\nexample-a,2026-01-10,2026-01-12,completed\nexample-b,2026-02-10,,pending\n')});
 const message=page.getByLabel('Message Data analyst',{exact:true});await expect(message).toBeEnabled();
 await message.fill('One product. Compare the planned and actual dates in these development records. Keep the missing actual date unknown and show source links.');
 const sent=page.waitForResponse(r=>/\/sources\/[a-f0-9]+\/generate$/.test(r.url()) && r.request().method()==='POST');
 await page.getByRole('button',{name:'Send ↑',exact:true}).click();
 const response=await sent;expect(response.ok()).toBe(true);
 expect(response.request().postDataJSON().intake_job_id).toBe(prior.id);
 const job=await response.json();await fs.writeFile(path.join(folder,'handoff-started.json'),JSON.stringify(job,null,2));
 await expect.poll(async()=>{const state=await (await page.request.get('/api/workspace/source-jobs/'+job.id)).json();await fs.writeFile(path.join(folder,'handoff-latest.json'),JSON.stringify(state,null,2));return state.status;},{timeout:260000,intervals:[2000]}).toBe('awaiting_confirmation');
 await expect(page.getByRole('region',{name:'Visualization jobs'})).toBeVisible();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/37-intake-handoff.desktop.png'),fullPage:true});
});

test('Saved intake reply is readable on desktop and mobile',async({page},info)=>{
 test.skip(process.env.BONSAI_INTAKE_REVIEW!=='1','Requires saved development reply; no inference');
 const prior=JSON.parse(await fs.readFile(path.resolve('.cache/intake-live-proof/completed.json'),'utf8'));
 await page.addInitScript(({id})=>localStorage.setItem('bonsai-workstream-draft:v1:Data%20analyst:new',JSON.stringify({version:1,intent:'',intakeJobId:id,attached:[],sourceId:'',applyReviews:false})),{id:prior.id});
 await page.goto('/#/workspace');
 if(info.project.name==='mobile')await page.getByRole('button',{name:'Workstreams Choose a role or conversation'}).click();
 await page.getByRole('button',{name:'Data analyst',exact:true}).click();
 await expect(page.locator('.intake-reply')).toHaveText(prior.reply);
 await expect(page.getByRole('heading',{name:'What would you like to understand?'})).toBeHidden();
 await expect(page.getByLabel('Message Data analyst',{exact:true})).toBeEnabled();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/36-intake-conversation.'+info.project.name+'.png'),fullPage:true});
});

test('Saved workstream reopens without browser draft storage',async({page},info)=>{
 const prior=JSON.parse(await fs.readFile(path.resolve('.cache/intake-live-proof/completed.json'),'utf8'));
 await page.goto('/#/workspace');
 await page.evaluate(()=>localStorage.clear());await page.reload();
 if(info.project.name==='mobile')await page.getByRole('button',{name:'Workstreams Choose a role or conversation'}).click();
 const stream=page.locator('.stream-row').filter({has:page.locator('strong',{hasText:prior.request})});
 await expect(stream).toHaveCount(1);await stream.click();
 await expect(page.locator('.intake-reply')).toHaveText(prior.reply);
 await expect(page.getByRole('region',{name:'Visualization jobs'})).toContainText('Planned vs Actual Release Dates');
 await page.getByRole('button',{name:/^Files/}).click();
 await expect(page.getByRole('heading',{name:'development-release-dates.csv',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Conversation',exact:true}).click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 if(info.project.name==='desktop'){
  const thread=await page.locator('.conversation-thread').boundingBox();const composer=await page.locator('.message-compose').boundingBox();
  expect(thread!.y+thread!.height).toBeLessThanOrEqual(composer!.y);
  await page.locator('.conversation-thread').evaluate(el=>el.scrollTop=el.scrollHeight);
 }
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/38-recovered-workstream.'+info.project.name+'.png'),fullPage:true});
});

test('Expected results captures ordered selection checks without inference',async({page},info)=>{
 const id='32403b0a26bd447abcfebd26c9ef3b59';
 const project=await (await page.request.get('/api/workspace/'+id)).json();
 await page.goto('/#/workspace');
 if(info.project.name==='mobile')await page.getByRole('button',{name:'Workstreams Choose a role or conversation'}).click();
 await page.locator('.stream-row').filter({has:page.locator('strong',{hasText:project.title})}).click();
 await page.getByLabel('Describe the next change').fill('Keep the measured-observations filter selected after clicking it.');
 await page.locator('.expectations summary').click();
 await page.getByRole('button',{name:'Add expected result',exact:true}).click();
 await page.getByRole('combobox',{name:'Check 1',exact:true}).selectOption('click');
 await page.getByLabel('Exact label',{exact:true}).fill('Measured observations');
 await expect(page.getByRole('button',{name:'Send request',exact:true})).toBeDisabled();
 await page.getByRole('button',{name:'Add expected result',exact:true}).click();
 await page.getByRole('combobox',{name:'Check 2',exact:true}).selectOption('pressed');
 await page.getByLabel('Exact label',{exact:true}).nth(1).fill('Measured observations');
 await page.getByRole('combobox',{name:'Expected selection',exact:true}).selectOption('false');
 await page.getByRole('combobox',{name:'Expected selection',exact:true}).selectOption('true');
 let submitted:any;
 await page.route('**/api/workspace/'+id+'/attempts',async route=>{
  submitted=route.request().postDataJSON();await route.fulfill({status:409,json:{error:'Development interception: no inference submitted'}});
 });
 await page.getByRole('button',{name:'Send request',exact:true}).click();
 await expect(page.getByRole('alert')).toContainText('Development interception');
 expect(submitted.request_checks).toEqual([
  {target:{role:'button',name:'Measured observations'},action:'click',value:null},
  {target:{role:'button',name:'Measured observations'},action:'pressed',value:true}
 ]);
 await expect(page.getByLabel('Exact label',{exact:true}).nth(1)).toHaveValue('Measured observations');
 await page.locator('.expectations').scrollIntoViewIfNeeded();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/39-selection-checks.'+info.project.name+'.png'),fullPage:true});
});

test('Video evidence keeps speech and frame navigation separate',async({page},info)=>{
 test.skip(process.env.VIDEO_SPEECH_REVIEW!=='1','Requires completed development video extraction');
 const source=JSON.parse(await fs.readFile(path.resolve('.cache/video-speech-development/live/merged.json'),'utf8'));
 const speech=source.records.filter((r:any)=>r.locator.evidence_channel==='speech');
 const frames=source.records.filter((r:any)=>r.locator.evidence_channel==='visual');
 expect(speech.length).toBeGreaterThan(0);expect(frames.length).toBeGreaterThan(0);
 await page.goto('/#/workspace');await page.getByRole('button',{name:'Files',exact:true}).click();
 await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(source.source_id);
 await expect(page.getByRole('button',{name:'Speech transcribed',exact:true})).toBeDisabled();
 await expect(page.getByText('Speech extraction evidence',{exact:true})).toBeVisible();
 const transcript=page.locator('.transcript');
 await expect(transcript.getByRole('button',{name:/^Speech ·/})).toHaveCount(speech.length);
 await expect(transcript.getByRole('button',{name:/^Frame ·/})).toHaveCount(frames.length);
 await transcript.getByRole('button',{name:/^Speech ·/}).last().click();
 await expect.poll(async()=>page.locator('video').evaluate((el:HTMLVideoElement)=>el.currentTime)).toBeCloseTo(speech.at(-1).locator.start_seconds,1);
 await transcript.getByRole('button',{name:/^Frame ·/}).first().click();
 await expect.poll(async()=>page.locator('video').evaluate((el:HTMLVideoElement)=>el.currentTime)).toBeCloseTo(frames[0].locator.time_seconds,1);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await expect.poll(async()=>page.locator('video').evaluate((el:HTMLVideoElement)=>el.readyState)).toBeGreaterThanOrEqual(2);
 await expect.poll(async()=>page.locator('video').evaluate((el:HTMLVideoElement)=>el.seeking)).toBe(false);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/40-video-speech.'+info.project.name+'.png'),fullPage:true});
});

test('Narrated video graph separates evidence groups and preserves source values',async({page},info)=>{
 test.skip(!process.env.VIDEO_REVISION_PREVIEW_URL,'Requires corrected development video preview');
 const base=process.env.VIDEO_REVISION_PREVIEW_URL!;
 const original=JSON.parse(await fs.readFile(path.resolve('.cache/video-speech-development/live/merged.json'),'utf8'));
 const model=await (await page.request.get(base+'api/desktop')).json();
 expect(model.chart.component).toBe('ForceDirectedGraph');expect(model.plan.view.groupBy).toEqual(['evidence_channel']);
 expect(model.rows).toHaveLength(5);expect(model.chart.props.nodes).toHaveLength(3);expect(model.chart.props.edges).toHaveLength(2);
 expect(model.node_membership[model.grouping_root.id]).toHaveLength(5);
 await page.goto(base);
 await expect(page.getByRole('heading',{name:'Video evidence: observations and requirements',exact:true})).toBeVisible();
 for(const channel of ['speech','visual']){
  const expected=original.records.filter((r:any)=>r.locator.evidence_channel===channel);
  const node=model.chart.props.nodes.find((n:any)=>n.label==='evidence_channel: '+channel);
  await page.getByRole('button',{name:'Explore '+node.label,exact:true}).click();
  await expect(page.getByTestId('record-row')).toHaveCount(expected.length);
  const visible=[];for(const row of await page.getByTestId('record-data').all())visible.push(JSON.parse((await row.textContent())!));
  for(const record of expected)expect(visible.some(data=>Object.entries(record.data).every(([key,value])=>data[key]===value))).toBe(true);
  if(channel==='speech'){
   await expect(page.getByRole('region',{name:'Source records'})).toContainText('The team needs to inspect model releases by size');
   const row=page.getByTestId('record-row').first();await row.getByText('Supporting source passages',{exact:true}).click();
   await expect(row.getByRole('link')).not.toHaveCount(0);
   for(const link of await row.getByRole('link').all())expect(await link.getAttribute('href')).toContain(original.source_id);
  }
 }
 await page.getByRole('button',{name:'Clear filters',exact:true}).click();await expect(page.getByTestId('record-row')).toHaveCount(5);
 const target=model.rows[0];await page.getByRole('button',{name:'Inspect '+target.id,exact:true}).click();
 const note='Development video evidence check '+info.project.name+' '+Date.now();
 await page.getByRole('textbox',{name:'Evidence note',exact:true}).fill(note);await page.getByRole('button',{name:'Save note',exact:true}).click();
 await expect(page.getByText(note,{exact:true})).toBeVisible();await page.reload();await expect(page.getByText(note,{exact:true})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/41-video-evidence-graph.'+info.project.name+'.png'),fullPage:true});
});

test('Confirmed development video build can retry its recorded render failure',async({page},info)=>{
 test.skip(process.env.VIDEO_BUILD_RETRY_LIVE!=='1' || info.project.name!=='desktop','Explicit development build retry only');
 test.setTimeout(180000);
 const jid='8bec94ab1ed34e7e8e0c4e28e1c06854';
 const prior=await (await page.request.get('/api/workspace/source-jobs/'+jid)).json();expect(prior.status).toBe('failed');expect(prior.workspace_id).toBeUndefined();
 await page.setExtraHTTPHeaders({'X-Eval-Actor':'codex-development-retry-browser'});
 await page.goto('/#/workspace');
 await page.locator('.stream-row').filter({has:page.locator('strong',{hasText:'development-narrated-observations.mp4'})}).click();
 const response=page.waitForResponse(r=>r.url().endsWith('/'+jid+'/retry-build') && r.request().method()==='POST');
 await page.getByRole('button',{name:'Retry confirmed build',exact:true}).click();expect((await response).ok()).toBe(true);
 await expect.poll(async()=>{const job=await (await page.request.get('/api/workspace/source-jobs/'+jid)).json();await fs.writeFile(path.resolve('.cache/video-speech-revision/retry-latest.json'),JSON.stringify(job,null,2));return job.status;},{timeout:150000,intervals:[1500]}).toBe('completed');
 await expect(page.getByRole('button',{name:'Open editable project',exact:true})).toBeVisible();
});

test('First message stays together with tabs and role tools',async({page},info)=>{
 await page.route('**/api/workspace/source-jobs',async route=>{const response=await route.fetch();const body=await response.json();await route.fulfill({json:{...body,jobs:body.jobs.filter((job:any)=>!['queued','running'].includes(job.status))}});});
 await page.goto('/#/workspace');
 const sections=page.getByRole('navigation',{name:'Workstream sections'});
 await expect(sections.getByRole('button',{name:'Conversation',exact:true})).toBeVisible();
 const message=page.getByRole('textbox',{name:'Message Research analyst',exact:true});
 await expect(message).toBeVisible();
 await page.getByRole('button',{name:'Find patterns',exact:true}).click();
 await expect(message).toBeFocused();
 await expect(message).toHaveValue(/Group related records/);
 const intro=await page.locator('.conversation-intro').boundingBox();
 const composer=await page.locator('.message-compose').boundingBox();
 expect(composer!.y-(intro!.y+intro!.height)).toBeLessThan(50);
 await sections.getByRole('button',{name:'Files',exact:true}).click();
 await expect(message).toBeHidden();
 await expect(page.getByRole('heading',{name:'Files for this workstream'})).toBeVisible();
 await sections.getByRole('button',{name:'Activity',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Runtime activity'})).toBeVisible();
 await sections.getByRole('button',{name:'Conversation',exact:true}).click();
 await expect(message).toHaveValue(/Group related records/);
 if(info.project.name==='mobile')await page.locator('.mobile-stream-toggle').click();
 await page.getByRole('button',{name:'Data analyst',exact:true}).click();
 await expect(page.getByRole('textbox',{name:'Message Data analyst',exact:true})).toBeVisible();
 if(info.project.name==='mobile')await page.locator('.mobile-stream-toggle').click();
 await page.locator('.shared-tools summary').click();
 await page.getByRole('button',{name:'Search attached files',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Files for this workstream'})).toBeVisible();
 if(info.project.name==='mobile')await page.locator('.mobile-stream-toggle').click();
 await sections.getByRole('button',{name:'Conversation',exact:true}).click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/42-first-message.'+info.project.name+'.png'),fullPage:true});
 // Exercise the first-message transport without spending an inference or fabricating a reply.
 let submitted:any;
 await page.route('**/api/workspace/source-jobs/intake',async route=>{
   submitted=route.request().postDataJSON();
   await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Development check: model unavailable'})});
 });
 const roleMessage=page.getByRole('textbox',{name:'Message Data analyst',exact:true});
 await roleMessage.fill('Help me compare the evidence in my documents.');
 await roleMessage.press('Control+Enter');
 await expect(page.getByText('Error: Development check: model unavailable', {exact:true})).toBeVisible();
 expect(submitted.role).toBe('Data analyst');
 expect(submitted.message).toBe('Help me compare the evidence in my documents.');
 await expect(roleMessage).toHaveValue(submitted.message);

});

test('Drop desktop data into the first message without losing the request',async({page},info)=>{
 await page.route('**/api/workspace/source-jobs',async route=>{const response=await route.fetch();const body=await response.json();await route.fulfill({json:{...body,jobs:body.jobs.filter((job:any)=>!['queued','running'].includes(job.status))}});});
 await page.setExtraHTTPHeaders({'X-Eval-Actor':'codex-development-file-drop'});
 await page.goto('/#/workspace');
 const message=page.getByRole('textbox',{name:'Message Research analyst',exact:true});
 await expect(message).toBeVisible();
 await message.fill('Compare these development records with their original sources.');
 const transfer=await page.evaluateHandle(()=>{
   const data=new DataTransfer();
   data.items.add(new File(['team,count\nResearch,0\nDesign,12\n'],'development-dropped-records.csv',{type:'text/csv'}));
   return data;
 });
 await page.locator('body').dispatchEvent('dragenter',{dataTransfer:transfer});
 await expect(page.getByText('Drop files into this workstream',{exact:true})).toBeVisible();
 await page.locator('body').dispatchEvent('drop',{dataTransfer:transfer});
 await expect(page.locator('.composer-files')).toContainText('development-dropped-records.csv');
 await expect(page.locator('.composer-files')).toContainText('2 records');
 await expect(message).toHaveValue('Compare these development records with their original sources.');
 await expect(message).toBeFocused();
 await expect(page.getByRole('button',{name:'Send ↑',exact:true})).toBeEnabled();
 await page.getByRole('button',{name:'Inspect files',exact:true}).click();
 await expect(page.locator('.source-summary')).toContainText('2 records');
 await page.getByText('Record 1',{exact:true}).click();
 await expect(page.locator('.records')).toContainText('"count": "0"');
 await page.getByRole('navigation',{name:'Workstream sections'}).getByRole('button',{name:'Conversation',exact:true}).click();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/43-dropped-files.'+info.project.name+'.png'),fullPage:true});
 await transfer.dispose();
});

test('Mixed attachment readiness blocks a partial source set',async({page})=>{
 await page.route('**/api/workspace/source-jobs',async route=>{const response=await route.fetch();const body=await response.json();await route.fulfill({json:{...body,jobs:body.jobs.filter((job:any)=>!['queued','running'].includes(job.status))}});});
 const sources:any[]=[];
 await page.route('**/api/workspace/sources',async route=>{
   if(route.request().method()==='POST'){
     const name=decodeURIComponent(route.request().headers()['x-source-filename']);
     const failed=name==='needs-extraction.pdf';
     const value={source_id:failed?'development-pending':'development-ready',filename:name,sha256:'development',kind:failed?'document':'table',status:failed?'extraction_failed':'extracted',record_count:failed?0:2,records:[],review:{latest:{}}};
     sources.push(value);await route.fulfill({json:value});
   }else await route.fulfill({json:{sources}});
 });
 await page.goto('/#/workspace');
 const message=page.getByRole('textbox',{name:'Message Research analyst',exact:true});
 await expect(message).toBeVisible();await message.fill('Compare all of the attached source evidence.');
 await page.locator('input[type=file]').setInputFiles([{name:'needs-extraction.pdf',mimeType:'application/pdf',buffer:Buffer.from('development failure fixture')},{name:'ready.csv',mimeType:'text/csv',buffer:Buffer.from('a\n1\n2\n')}]);
 await expect(page.getByRole('region',{name:'File intake summary'})).toContainText('Some files need attention');
 await expect(page.getByRole('button',{name:'Send ↑',exact:true})).toBeDisabled();
 await page.getByRole('button',{name:'Remove needs-extraction.pdf',exact:true}).last().click();
 await expect(page.getByRole('region',{name:'File intake summary'})).toContainText('Your files are ready to discuss');
 await expect(page.getByRole('button',{name:'Send ↑',exact:true})).toBeEnabled();
});

test('Proposal findings expose readable sources and draft a targeted correction',async({page},info)=>{
 const job=JSON.parse(await fs.readFile(path.resolve('.cache/workspace-live-v3-20260921/workspace/source-jobs/2c74cd345eaf42e2a5ce399b4e4f195a/status.json'),'utf8'));
 // Pin the reviewed development proposal in this browser; never confirm or mutate its server state.
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[{...job,status:'awaiting_confirmation'}]}}));
 await page.goto('/#/workspace');
 const nav=page.getByRole('navigation',{name:'Workstream sections'});
 await nav.getByRole('button',{name:'Files',exact:true}).click();
 await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(job.source_id);
 await nav.getByRole('button',{name:'Conversation',exact:true}).click();
 const finding=page.locator('.proposal .finding').first();
 await finding.locator('summary').first().click();
 await expect(finding.locator('.source-comparison article')).toHaveCount(2);
 await expect(finding.locator('.source-comparison')).toContainText('annotated (2).mp4');
 await expect(finding.locator('.source-comparison')).toContainText('annotated (3).mp4');
 await expect(finding.locator('.source-comparison')).toContainText('UNREVIEWED BONSAI');
 await expect(finding.locator('a').first()).toHaveAttribute('href',/#t=0$/);
 await finding.scrollIntoViewIfNeeded();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/44-finding-evidence.'+info.project.name+'.png'),fullPage:true});
 await finding.getByRole('button',{name:'Question this finding'}).click();
 const feedback=page.getByRole('textbox',{name:'Clarify or change this proposal'});
 await expect(feedback).toBeFocused();
 await expect(feedback).toHaveValue('Please recheck this finding against each cited source: “'+job.proposal.interpretation.findings[0].text+'”');
 await expect(page.getByRole('button',{name:'Discuss this change',exact:true})).toBeEnabled();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

test('Generated view plays the selected cited video beside notes',async({page},info)=>{
 const preview=JSON.parse(await fs.readFile(path.resolve('.cache/inline-media-inspection/preview.json'),'utf8'));
 await page.goto(preview.url);
 await expect(page.getByTestId('record-row')).toHaveCount(3);
 const first=page.getByTestId('record-row').first();await first.getByRole('button',{name:/Inspect /}).click();
 const media=page.getByRole('region',{name:'Selected source media'});
 await expect(media.locator('video')).toHaveCount(1);
 await expect.poll(()=>media.locator('video').evaluate((video:HTMLVideoElement)=>video.readyState)).toBeGreaterThanOrEqual(1);
 await expect.poll(()=>media.locator('video').evaluate((video:HTMLVideoElement)=>video.videoWidth)).toBeGreaterThan(0);
 expect(await media.locator('video').evaluate((video:HTMLVideoElement)=>video.paused)).toBe(true);
 await expect(media.locator('video')).toHaveAttribute('src',/53b4e713.*#t=0/);
 await media.locator('video').evaluate((video:HTMLVideoElement)=>video.play());
 await expect.poll(()=>media.locator('video').evaluate((video:HTMLVideoElement)=>video.currentTime)).toBeGreaterThan(.1);
 await media.locator('video').evaluate((video:HTMLVideoElement)=>video.pause());
 await page.getByTestId('record-row').nth(1).getByRole('button',{name:/Inspect /}).click();
 await expect(media.locator('video')).toHaveAttribute('src',/ffc683c5.*#t=0/);
 await expect.poll(()=>media.locator('video').evaluate((video:HTMLVideoElement)=>video.videoWidth)).toBeGreaterThan(0);
 await expect(page.getByRole('textbox',{name:'Evidence note',exact:true})).toBeVisible();
 await media.scrollIntoViewIfNeeded();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/45-inline-source-media.'+info.project.name+'.png'),fullPage:true});
});

test('Source type and nonzero timestamps survive structured media evidence',async({page},info)=>{
 for(const kind of ['video','audio']){
  const preview=JSON.parse(await fs.readFile(path.resolve('.cache/media-timestamp-verification/'+kind+'-preview.json'),'utf8'));
  await page.goto(preview.url);
  const data=await (await page.request.get(preview.url+'api/desktop')).json();
  const row=data.rows.find((row:any)=>row.locator.source_evidence.some((p:any)=>p.locator.start_seconds>0));
  expect(row).toBeTruthy();
  const time=row.locator.source_evidence.find((p:any)=>p.locator.start_seconds>0).locator.start_seconds;
  await page.getByRole('button',{name:'Inspect '+row.id,exact:true}).click();
  const media=page.getByRole('region',{name:'Selected source media'}).locator(kind);
  await expect(media).toHaveCount(1);
  await expect.poll(()=>media.evaluate((v:HTMLMediaElement)=>v.readyState)).toBeGreaterThanOrEqual(1);
  await expect.poll(()=>media.evaluate((v:HTMLMediaElement)=>v.currentTime)).toBeCloseTo(time,1);
  if(kind==='video')await expect.poll(()=>media.evaluate((v:HTMLVideoElement)=>v.videoWidth)).toBeGreaterThan(0);
  await media.evaluate((v:HTMLMediaElement)=>v.play());
  await expect.poll(()=>media.evaluate((v:HTMLMediaElement)=>v.currentTime)).toBeGreaterThan(time+.1);
  await media.evaluate((v:HTMLMediaElement)=>v.pause());
  await expect(page.getByRole('textbox',{name:'Evidence note',exact:true})).toBeVisible();
  await media.scrollIntoViewIfNeeded();
  await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/46-'+kind+'-timestamp.'+info.project.name+'.png'),fullPage:true});
 }
});

test('Evidence note drafts remain bound to their record during a save',async({page},info)=>{
 await page.setExtraHTTPHeaders({'X-Eval-Actor':'codex-development-note-draft-check'});
 const preview=JSON.parse(await fs.readFile(path.resolve('.cache/note-draft-verification/preview.json'),'utf8'));
 await page.goto(preview.url);
 const data=await (await page.request.get(preview.url+'api/desktop')).json();
 const a=data.rows[0],b=data.rows[1];
 const select=(row:any)=>page.getByRole('button',{name:'Inspect '+row.id,exact:true}).click();
 const note=page.getByRole('textbox',{name:'Evidence note',exact:true});
 const textA='Development A '+info.project.name+' '+Date.now();const textB='Development B retained draft';
 await select(a);await note.fill(textA);
 await select(b);await expect(note).toHaveValue('');await note.fill(textB);
 await select(a);await expect(note).toHaveValue(textA);
 let release:()=>void=()=>{};const gate=new Promise<void>(resolve=>release=resolve);
 let sent:any;
 await page.route('**/api/annotations',async route=>{
  if(route.request().method()!=='POST')return route.continue();
  sent=route.request().postDataJSON();await gate;
  const response=await route.fetch();await route.fulfill({response});
 });
 await page.getByRole('button',{name:'Save note',exact:true}).click();
 await expect.poll(()=>sent?.record_id).toBe(a.id);
 await select(b);await expect(note).toHaveValue(textB);
 release();await expect(page.getByRole('button',{name:'Save note',exact:true})).toBeEnabled();
 await expect(note).toHaveValue(textB);
 await select(a);await expect(note).toHaveValue('');
 const saved=await (await page.request.get(preview.url+'api/annotations')).json();
 const entry=saved.find((n:any)=>n.note===textA);
 expect(entry.record_id).toBe(a.id);expect(entry.record_snapshot.data).toEqual(a.data);
 expect(entry.review_origin).toBe('codex-development-note-draft-check');
 await select(b);await expect(note).toHaveValue(textB);
 await page.route('**/api/annotations',route=>route.request().method()==='POST' ? route.fulfill({status:503,json:{error:'Development save failure'}}) : route.continue());
 await page.getByRole('button',{name:'Save note',exact:true}).click();
 await expect(page.getByRole('alert')).toContainText('Development save failure');
 await expect(note).toHaveValue(textB);
 await expect(page.getByRole('button',{name:'Save note',exact:true})).toBeEnabled();
});

test('Workstream sidebar separates conversations from file activity',async({page},info)=>{
 await page.goto('/#/workspace');
 await expect(page.getByRole('textbox',{name:'Message Research analyst',exact:true})).toBeVisible();
 if(info.project.name==='mobile')await page.locator('.mobile-stream-toggle').click();
 const sidebar=page.getByRole('complementary',{name:'Workstreams'});
 await expect(sidebar.getByRole('button',{name:'New workstream',exact:true})).toHaveCount(1);
 const views=sidebar.locator('details.stream-group').filter({has:page.locator('summary', {hasText:'Saved views'})});
 const files=sidebar.locator('details.stream-group').filter({has:page.locator('summary', {hasText:'Files & activity'})});
 await expect(views).not.toHaveAttribute('open','');
 await expect(files).not.toHaveAttribute('open','');
 await files.locator('summary').click();
 await expect(files).toHaveAttribute('open','');
 await files.locator('summary').click();
 await sidebar.getByRole('textbox',{name:'Search workstreams'}).fill('development');
 await expect(files).toHaveAttribute('open','');
 await expect(views).toHaveAttribute('open','');
 await sidebar.getByRole('textbox',{name:'Search workstreams'}).fill('');
 await expect(files).not.toHaveAttribute('open','');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/47-workstream-sidebar.'+info.project.name+'.png'),fullPage:true});
});

test('Generated video stage view preserves values and cited playback',async({page},info)=>{
 const preview=JSON.parse(await fs.readFile(path.resolve('.cache/video-three-stage-explicit-repair/preview.json'),'utf8'));
 await page.goto(preview.url);
 await expect(page.getByTestId('record-row')).toHaveCount(3);
 const media=page.getByRole('region',{name:'Selected source media'});
 for(const [index,stage,count,seconds] of [[0,'Intake',12,0],[1,'Review',7,2.875],[2,'Approved',3,5.75]] as const){
   const row=page.getByTestId('record-row').nth(index);
   await row.locator('details.raw-data summary').click();
   expect(JSON.parse(await row.getByTestId('record-data').innerText())).toEqual({stage,record_count:count,sample_seconds:seconds});
   await row.getByRole('button',{name:/Inspect /}).click();
   await expect(media.locator('video')).toHaveCount(1);
   await expect.poll(()=>media.locator('video').evaluate((v:HTMLVideoElement)=>v.readyState)).toBeGreaterThanOrEqual(1);
   await expect.poll(()=>media.locator('video').evaluate((v:HTMLVideoElement)=>v.currentTime)).toBeCloseTo(seconds,1);
   expect(await media.locator('video').evaluate((v:HTMLVideoElement)=>v.videoWidth)).toBeGreaterThan(0);
   await expect(page.getByRole('textbox',{name:'Evidence note',exact:true})).toBeVisible();
 }
 await media.scrollIntoViewIfNeeded();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/48-three-stage-video.'+info.project.name+'.png'),fullPage:true});
});

test('Constrained model family graph preserves node membership and source links',async({page},info)=>{
 const original=JSON.parse(await fs.readFile(path.resolve('.cache/constrained-model-family-graph/source.json'),'utf8'));
 const preview=JSON.parse(await fs.readFile(path.resolve('.cache/constrained-model-family-graph/preview.json'),'utf8'));
 const response=await page.request.get(preview.url+'api/desktop');const model=await response.json();
 expect(model.plan.view).toEqual({component:'ForceDirectedGraph',groupBy:['parameter_size','runtime']});
 expect(model.rows).toHaveLength(14);
 for(const row of model.rows)expect(row.data).toEqual(original.records.find((r:any)=>r.id===row.id).data);
 await page.goto(preview.url);
 await expect(page.getByRole('heading',{name:'Bonsai Model Family Exploration',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Explore parameter_size: 8B',exact:true}).click();
 const expected=original.records.filter((r:any)=>r.data.parameter_size==='8B');
 await expect(page.getByTestId('record-row')).toHaveCount(expected.length);
 for(const node of model.chart.props.nodes){
   await page.getByRole('combobox',{name:'Group',exact:true}).selectOption(node.id);
   const memberIds=model.node_membership[node.id];
   await expect(page.getByTestId('record-row')).toHaveCount(memberIds.length);
   for(const row of await page.getByTestId('record-row').all()){
     const data=JSON.parse((await row.getByTestId('record-data').textContent())!);
     expect(memberIds.some((id:string)=>model.rows.find((r:any)=>r.id===id).data.id===data.id)).toBe(true);
     await expect(row.getByRole('heading',{name:data.id,exact:true})).toBeVisible();
     await expect(row.getByRole('link',{name:data.source_url,exact:true})).toHaveAttribute('href',data.source_url);
   }
 }
 await page.getByRole('button',{name:'Clear filters',exact:true}).click();
 await expect(page.getByTestId('record-row')).toHaveCount(14);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/49-model-family-graph.'+info.project.name+'.png'),fullPage:true});
});


test('Evidence note context names the selected model record',async({page},info)=>{
 const preview=JSON.parse(await fs.readFile(path.resolve('.cache/record-title-verification/preview.json'),'utf8'));
 await page.goto(preview.url);
 const rows=page.getByTestId('record-row');
 await expect(rows).toHaveCount(14);
 const first=rows.first();
 const name=await first.getByRole('heading').innerText();
 expect(name).toContain('prism-ml/');
 await first.getByRole('button',{name:/Inspect /}).click();
 await expect(page.locator('aside .selected-context')).toHaveText('Adding a note to '+name);
 await page.getByRole('textbox',{name:'Evidence note',exact:true}).fill('Draft remains attached to this model');
 const second=rows.nth(1);await second.getByRole('button',{name:/Inspect /}).click();
 await expect(page.locator('aside .selected-context')).toHaveText('Adding a note to '+await second.getByRole('heading').innerText());
 await expect(page.getByRole('textbox',{name:'Evidence note',exact:true})).toHaveValue('');
 await first.getByRole('button',{name:/Inspect /}).click();
 await expect(page.getByRole('textbox',{name:'Evidence note',exact:true})).toHaveValue('Draft remains attached to this model');
 await first.screenshot({path:path.resolve(import.meta.dirname,'../shots/50-record-title.'+info.project.name+'.png')});
});

test('Scanned PDF becomes a source-linked review record',async({page},info)=>{
 const preview=JSON.parse(await fs.readFile(path.resolve('.cache/scanned-pdf-interface/preview.json'),'utf8'));
 const source=JSON.parse(await fs.readFile(path.resolve('.cache/scanned-pdf-interface/source.json'),'utf8'));
 await page.goto(preview.url);
 const row=page.getByTestId('record-row');await expect(row).toHaveCount(1);
 await expect(row.getByRole('heading',{name:'Orchard',exact:true})).toBeVisible();
 const data=JSON.parse((await row.getByTestId('record-data').textContent())!);
 expect(data).toMatchObject({project:'Orchard',owner:'Maya',review_status:'Ready for review',open_issue_count:3});
 await row.getByText('Supporting source passages',{exact:true}).click();
 await expect(row).toContainText('Status: Ready for review');
 await expect(row).toContainText('Open issues: 3');
 const links=row.getByRole('link');await expect(links).toHaveCount(1);
 await expect(row.locator('.source-citation blockquote')).toHaveCount(5);
 for(const link of await links.all()){
   const href=await link.getAttribute('href');expect(href).toContain(source.source_id+'/file#page=1');
 }
 const response=await page.request.get((await links.first().getAttribute('href'))!);
 expect(response.ok()).toBe(true);expect((await response.body()).subarray(0,5).toString()).toBe('%PDF-');
 await row.getByRole('button',{name:/Inspect /}).click();
 await expect(page.locator('aside .selected-context')).toHaveText('Adding a note to Orchard');
 await expect(page.getByRole('textbox',{name:'Evidence note',exact:true})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/51-scanned-pdf-record.'+info.project.name+'.png'),fullPage:true});
});


test('Citation groups retain separate source locations',async({page},info)=>{
 const preview=JSON.parse(await fs.readFile(path.resolve('.cache/citation-group-verification/preview.json'),'utf8'));
 await page.route('**/api/desktop',async route=>{
   const response=await route.fetch();const model=await response.json();
   const row=model.rows[0];const passage=row.locator.source_evidence[0];
   // Browser-only location fixture. No file, review, or source record is changed.
   const id='browser-only-second-location';
   row.locator.source_evidence.push({...passage,record_id:id,locator:{...passage.locator,page:2},quote:'Browser-only page two quote'});
   model.evidence_links[id]={...model.evidence_links[passage.record_id],url:model.evidence_links[passage.record_id].url.replace('#page=1','#page=2'),label:'Browser-only page 2'};
   await route.fulfill({json:model});
 });
 await page.goto(preview.url);
 const row=page.getByTestId('record-row');await expect(row).toHaveCount(1);
 await row.getByText('Supporting source passages',{exact:true}).click();
 await expect(row.locator('.source-citation')).toHaveCount(2);
 await expect(row.locator('.source-citation').first().locator('blockquote')).toHaveCount(5);
 await expect(row.locator('.source-citation').nth(1)).toContainText('Browser-only page two quote');
 await expect(row.getByRole('link')).toHaveCount(2);
});

test('Failed saved project offers confirmed build retry',async({page},info)=>{
 const job={id:'development-saved-build-retry',source_id:'91d10b75eb64a3635f8706ab6f7f90711f71e5c30474d55d5a004fa273b41072',filename:'Review data.csv',request:'Explore the attached records',status:'failed',stage:'Build stopped',workspace_id:'development-saved-project',planning_run_id:'development-plan',proposal_sha256:'development-confirmed-hash',error:'Development build failure'};
 let retried=false;
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[job]}}));
 await page.route('**/api/workspace/source-jobs/'+job.id+'/retry-build',async route=>{
  expect(route.request().postDataJSON()).toEqual({proposal_sha256:job.proposal_sha256});
  retried=true;await route.fulfill({json:{...job,status:'queued'}});
 });
 await page.goto('/#/workspace');
 const nav=page.getByRole('navigation',{name:'Workstream sections'});
 await nav.getByRole('button',{name:'Files',exact:true}).click();
 await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(job.source_id);
 await nav.getByRole('button',{name:'Conversation',exact:true}).click();
 const button=page.getByRole('button',{name:'Retry confirmed build',exact:true});
 await expect(button).toBeVisible();await expect(button).toBeEnabled();
 await button.scrollIntoViewIfNeeded();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/52-saved-build-retry.'+info.project.name+'.png'),fullPage:true});
 await button.click();await expect.poll(()=>retried).toBe(true);
});

test('Dated series preserves separate teams and zero values',async({page},info)=>{
 const status=JSON.parse(await fs.readFile(path.resolve('.cache/dated-series-experiment/build-status.json'),'utf8'));
 const current=await (await page.request.get('/api/workspace/'+status.workspace_id)).json();
 status.preview=current.preview;
 await page.goto(status.preview.url);
 const model=await (await page.request.get(new URL('/api/desktop',status.preview.url).href)).json();
 expect(model.rows.map((r:any)=>[r.data.date,r.data.team,r.data.open_issues])).toEqual([
  ['2026-09-20','Orchard',3],['2026-09-18','Meadow',7],['2026-09-18','Orchard',0],
  ['2026-09-20','Meadow',4],['2026-09-19','Orchard',2],['2026-09-19','Meadow',6]]);
 const xs=model.chart.props.data.map((d:any)=>d.x);
 expect(xs).toEqual([...xs].sort((a,b)=>a-b));
 await expect(page.getByTestId('record-row')).toHaveCount(6);
 await expect(page.locator('.chart img')).toBeVisible();
 expect(await page.locator('.chart-viewport').evaluate(el=>el.scrollHeight<=el.clientHeight+1)).toBe(true);
 expect(await page.locator('.chart img').evaluate((img:HTMLImageElement)=>img.complete && img.naturalWidth>0)).toBe(true);
 await page.getByTestId('record-row').nth(2).getByRole('button',{name:/Inspect /}).click();
 await expect(page.getByRole('textbox',{name:'Evidence note',exact:true})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/53-dated-series.'+info.project.name+'.png'),fullPage:true});
});

test('Timeline observations select source records and retain note drafts',async({page},info)=>{
 const preview=JSON.parse(await fs.readFile(path.resolve('.cache/dated-series-experiment/interactive-preview.json'),'utf8'));
 await page.goto(preview.url);
 const points=page.getByRole('button',{name:/^Inspect observation /});
 await expect(points).toHaveCount(6);
 const zero=page.getByRole('button',{name:'Inspect observation 2026-09-18, 0, Orchard',exact:true});
 await zero.click();await expect(zero).toHaveAttribute('aria-pressed','true');
 const context=page.locator('aside .selected-context');
 await expect(context).toHaveText('Adding a note to Record 3');
 const note=page.getByRole('textbox',{name:'Evidence note',exact:true});await note.fill('Investigate the zero observation');
 const other=page.getByRole('button',{name:'Inspect observation 2026-09-20, 3, Orchard',exact:true});
 await other.focus();await page.keyboard.press('Enter');
 await expect(context).toHaveText('Adding a note to Record 1');await expect(note).toHaveValue('');
 await zero.click();await expect(note).toHaveValue('Investigate the zero observation');
 await page.getByRole('button',{name:'Zoom in',exact:true}).click();
 await expect(zero).toHaveAttribute('aria-pressed','true');
 await page.getByRole('button',{name:'Fit chart',exact:true}).click();
 await page.locator('.chart').scrollIntoViewIfNeeded();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/54-timeline-inspection.'+info.project.name+'.png'),fullPage:true});
});

test('Email thread correction preserves messages and review states',async({page},info)=>{
 const status=JSON.parse(await fs.readFile(path.resolve('.cache/email-thread-experiment/build-status.json'),'utf8'));
 const current=await (await page.request.get('/api/workspace/'+status.workspace_id)).json();
 await page.goto(current.preview.url);
 const model=await (await page.request.get(new URL('/api/desktop',current.preview.url).href)).json();
 expect(model.rows.map((r:any)=>[r.data.sent_date,r.data.project,r.data.owner,r.data.open_issue_count,r.data.review_status])).toEqual([
 ['2026-09-18','Orchard','Maya',5,'Needs revision'],['2026-09-20','Orchard','Maya',2,'Ready for review']]);
 expect(model.chart.props.data.map((r:any)=>r.group)).toEqual(['Orchard','Orchard']);
 await expect(page.getByRole('button',{name:/^Inspect observation /})).toHaveCount(2);
 const rows=page.getByTestId('record-row');await expect(rows).toHaveCount(2);
 await expect(rows.nth(0).getByRole('heading',{name:'Orchard · 2026-09-18',exact:true})).toBeVisible();
 await expect(rows.nth(1).getByRole('heading',{name:'Orchard · 2026-09-20',exact:true})).toBeVisible();
 for(let i=0;i<2;i++){
  await rows.nth(i).locator('summary').filter({hasText:'Supporting source passages'}).click();
  await expect(rows.nth(i).getByRole('heading',{name:'development-review-thread.mbox · Message '+(i+1),exact:true})).toBeVisible();
  const link=rows.nth(i).getByRole('link',{name:'Open original source',exact:true});
  await expect(link).toHaveCount(1);
  const bytes=await (await page.request.get(await link.getAttribute('href') as string)).body();
  expect(bytes.equals(await fs.readFile(path.resolve('.cache/email-thread-experiment/development-review-thread.mbox')))).toBe(true);
 }
 await page.getByRole('button',{name:/^Inspect observation /}).last().click();
 await expect(page.getByRole('textbox',{name:'Evidence note',exact:true})).toBeVisible();
 await expect(page.locator('aside .selected-context')).toHaveText('Adding a note to Orchard · 2026-09-20');
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/55-email-thread.'+info.project.name+'.png'),fullPage:true});
 // Browser-only collision fixture; no source or annotation is changed on the server.
 await page.route('**/api/desktop',async route=>{
  const response=await route.fetch();const data=await response.json();
  data.rows[1].data.sent_date=data.rows[0].data.sent_date;
  await route.fulfill({json:data});
 });
 await page.reload();
 await expect(page.getByTestId('record-row').nth(0).getByRole('heading',{name:'Orchard · 2026-09-18 · Record 1',exact:true})).toBeVisible();
 await expect(page.getByTestId('record-row').nth(1).getByRole('heading',{name:'Orchard · 2026-09-18 · Record 2',exact:true})).toBeVisible();

});

test('Alternative view choice drafts feedback before any revision request',async({page},info)=>{
 const job=JSON.parse(await fs.readFile(path.resolve('.cache/email-contract-replay/status.json'),'utf8'));
 let sent:string[]=[];
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[job]}}));
 await page.route('**/api/workspace/source-jobs/'+job.id+'/revise',async route=>{
  sent.push(route.request().postDataJSON().feedback);await route.fulfill({json:{...job,id:'development-view-revision',status:'queued'}});
 });
 await page.goto('/#/workspace');
 const nav=page.getByRole('navigation',{name:'Workstream sections'});
 await nav.getByRole('button',{name:'Files',exact:true}).click();
 await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(job.source_id);
 await nav.getByRole('button',{name:'Conversation',exact:true}).click();
 const recordReview=page.locator('.proposal .record-review');
 await expect(recordReview.locator('.structured-records')).not.toBeVisible();
 await recordReview.locator(':scope > summary').click();
 const recordRows=recordReview.locator('.structured-records > article');
 await expect(recordRows).toHaveCount(job.proposal.structure.records.length);
 for(let i=0;i<job.proposal.structure.records.length;i++){
  for(const value of Object.values(job.proposal.structure.records[i].values)){
   await expect(recordRows.nth(i)).toContainText(String(value));
  }
 }
 await recordReview.locator(':scope > summary').click();
 await expect(recordReview.locator('.structured-records')).not.toBeVisible();
 await page.locator('.view-choice summary').click();
 await page.getByRole('combobox',{name:'View to discuss',exact:true}).selectOption('LineChart');
 const feedback=page.getByRole('textbox',{name:'Clarify or change this proposal',exact:true});
 await expect(page.getByRole('button',{name:'Yes, build this view',exact:true})).toBeEnabled();
 await feedback.fill('Keep the original review status wording.');
 await expect(page.getByRole('button',{name:'Yes, build this view',exact:true})).toBeDisabled();
 await page.getByRole('button',{name:'Draft this change',exact:true}).click();
 expect(await feedback.inputValue()).toContain('Keep the original review status wording.');
 expect(await feedback.inputValue()).toContain('Follow changes over time');
 expect(sent).toHaveLength(0);
 const draft=await feedback.inputValue();
 await feedback.fill('');
 await expect(page.getByRole('button',{name:'Yes, build this view',exact:true})).toBeEnabled();
 await feedback.fill(draft);
 await expect(page.getByRole('button',{name:'Yes, build this view',exact:true})).toBeDisabled();
 await page.locator('.view-choice').scrollIntoViewIfNeeded();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/56-proposal-view-choice.'+info.project.name+'.png'),fullPage:true});
 await page.getByRole('button',{name:'Discuss this change',exact:true}).click();
 await expect.poll(()=>sent.length).toBe(1);
 expect(sent[0]).toContain('Preserve the source records, values and citations.');
});

test('Proposal feedback survives reload and stays with its proposal',async({page})=>{
 const original=JSON.parse(await fs.readFile(path.resolve('.cache/email-contract-replay/status.json'),'utf8'));
 let job=original;
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[job]}}));
 async function openProposal(){
  await page.goto('/#/workspace');
  const nav=page.getByRole('navigation',{name:'Workstream sections'});
  await nav.getByRole('button',{name:/^Files(?: · \d+)?$/}).click();
  await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(job.source_id);
  await nav.getByRole('button',{name:'Conversation',exact:true}).click();
 }
 await openProposal();
 const feedback=page.getByRole('textbox',{name:'Clarify or change this proposal',exact:true});
 await feedback.fill('Keep both messages and group by project.');
 await expect(page.getByText('Draft saved in this browser.',{exact:true}).first()).toBeVisible();
 await page.reload();await openProposal();
 await expect(feedback).toHaveValue('Keep both messages and group by project.');
 await expect(page.getByRole('button',{name:'Yes, build this view',exact:true})).toBeDisabled();
 job={...original,id:'development-distinct-proposal',proposal_sha256:'different'};
 await page.reload();await openProposal();
 await expect(feedback).toHaveValue('');
 job=original;await page.reload();await openProposal();
 await expect(feedback).toHaveValue('Keep both messages and group by project.');
 await feedback.fill('');await page.reload();await openProposal();
 await expect(feedback).toHaveValue('');
 await expect(page.getByRole('button',{name:'Yes, build this view',exact:true})).toBeEnabled();
});

test('Requested page gaps can be discussed without sending automatically',async({page},info)=>{
 const job=JSON.parse(await fs.readFile(path.resolve('.cache/email-contract-replay/status.json'),'utf8'));
 job.source_coverage={...job.source_coverage,requested_page_coverage:{requested:[3,4,99],shown:[3],omitted:[4],not_found:[99]}};
 let sent=0;
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[job]}}));
 await page.route('**/api/workspace/source-jobs/'+job.id+'/revise',async route=>{sent++;await route.fulfill({json:{...job,status:'queued'}});});
 await page.goto('/#/workspace');
 const nav=page.getByRole('navigation',{name:'Workstream sections'});
 await nav.getByRole('button',{name:/^Files(?: · \d+)?$/}).click();
 await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(job.source_id);
 await nav.getByRole('button',{name:'Conversation',exact:true}).click();
 const coverage=page.getByRole('region',{name:'Requested page coverage'});
 await expect(coverage).toContainText('Included: 3');
 await expect(coverage).toContainText('Not read because of the evidence limit: 4');
 await expect(coverage).toContainText('Not found in the supplied records: 99');
 await coverage.getByRole('button',{name:'Draft a follow-up for these pages'}).click();
 const feedback=page.getByRole('textbox',{name:'Clarify or change this proposal',exact:true});
 await expect(feedback).toHaveValue(/Please inspect page 4/);
 expect(await feedback.inputValue()).not.toContain('page 99');
 await expect(page.getByRole('button',{name:'Yes, build this view',exact:true})).toBeDisabled();
 expect(sent).toBe(0);
 await coverage.scrollIntoViewIfNeeded();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/57-requested-page-coverage.'+info.project.name+'.png'),fullPage:true});
});

test('PDF extraction refresh is explicit and preserves visible text on failure',async({page},info)=>{
 const sid='91d10b75eb64a3635f8706ab6f7f90711f71e5c30474d55d5a004fa273b41072';
 const response=await page.request.get('/api/workspace/sources/'+sid);
 const source=await response.json();
 let sent=0;
 await page.route('**/api/workspace/sources/'+sid+'/extract',async route=>{
  expect(route.request().postDataJSON()).toEqual({refresh_pdf:true});sent++;
  await route.fulfill({json:{...source,refresh_error:'Development fixture: OCR unavailable'}});
 });
 await page.goto('/#/workspace');
 await page.getByRole('navigation',{name:'Workstream sections'}).getByRole('button',{name:/^Files(?: · \d+)?$/}).click();
 await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(sid);
 const button=page.getByRole('button',{name:'Refresh PDF text and OCR',exact:true});
 await expect(button).not.toBeVisible();
 await page.getByText('Refresh PDF extraction',{exact:true}).click();
 expect(sent).toBe(0);
 await button.click();
 await expect(page.getByRole('alert')).toContainText('The previous extracted text is still available');
 expect(sent).toBe(1);
 await expect(page.locator('.source-summary')).toContainText('extracted');
 await page.getByText('Refresh PDF extraction',{exact:true}).scrollIntoViewIfNeeded();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/58-pdf-refresh.'+info.project.name+'.png'),fullPage:true});
});

test('Source inspection reaches records beyond the initial page',async({page},info)=>{
 const sid='3c3aa0c1adb26124ba361a733c7af3bca34f2f1d81ea17057d268f846b52a74e';
 const original=await (await page.request.get('/api/workspace/sources/'+sid)).json();
 const records=Array.from({length:205},(_,i)=>({id:sid+':row:'+i,locator:{line:i+1},data:{index:i}}));
 await page.route('**/api/workspace/sources/'+sid+'*',async route=>{
  const url=new URL(route.request().url());
  if(url.pathname!='/api/workspace/sources/'+sid)return route.fallback();
  const offset=Number(url.searchParams.get('offset') ?? 0);
  await route.fulfill({json:{...original,filename:'Development pagination fixture.json',kind:'table',record_count:205,matching_record_count:205,record_query:'',record_indices:{},records:records.slice(offset,offset+100),record_offset:offset,next_record_offset:offset+100<205?offset+100:null,review:{...original.review,latest:{}}}});
 });
 await page.route('**/api/workspace/sources/'+sid+'/review',route=>route.fulfill({json:{ok:true}}));
 await page.goto('/#/workspace');
 await page.getByRole('navigation',{name:'Workstream sections'}).getByRole('button',{name:/^Files(?: · \d+)?$/}).click();
 await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(sid);
 const rows=page.locator('.records > details');
 await expect(rows).toHaveCount(100);
 const nav=page.getByRole('navigation',{name:'Source record pages'});
 await expect(nav.getByRole('button',{name:'Previous records'})).toBeDisabled();
 await nav.getByRole('button',{name:'Next records'}).click();
 await expect(page.getByText(/Showing records 101–200 of 205/)).toBeVisible();
 await nav.getByRole('button',{name:'Next records'}).click();
 await expect(rows).toHaveCount(5);
 await rows.last().locator(':scope > summary').click();
 await expect(rows.last()).toContainText('204');
 await expect(nav.getByRole('button',{name:'Next records'})).toBeDisabled();
 await page.getByText('Review records and export corrections',{exact:true}).click();
 await page.getByRole('combobox',{name:'Source record',exact:true}).selectOption(sid+':row:204');
 await page.getByRole('textbox',{name:'Reviewer name',exact:true}).fill('Development test');
 await page.getByRole('combobox',{name:'Reviewer type',exact:true}).selectOption('test');
 await page.getByRole('textbox',{name:'Evidence and reason',exact:true}).fill('Mocked review, no live label saved.');
 await page.getByRole('button',{name:'Save record review',exact:true}).click();
 await expect(page.getByRole('combobox',{name:'Source record',exact:true})).toHaveValue(sid+':row:204');
 await expect(page.getByText(/Review saved. Original extraction/)).toBeVisible();
 await expect(page.getByText(/Showing records 201–205 of 205/)).toBeVisible();

 await nav.scrollIntoViewIfNeeded();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/59-source-pagination.'+info.project.name+'.png'),fullPage:true});
 await nav.getByRole('button',{name:'Previous records'}).click();
 await expect(page.getByText(/Showing records 101–200 of 205/)).toBeVisible();
});

test('PDF content search reaches a measurement beyond the first ten pages',async({page},info)=>{
 const sid='02f32dd8bdd1d72b2e5293c89d06b739e19f789ad35820614bdcaec3f6ac3777';
 const sourceBefore=await (await page.request.get('/api/workspace/sources/'+sid)).json();
 await page.goto('/#/workspace');
 await page.getByRole('navigation',{name:'Workstream sections'}).getByRole('button',{name:/^Files(?: · \d+)?$/}).click();
 await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(sid);
 await page.getByRole('textbox',{name:'Search extracted content',exact:true}).fill('520us');
 await page.getByRole('button',{name:'Search records',exact:true}).click();
 await expect(page.getByText(/Showing records .* matches/)).toBeVisible();
 const row=page.locator('.records > details').filter({has:page.locator('summary',{hasText:/^Page 25$/})});
 await expect(row).toHaveCount(1);
 await row.locator(':scope > summary').click();
 await expect(row.locator('.record-content')).toContainText('520us');
 await expect(row.locator('pre')).not.toBeVisible();
 await row.getByText('Source details and raw record',{exact:true}).click();
 await expect(row.locator('pre')).toBeVisible();
 await row.getByText('Source details and raw record',{exact:true}).click();
 await page.getByText('Review records and export corrections',{exact:true}).click();
 await expect(page.getByRole('combobox',{name:'Source record',exact:true})).toContainText('Record 25');
 await page.getByRole('textbox',{name:'Search extracted content',exact:true}).scrollIntoViewIfNeeded();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/60-source-content-search.'+info.project.name+'.png'),fullPage:true});
 await page.route('**/api/workspace/sources/'+sid+'/pages/25',route=>route.fulfill({status:503,body:'Development preview failure'}),{times:1});
 await row.getByRole('button',{name:'View original page 25',exact:true}).click();
 await expect(row.getByRole('alert')).toContainText('This page could not be rendered');
 await row.getByRole('button',{name:'Retry page preview',exact:true}).click();
 const originalPage=row.getByRole('img',{name:'Original PDF page 25',exact:true});
 await expect(originalPage).toBeVisible();
 await expect.poll(()=>originalPage.evaluate((img:HTMLImageElement)=>img.naturalWidth)).toBeGreaterThan(0);
 await expect(row.getByRole('link',{name:'Open page 25 in the original PDF',exact:true})).toHaveAttribute('href',/file#page=25$/);
 await originalPage.scrollIntoViewIfNeeded();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/61-original-pdf-page.'+info.project.name+'.png'),fullPage:true});
 await row.getByRole('button',{name:'Hide original page 25',exact:true}).click();
 await expect(originalPage).toHaveCount(0);
 await page.getByRole('button',{name:'Clear content search',exact:true}).click();
 await expect(page.locator('.records > details')).toHaveCount(Math.min(100,sourceBefore.record_count));
});

test('PDF proposal supporting sources show original page images without confirming',async({page})=>{
 const response=await page.request.get('/api/workspace/source-jobs/822dcb824ec8440489d1d6b91c7c2470');
 expect(response.ok()).toBe(true);
 const job=await response.json();
 expect(job.status).toBe('awaiting_confirmation');
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[job]}}));
 await page.goto('/#/workspace');
 const nav=page.getByRole('navigation',{name:'Workstream sections'});
 await nav.getByRole('button',{name:/^Files(?: · \d+)?$/}).click();
 await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(job.source_id);
 await nav.getByRole('button',{name:'Conversation',exact:true}).click();
 await page.getByText(/Compare supporting sources/).first().click();
 const preview=page.getByRole('button',{name:/^View original page \d+$/}).first();
 await preview.click();
 const img=page.getByRole('img',{name:/^Original PDF page \d+$/}).first();
 await expect(img).toBeVisible();
 await expect.poll(()=>img.evaluate((node:HTMLImageElement)=>node.naturalWidth)).toBeGreaterThan(0);
 const unchanged=await (await page.request.get('/api/workspace/source-jobs/'+job.id)).json();
 expect(unchanged.status).toBe('awaiting_confirmation');
 expect(unchanged.proposal_sha256).toBe(job.proposal_sha256);
});

test('PDF visual reading requests the selected page explicitly',async({page})=>{
 const sid='02f32dd8bdd1d72b2e5293c89d06b739e19f789ad35820614bdcaec3f6ac3777';
 const sent:unknown[]=[];
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[]}}));
 await page.route('**/api/workspace/sources/'+sid+'/vision',route=>{
  sent.push(route.request().postDataJSON());return route.fulfill({json:{status:'queued'}});
 });
 await page.goto('/#/workspace');
 await page.getByRole('navigation',{name:'Workstream sections'}).getByRole('button',{name:/^Files(?: · \d+)?$/}).click();
 await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(sid);
 const row=page.locator('.records > details').filter({has:page.locator('summary',{hasText:/^Page 25$/})});
 await row.locator(':scope > summary').click();
 expect(sent).toHaveLength(0);
 await row.getByRole('button',{name:'Read page 25 with Bonsai',exact:true}).click();
 await expect.poll(()=>sent.length).toBe(1);
 expect(sent[0]).toEqual({page:25});
});

test('PDF visual observations remain separate and marked unreviewed',async({page},info)=>{
 const sid='02f32dd8bdd1d72b2e5293c89d06b739e19f789ad35820614bdcaec3f6ac3777';
 await page.goto('/#/workspace');
 await page.getByRole('navigation',{name:'Workstream sections'}).getByRole('button',{name:/^Files(?: · \d+)?$/}).click();
 await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(sid);
 await page.getByRole('textbox',{name:'Search extracted content',exact:true}).fill('389.1');
 await page.getByRole('button',{name:'Search records',exact:true}).click();
 const row=page.locator('.records > details').filter({has:page.locator('summary',{hasText:/^Page 25 · Bonsai observation$/})});
 await expect(row).toHaveCount(1);
 await row.locator(':scope > summary').click();
 await expect(row).toContainText('Bonsai visual observation · unreviewed');
 await expect(row.locator('.record-content')).toContainText('402.1ms, 389.1ms');
 await row.getByRole('button',{name:'View original page 25',exact:true}).click();
 const image=row.getByRole('img',{name:'Original PDF page 25',exact:true});
 await expect.poll(()=>image.evaluate((img:HTMLImageElement)=>img.naturalWidth)).toBeGreaterThan(0);
 await image.scrollIntoViewIfNeeded();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/62-pdf-visual-observation.'+info.project.name+'.png'),fullPage:true});
});

test('Old vision completion does not keep resetting a refreshed source search',async({page})=>{
 const sid='02f32dd8bdd1d72b2e5293c89d06b739e19f789ad35820614bdcaec3f6ac3777';
 let polls=0;
 let sourceRequests=0;
 await page.route('**/api/workspace/sources/'+sid+'*',route=>{sourceRequests++;return route.fallback();});
 await page.route('**/api/workspace/source-jobs',route=>{
  polls++;
  return route.fulfill({json:{jobs:[{id:'development-old-vision',source_id:sid,filename:'S82065.pdf',kind:'vision_extraction',status:'completed',stage:'Done',run_id:'older-than-current-ocr'}]}});
 });
 await page.goto('/#/workspace');
 await page.getByRole('navigation',{name:'Workstream sections'}).getByRole('button',{name:/^Files(?: · \d+)?$/}).click();
 await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(sid);
 const search=page.getByRole('textbox',{name:'Search extracted content',exact:true});
 await search.fill('520us');await page.getByRole('button',{name:'Search records',exact:true}).click();
 const initialPolls=polls;
 await expect.poll(()=>polls,{timeout:7000}).toBeGreaterThan(initialPolls+1);
 await expect(search).toHaveValue('520us');
 await expect(page.getByText(/Showing records .* matches/)).toBeVisible();
 const settledRequests=sourceRequests;const settledPolls=polls;
 await expect.poll(()=>polls,{timeout:7000}).toBeGreaterThan(settledPolls+1);
 expect(sourceRequests).toBe(settledRequests);
});

test('Wide timing comparison keeps units and values accessible without page overflow',async({page},info)=>{
 const compiled=JSON.parse(await fs.readFile(path.resolve('.cache/pdf-visual-structure/wide-table-compiled.json'),'utf8'));
 const project=await (await page.request.get('/api/workspace/cecb54fb6b604fdd85c8230f7dabaa53')).json();
 expect(project.preview?.url).toBeTruthy();
 await page.route('**/api/desktop',route=>route.fulfill({json:{...compiled,evidence_links:{}}}));
 await page.route('**/api/annotations',route=>route.fulfill({json:[]}));
 await page.goto(project.preview.url);
 const table=page.getByRole('region',{name:'Source record table',exact:true});
 await expect(table.getByRole('columnheader')).toHaveCount(9);
 await expect(table.getByRole('cell',{name:'402.1',exact:true})).toBeVisible();
 await expect(table.getByRole('cell',{name:'389.1',exact:true})).toBeVisible();
 await expect(table.getByRole('cell',{name:'520',exact:true})).toBeVisible();
 await expect(table.getByRole('cell',{name:'us',exact:true})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await table.focus();
 const overflow=await table.evaluate(node=>node.scrollWidth>node.clientWidth);
 if(overflow){await page.keyboard.press('ArrowRight');await expect.poll(()=>table.evaluate(node=>node.scrollLeft)).toBeGreaterThan(0);}
 await table.getByRole('button',{name:/Review table record/}).first().click();
 await expect(page.getByRole('textbox',{name:'Evidence note',exact:true})).toBeEnabled();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/63-wide-timing-table.'+info.project.name+'.png'),fullPage:true});
});

test('Saved response recovery returns measurements for review without confirming',async({page},info)=>{
 const recovered=JSON.parse(await fs.readFile(path.resolve('.cache/pdf-revalidation/job.json'),'utf8'));
 const parent=await (await page.request.get('/api/workspace/source-jobs/'+recovered.parent_job_id)).json();
 let shown=parent;let calls=0;let confirmations=0;
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[shown]}}));
 await page.route('**/api/workspace/source-jobs/'+parent.id+'/revalidate',route=>{
  calls++;shown=recovered;return route.fulfill({json:recovered});
 });
 await page.route('**/api/workspace/source-jobs/*/confirm',route=>{confirmations++;return route.fulfill({status:400,json:{error:'No confirmation in development check'}});});
 await page.goto('/#/workspace');
 const nav=page.getByRole('navigation',{name:'Workstream sections'});
 await nav.getByRole('button',{name:/^Files(?: · \d+)?$/}).click();
 await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(parent.source_id);
 await nav.getByRole('button',{name:'Conversation',exact:true}).click();
 await page.getByRole('button',{name:'Check saved response again',exact:true}).click();
 await expect(page.getByText(/Saved response is ready for your review/)).toBeVisible();
 expect(calls).toBe(1);expect(confirmations).toBe(0);
 await page.getByText('Review 4 proposed records',{exact:true}).click();
 const values=page.locator('.structured-records');
 await expect(values.getByText('402.1',{exact:true})).toBeVisible();
 await expect(values.getByText('389.1',{exact:true})).toBeVisible();
 await expect(values.getByText('520',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'Yes, build this view',exact:true})).toBeEnabled();
 await values.scrollIntoViewIfNeeded();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/64-recovered-proposal.'+info.project.name+'.png'),fullPage:true});
});

test('Discuss this PDF page persists explicit scope until the user clears it',async({page},info)=>{
 const sid='02f32dd8bdd1d72b2e5293c89d06b739e19f789ad35820614bdcaec3f6ac3777';
 const sent:any[]=[];
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[]}}));
 await page.route('**/api/workspace/sources/'+sid+'/generate',route=>{sent.push(route.request().postDataJSON());return route.fulfill({json:{status:'queued'}});});
 await page.goto('/#/workspace');
 await page.getByRole('navigation',{name:'Workstream sections'}).getByRole('button',{name:/^Files(?: · \d+)?$/}).click();
 await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(sid);
 const row=page.locator('.records > details').filter({has:page.locator('summary',{hasText:/^Page 25$/})});
 await row.locator(':scope > summary').click();
 await row.getByRole('button',{name:'Discuss this page',exact:true}).click();
 const scope=page.getByLabel('Selected source scope',{exact:true});
 await expect(scope).toContainText('Only page 25 of S82065.pdf');
 await expect(page.getByRole('textbox',{name:'Message Research analyst',exact:true})).toBeFocused();
 expect(sent).toHaveLength(0);
 await page.reload();
 await expect(scope).toContainText('Only page 25');
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/65-page-scoped-draft.'+info.project.name+'.png'),fullPage:true});
 await page.getByRole('button',{name:'Send ↑',exact:true}).click();
 await expect.poll(()=>sent.length).toBe(1);
 expect(sent[0].source_scope).toEqual({pages:[25]});
 await page.getByRole('button',{name:'Use all attached files',exact:true}).click();
 await expect(scope).toHaveCount(0);
 await page.getByRole('button',{name:'Send ↑',exact:true}).click();
 await expect.poll(()=>sent.length).toBe(2);
 expect(sent[1].source_scope).toBeNull();
});

test('Proposal coverage distinguishes records outside explicit page scope',async({page},info)=>{
 const job=JSON.parse(await fs.readFile(path.resolve('.cache/pdf-revalidation/job.json'),'utf8'));
 const packet=JSON.parse(await fs.readFile(path.resolve('.cache/workspace-live-v3-20260921/workspace/source-jobs/e447aaf47075462cb9ba5e09760cf50c/source-packet.json'),'utf8'));
 job.source_coverage={...job.source_coverage,source_scope:packet.source_scope,records_shown:4,records_total:82,coverage:packet.coverage};
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[job]}}));
 await page.goto('/#/workspace');
 const nav=page.getByRole('navigation',{name:'Workstream sections'});
 await nav.getByRole('button',{name:/^Files(?: · \d+)?$/}).click();
 await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(job.source_id);
 await nav.getByRole('button',{name:'Conversation',exact:true}).click();
 const scope=page.getByLabel('Proposal source scope',{exact:true});
 await expect(scope).toContainText('Scoped to PDF pages 25');
 await expect(scope).toContainText('4 records in scope; 78 records outside this scope were not supplied');
 await scope.scrollIntoViewIfNeeded();
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/66-proposal-page-scope.'+info.project.name+'.png'),fullPage:true});
});

test('Structured coverage exposes a source mentioned only in findings',async({page,request},info)=>{
 const response=await request.get('/api/workspace/source-jobs/285132378cda464384902eebb8d9ac16');
 expect(response.ok()).toBe(true);const job=await response.json();
 expect(job.source_coverage.structured_usage.cited_records).toBe(1);
 expect(job.source_coverage.structured_usage.supplied_records).toBe(2);
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[job]}}));
 let revisions=0;await page.route('**/api/workspace/source-jobs/*/revise',route=>{revisions++;return route.fulfill({json:{}});});
 await page.goto('/#/workspace');
 const nav=page.getByRole('navigation',{name:'Workstream sections'});
 await nav.getByRole('button',{name:/^Files(?: · \d+)?$/}).click();
 await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(job.source_id);
 await nav.getByRole('button',{name:'Conversation',exact:true}).click();
 const coverage=page.getByRole('region',{name:'Structured data source coverage'});
 await expect(coverage).toContainText('1 of 2 supplied source records');
 await expect(coverage).toContainText('Source records without data citations: 1');
 await coverage.getByRole('button',{name:'Ask Bonsai to check unused sources'}).click();
 await expect(page.getByText('Draft saved in this browser.',{exact:true}).first()).toBeVisible();
 expect(await page.locator('textarea').evaluateAll(elements=>elements.some(element=>(element as HTMLTextAreaElement).value.includes('Recheck whether the unused sources contain observations needed for my request')))).toBe(true);
 expect(revisions).toBe(0);
 await coverage.scrollIntoViewIfNeeded();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/67-structured-source-coverage.'+info.project.name+'.png'),fullPage:true});
});

test('Record retention is explicit, draft-persistent, and sent with the request',async({page},info)=>{
 const sid='60040aca3ec11924026f5a2d6cd10b7e61a11a05cdbc33d43d5bf982a753fb8c';const sent:any[]=[];
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[]}}));
 await page.route('**/api/workspace/sources/'+sid+'/generate',route=>{sent.push(route.request().postDataJSON());return route.fulfill({json:{id:'test'}});});
 await page.goto('/#/workspace');const nav=page.getByRole('navigation',{name:'Workstream sections'});
 await nav.getByRole('button',{name:/^Files(?: · \d+)?$/}).click();await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(sid);
 await nav.getByRole('button',{name:'Conversation',exact:true}).click();await page.getByText('Data requirements',{exact:true}).click();
 const checkbox=page.getByRole('checkbox',{name:'Keep one output row per source record'});await expect(checkbox).not.toBeChecked();await checkbox.check();
 await page.getByLabel('Message Research analyst',{exact:true}).fill('Keep each message as a separate observation over time.');
 await page.reload();await page.getByText('Data requirements · Preserve every record',{exact:true}).click();await expect(checkbox).toBeChecked();expect(sent).toHaveLength(0);
 await page.getByRole('button',{name:'Send ↑',exact:true}).click();await expect.poll(()=>sent.length).toBe(1);expect(sent[0].task_contract).toEqual({record_policy:'one_per_source_record'});
 await checkbox.uncheck();await page.getByRole('button',{name:'Send ↑',exact:true}).click();await expect.poll(()=>sent.length).toBe(2);expect(sent[1].task_contract).toBeNull();
 await checkbox.check();await checkbox.scrollIntoViewIfNeeded();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/68-record-retention-draft.'+info.project.name+'.png'),fullPage:true});
});

test('Saved proposal displays its frozen record retention requirement',async({page,request},info)=>{
 const response=await request.get('/api/workspace/source-jobs/589fedcd1527418a8865cfd6babe3906');expect(response.ok()).toBe(true);const job=await response.json();
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[job]}}));await page.goto('/#/workspace');
 const nav=page.getByRole('navigation',{name:'Workstream sections'});await nav.getByRole('button',{name:/^Files(?: · \d+)?$/}).click();
 await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(job.source_id);await nav.getByRole('button',{name:'Conversation',exact:true}).click();
 const requirement=page.getByLabel('Record retention requirement',{exact:true});await expect(requirement).toContainText('one output row for each of the 2 source records');await expect(requirement).toContainText('Revisions retain this requirement');
 await requirement.scrollIntoViewIfNeeded();await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/69-record-retention-proposal.'+info.project.name+'.png'),fullPage:true});
});

test('Chart preview is lazy, retryable, and does not confirm a build',async({page,request},info)=>{
 const jid='7faa024b1bc043b0b01ebe3dd78a417d';const response=await request.get('/api/workspace/source-jobs/'+jid);expect(response.ok()).toBe(true);const job=await response.json();
 let images=0,confirmations=0;
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[{...job,status:'awaiting_confirmation',workspace_id:undefined}]}}));
 await page.route('**/api/workspace/source-jobs/'+jid+'/proposal-preview?*',route=>{images++;return images===1 ? route.fulfill({status:503,body:'Temporary render failure'}) : route.continue();});
 await page.route('**/api/workspace/source-jobs/*/confirm',route=>{confirmations++;return route.fulfill({json:{}});});
 await page.goto('/#/workspace');const nav=page.getByRole('navigation',{name:'Workstream sections'});
 await nav.getByRole('button',{name:/^Files(?: · \d+)?$/}).click();await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(job.source_id);
 await nav.getByRole('button',{name:'Conversation',exact:true}).click();
 const preview=page.getByRole('region',{name:'Proposed chart preview'});
 await expect(preview.getByRole('img')).toHaveCount(0);expect(images).toBe(0);
 await preview.getByRole('button',{name:'Preview proposed chart',exact:true}).click();await expect(preview.getByRole('alert')).toContainText('could not load');
 await preview.getByRole('button',{name:'Retry chart preview',exact:true}).click();const img=preview.getByRole('img');
 await expect.poll(()=>img.evaluate(element=>(element as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
 expect(images).toBe(2);expect(confirmations).toBe(0);
 const unchanged=await (await request.get('/api/workspace/source-jobs/'+jid)).json();expect(unchanged.status).toBe(job.status);expect(unchanged.workspace_id).toBe(job.workspace_id);
 await preview.scrollIntoViewIfNeeded();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/70-proposed-chart-preview.'+info.project.name+'.png'),fullPage:true});
});

test('Generated view separates automated notes from discussion',async({page,request},info)=>{
 const project=await (await request.get('/api/workspace/171bc98e7caf4aa48ef1a600cea1f028')).json();
 const model=await (await request.get(project.preview.url+'api/desktop')).json();
 const common={record_snapshot:model.rows[0],record_id:model.rows[0].id};
 await page.route('**/api/annotations',route=>route.fulfill({json:[
  {...common,id:'fixture-discussion',note:'Development discussion note fixture',review_origin:'fixture-reviewer'},
  {...common,id:'fixture-automated',note:'Development automated verification fixture',review_origin:'workspace-automated-check'}
 ]}));
 await page.goto(project.preview.url);
 await expect(page.getByText('Development discussion note fixture',{exact:true})).toBeVisible();
 const automated=page.getByText('Development automated verification fixture',{exact:true});
 await expect(automated).toBeHidden();
 const disclosure=page.locator('summary').filter({hasText:'Automated verification notes (1)'});
 await disclosure.click();await expect(automated).toBeVisible();
 await disclosure.click();await expect(automated).toBeHidden();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/71-discussion-and-verification-notes.'+info.project.name+'.png'),fullPage:true});
});

test('Saved-view editor sends explicit model profile without changing defaults',async({page,request},info)=>{
 const id='171bc98e7caf4aa48ef1a600cea1f028';const project=await (await request.get('/api/workspace/'+id)).json();
 const submitted:any[]=[];
 await page.route('**/api/workspace/'+id+'/attempts',route=>{submitted.push(route.request().postDataJSON());return route.fulfill({status:409,json:{error:'Development interception: no inference'}});});
 await page.goto('/#/workspace');
 if(info.project.name==='mobile')await page.locator('.mobile-stream-toggle').click();
 const sidebar=page.getByRole('complementary',{name:'Workstreams'});
 await sidebar.getByRole('textbox',{name:'Search workstreams'}).fill(project.title);
 await sidebar.getByRole('button').filter({hasText:project.title}).click();
 const settings=page.locator('details.model-settings');
 await settings.locator('summary').click();
 const profile=page.getByRole('combobox',{name:'Generation profile',exact:true});
 await expect(profile).toHaveValue('');
 await page.getByRole('textbox',{name:'Describe the next change',exact:true}).fill('Development check: preserve my selected model configuration.');
 await profile.selectOption('bonsai2-bounded');
 await page.getByRole('button',{name:'Send request',exact:true}).click();
 await expect.poll(()=>submitted.length).toBe(1);
 expect(submitted[0].generation_config).toEqual({profile:'bonsai2-bounded',seed:42});
 await expect(profile).toHaveValue('bonsai2-bounded');
 if(info.project.name==='mobile')await page.locator('.mobile-stream-toggle').click();
 await sidebar.getByRole('button',{name:'Research analyst',exact:true}).click();
 if(info.project.name==='mobile')await page.locator('.mobile-stream-toggle').click();
 await sidebar.getByRole('button').filter({hasText:project.title}).click();
 await settings.locator('summary').click();
 await expect(profile).toHaveValue('bonsai2-bounded');
 await settings.scrollIntoViewIfNeeded();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/72-editor-model-settings.'+info.project.name+'.png'),fullPage:true});
 await profile.selectOption('');await page.getByRole('button',{name:'Send request',exact:true}).click();
 await expect.poll(()=>submitted.length).toBe(2);expect(submitted[1].generation_config).toBeUndefined();
});

test('Source proposal profile persists with draft and resets on clear',async({page},info)=>{
 const sid='a54743cb88a798bb97e49576bc52fad025b3433b52c23577a889f029de6753d4';const sent:any[]=[];
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[]}}));
 await page.route('**/api/workspace/sources/'+sid+'/generate',route=>{sent.push(route.request().postDataJSON());return route.fulfill({json:{id:'development-intercept'}});});
 await page.goto('/#/workspace');const nav=page.getByRole('navigation',{name:'Workstream sections'});
 await nav.getByRole('button',{name:/^Files(?: · \d+)?$/}).click();await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(sid);
 await nav.getByRole('button',{name:'Conversation',exact:true}).click();
 const settings=page.locator('details.model-settings');await settings.locator('summary').click();
 const profile=page.getByRole('combobox',{name:'Proposal generation profile',exact:true});await expect(profile).toHaveValue('');
 await profile.selectOption('bonsai2-bounded');await page.getByLabel('Message Research analyst',{exact:true}).fill('Development check: structure these meeting observations.');
 await page.reload();await settings.locator('summary').click();await expect(profile).toHaveValue('bonsai2-bounded');expect(sent).toHaveLength(0);
 await page.getByRole('button',{name:'Send ↑',exact:true}).click();await expect.poll(()=>sent.length).toBe(1);expect(sent[0].generation_config).toEqual({profile:'bonsai2-bounded',seed:42});
 await settings.scrollIntoViewIfNeeded();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/73-source-model-settings.'+info.project.name+'.png'),fullPage:true});
 await profile.selectOption('');await page.getByRole('button',{name:'Send ↑',exact:true}).click();await expect.poll(()=>sent.length).toBe(2);expect(sent[1].generation_config).toBeUndefined();
 await profile.selectOption('bonsai2-instruct');await page.getByRole('button',{name:'Clear draft',exact:true}).click();
 await nav.getByRole('button',{name:/^Files(?: · \d+)?$/}).click();await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(sid);await nav.getByRole('button',{name:'Conversation',exact:true}).click();
 await settings.locator('summary').click();await expect(profile).toHaveValue('');
});

test('Recorded proposal configuration stays independent of composer selection',async({page,request},info)=>{
 const job=await (await request.get('/api/workspace/source-jobs/2c829db9c92e4894a9a2307f85dc19d3')).json();
 expect(job.generation_config).toEqual({profile:'bonsai2-bounded',seed:42});
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[job]}}));
 await page.goto('/#/workspace');const nav=page.getByRole('navigation',{name:'Workstream sections'});
 await nav.getByRole('button',{name:/^Files(?: · \d+)?$/}).click();await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(job.source_id);await nav.getByRole('button',{name:'Conversation',exact:true}).click();
 const recorded=page.locator('details[aria-label="Recorded model configuration"]');await recorded.locator('summary').click();
 await expect(recorded).toContainText('Reasoning · 512-token allowance · Seed 42');
 await page.locator('details.model-settings summary').click();await page.getByRole('combobox',{name:'Proposal generation profile',exact:true}).selectOption('bonsai2-instruct');
 await expect(recorded).toContainText('Reasoning · 512-token allowance · Seed 42');
 await recorded.scrollIntoViewIfNeeded();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/74-recorded-model-configuration.'+info.project.name+'.png'),fullPage:true});
 job.generation_config=null;await page.reload();await recorded.locator('summary').click();await expect(recorded).toContainText('Configuration was not recorded for this result');
});

test('Embedded saved view preserves exploration across workspace tabs',async({page,request},info)=>{
 const id='171bc98e7caf4aa48ef1a600cea1f028';const project=await (await request.get('/api/workspace/'+id)).json();
 await page.goto('/#/workspace');
 if(info.project.name==='mobile')await page.locator('.mobile-stream-toggle').click();
 const sidebar=page.getByRole('complementary',{name:'Workstreams'});await sidebar.getByRole('textbox',{name:'Search workstreams'}).fill(project.title);await sidebar.getByRole('button').filter({hasText:project.title}).click();
 const iframe=page.locator('iframe[title="Generated project preview"]');await iframe.scrollIntoViewIfNeeded();
 const frame=page.frameLocator('iframe[title="Generated project preview"]');await expect(frame.getByRole('heading',{name:project.title,exact:true})).toBeVisible({timeout:10000});
 await expect(frame.getByTestId('record-row')).toHaveCount(4);
 await frame.getByRole('searchbox',{name:'Search records',exact:true}).fill('Awaiting update');await expect(frame.getByTestId('record-row')).toHaveCount(1);await expect(frame.getByText('Not provided',{exact:true})).toBeVisible();
 await frame.locator('summary').filter({hasText:'Supporting source passages'}).click();await expect(frame.getByRole('link',{name:'Open original source',exact:true})).toBeVisible();
 await frame.getByRole('button',{name:'Clear filters',exact:true}).click();await expect(frame.getByTestId('record-row')).toHaveCount(4);
 const tabs=page.getByRole('navigation',{name:'Workspace views'});await tabs.getByRole('button',{name:'Source',exact:true}).click();await expect(page.locator('pre.source')).toContainText('verificationNotes');
 await tabs.getByRole('button',{name:'Evidence',exact:true}).click();await page.getByText('Review source interpretation',{exact:true}).click();await expect(page.getByText('Review source interpretation',{exact:true})).toBeVisible();
 await tabs.getByRole('button',{name:'Preview',exact:true}).click();await iframe.scrollIntoViewIfNeeded();await expect(frame.getByTestId('record-row')).toHaveCount(4);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/75-embedded-workstream-exploration.'+info.project.name+'.png'),fullPage:true});
});

test('Presentation intake reports slide coverage and keeps citations',async({page},info)=>{
 await page.goto('/#/workspace');
 const uploaded=page.waitForResponse(r=>r.url().endsWith('/api/workspace/sources') && r.request().method()==='POST');
 await page.locator('input[type="file"]').setInputFiles(path.resolve('research/harness-alignment/fixtures/desktop-regressions/development-slide-coverage.pptx'));
 expect((await uploaded).ok()).toBe(true);
 const nav=page.getByRole('navigation',{name:'Workstream sections'});
 await nav.getByRole('button',{name:/^Files(?: · \d+)?$/}).click();
 const source=page.locator('.source-summary');await expect(source).toContainText('2 records · presentation · extracted');
 await source.getByText('Slide coverage',{exact:true}).click();
 await expect(source).toContainText('Slide 1 · 2 extracted records');
 await expect(source).toContainText('Slide 2 (hidden) · No readable text; visual review needed');
 await expect(source).toContainText('1 embedded media files not read');
 await expect(page.locator('.records summary').first()).toContainText('Slide 1');
 await page.locator('.records summary').first().click();await expect(page.locator('.record-content').first()).toContainText('A & B');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/76-presentation-coverage.'+info.project.name+'.png'),fullPage:true});
});

test('Presentation generated view retains unplotted observation and original deck',async({page,request},info)=>{
 const project=await (await request.get('/api/workspace/e07a9297a91d40689a0779550797a3fc')).json();
 await page.goto(project.preview.url);
 await expect(page.getByTestId('record-row')).toHaveCount(4);
 await expect(page.getByRole('button',{name:/^Inspect observation /})).toHaveCount(3);
 await page.getByRole('searchbox',{name:'Search records',exact:true}).fill('Awaiting update');
 const row=page.getByTestId('record-row');await expect(row).toHaveCount(1);await expect(row).toContainText('Willow');await expect(row).toContainText('Not provided');
 await row.getByText('Supporting source passages',{exact:true}).click();await expect(row).toContainText('Theo did not report an issue count');
 const link=row.getByRole('link',{name:'Open original source',exact:true});const response=await request.get(await link.getAttribute('href'));
 expect(response.ok()).toBe(true);
 const expected=await fs.readFile(path.resolve('research/harness-alignment/fixtures/desktop-regressions/development-team-review.pptx'));
 expect(await response.body()).toEqual(expected);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/77-presentation-generated-view.'+info.project.name+'.png'),fullPage:true});
});

test('Proposal revision comparison preserves evidence and supports retry',async({page,request},info)=>{
 const jid='2dbbd4b2699342a39f7c1d02c56ef2e7';const job=await (await request.get('/api/workspace/source-jobs/'+jid)).json();
 const mutations:string[]=[];page.on('request',r=>{if(r.url().includes('/api/workspace/') && ['POST','PUT','DELETE'].includes(r.method()))mutations.push(r.url());});
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[job]}}));
 let requests=0;let fail=false;
 await page.route('**/api/workspace/source-jobs/'+jid+'/comparison',route=>{requests++;return fail ? route.fulfill({status:503,json:{error:'Development comparison outage'}}) : route.continue();});
 await page.goto('/#/workspace');const nav=page.getByRole('navigation',{name:'Workstream sections'});
 await nav.getByRole('button',{name:/^Files(?: · \d+)?$/}).click();await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(job.source_id);await nav.getByRole('button',{name:'Conversation',exact:true}).click();
 expect(requests).toBe(0);
 const comparison=page.locator('details.proposal-comparison');await comparison.locator(':scope > summary').click();
 await expect(comparison).toContainText('4 structured records keep the same values and citations. 0 appear only in the previous version; 0 appear only in this version.');
 await expect(comparison).toContainText('The visualization choice changed.');
 const previous=comparison.getByRole('region',{name:'Previous proposal version'});const current=comparison.getByRole('region',{name:'Current proposal version'});
 await expect(previous).toContainText('Table ·');await expect(current).toContainText('Scatterplot ·');
 await previous.getByText('Interpretation and uncertainties',{exact:true}).click();await current.getByText('Interpretation and uncertainties',{exact:true}).click();
 await expect(previous).toContainText('six provided observations');await expect(current).toContainText('four dated observations, not six');
 await previous.getByText('Interpretation and uncertainties',{exact:true}).click();await current.getByText('Interpretation and uncertainties',{exact:true}).click();
 await comparison.locator(':scope > summary').evaluate(el=>el.scrollIntoView({block:'start'}));expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/78-proposal-revision-comparison.'+info.project.name+'.png'),fullPage:true});
 fail=true;await page.reload();await page.locator('details.proposal-comparison > summary').click();await expect(page.getByRole('alert')).toContainText('Development comparison outage');
 fail=false;await page.getByRole('button',{name:'Retry comparison',exact:true}).click();await expect(comparison).toContainText('4 structured records keep the same values and citations');expect(mutations).toEqual([]);
});

test('Select chart from saved data without inference or confirmation',async({page,request},info)=>{
 let jid=info.project.name==='desktop' ? '333b4b24769e4b61be226d770eeba6d7' : 'c4eac071533c46138cff2ef2050fcbad';
 let job=await (await request.get('/api/workspace/source-jobs/'+jid)).json();
 while(job.superseded_by){jid=job.superseded_by;job=await (await request.get('/api/workspace/source-jobs/'+jid)).json();}
 expect(job.status).toBe('awaiting_confirmation');const original=job;const before=await (await request.get('/api/workspace')).json();
 const date=info.project.name==='desktop' ? 'review_date' : 'date';const color=job.proposal.plan.view.component==='Scatterplot' && job.proposal.plan.view.color==='project' ? '' : 'project';
 await page.setExtraHTTPHeaders({'X-Eval-Actor':'workspace-automated-view-check'});
 const posts:string[]=[];page.on('request',r=>{if(r.method()==='POST' && r.url().includes('/api/workspace/'))posts.push(r.url());});
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[job]}}));
 await page.route('**/api/workspace/source-jobs/'+jid+'/view-revision',async route=>{const response=await route.fetch();expect(response.ok()).toBe(true);job=await response.json();await route.fulfill({response});});
 await page.goto('/#/workspace');const nav=page.getByRole('navigation',{name:'Workstream sections'});
 await nav.getByRole('button',{name:/^Files(?: · \d+)?$/}).click();await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(job.source_id);await nav.getByRole('button',{name:'Conversation',exact:true}).click();
 const choice=page.locator('details.saved-view-choice');await choice.locator(':scope > summary').click();
 const apply=choice.getByRole('button',{name:'Review selected view',exact:true});await expect(apply).toBeDisabled();
 await choice.getByRole('combobox',{name:'Visualization',exact:true}).selectOption('Scatterplot');await choice.getByRole('combobox',{name:'Horizontal axis',exact:true}).selectOption(date);await expect(apply).toBeDisabled();
 await choice.getByRole('combobox',{name:'Vertical axis',exact:true}).selectOption('open_issue_count');await choice.getByRole('combobox',{name:'Color groups',exact:true}).selectOption(color);
 await apply.click();await expect.poll(()=>job.id!==original.id).toBe(true);
 expect(job.model_calls).toBe(0);expect(job.status).toBe('awaiting_confirmation');expect(job.kind).toBe('view_revision');expect(job.proposal.structure).toEqual(original.proposal.structure);expect(job.proposal.interpretation).toEqual(original.proposal.interpretation);
 await expect(page.getByText('View selected from saved data, with no model inference.',{exact:false})).toBeVisible();
 await page.getByRole('button',{name:'Preview proposed chart',exact:true}).click();const img=page.getByRole('img',{name:'Proposed chart: '+job.proposal.plan.title,exact:true});await expect(img).toBeVisible();await expect.poll(()=>img.evaluate((el:HTMLImageElement)=>el.complete&&el.naturalWidth>0)).toBe(true);
 const comparison=await (await request.get('/api/workspace/source-jobs/'+job.id+'/comparison')).json();expect(comparison.records.unchanged).toBe(4);
 const after=await (await request.get('/api/workspace')).json();expect(after.workspaces.length).toBe(before.workspaces.length);expect(after.running_source_jobs).toEqual([]);expect(posts).toHaveLength(1);expect(posts[0]).toContain('/view-revision');
 await img.scrollIntoViewIfNeeded();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/79-saved-data-view-selection.'+info.project.name+'.png'),fullPage:true});
 await fs.writeFile(path.resolve('.cache/view-choice-'+info.project.name+'.json'),JSON.stringify({parent_job_id:original.id,job_id:job.id,run_id:job.run_id,model_calls:job.model_calls,records_unchanged:true,preview_loaded:true,no_build_confirmed:true},null,2));
});

test('Selected view preview is identified as an explicit choice',async({page,request},info)=>{
 const job=await (await request.get('/api/workspace/source-jobs/d2bf4ae056d74a519cf57a9249a143b8')).json();
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[job]}}));
 await page.goto('/#/workspace');const nav=page.getByRole('navigation',{name:'Workstream sections'});await nav.getByRole('button',{name:/^Files(?: · \d+)?$/}).click();await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(job.source_id);await nav.getByRole('button',{name:'Conversation',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Selected view: '+job.proposal.plan.title,exact:true})).toBeVisible();await expect(page.getByText(job.proposal.plan.summary,{exact:true})).toBeVisible();
 await expect(page.getByRole('heading',{name:'Uncertainties from the earlier interpretation',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Preview proposed chart',exact:true}).click();const img=page.getByRole('img',{name:'Proposed chart: '+job.proposal.plan.title,exact:true});await expect.poll(()=>img.evaluate((el:HTMLImageElement)=>el.complete&&el.naturalWidth>0)).toBe(true);
 await img.scrollIntoViewIfNeeded();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/79-saved-data-view-selection.'+info.project.name+'.png'),fullPage:true});
});

test('Unused source evidence can be inspected before requesting a correction',async({page,request},info)=>{
 const job=await (await request.get('/api/workspace/source-jobs/9e7e5ff6004043479e2581a61a71e2e9')).json();
 expect(job.source_coverage.structured_usage.uncited_record_ids).toHaveLength(1);
 const mutations:string[]=[];page.on('request',r=>{if(r.url().includes('/api/workspace/')&&['POST','PUT','DELETE'].includes(r.method()))mutations.push(r.url());});
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[job]}}));
 await page.goto('/#/workspace');const nav=page.getByRole('navigation',{name:'Workstream sections'});
 await nav.getByRole('button',{name:/^Files(?: · \d+)?$/}).click();await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(job.source_id);await nav.getByRole('button',{name:'Conversation',exact:true}).click();
 const unused=page.locator('details.unused-sources');await unused.locator(':scope > summary').click();
 await expect(unused.locator('article')).toHaveCount(1);await expect(unused).toContainText('Orchard');
 await expect(unused.locator('article dl')).not.toBeEmpty();const original=unused.getByRole('link');await expect(original).toHaveCount(1);expect((await request.get(await original.getAttribute('href'))).ok()).toBe(true);
 await unused.scrollIntoViewIfNeeded();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/80-unused-source-evidence.'+info.project.name+'.png'),fullPage:true});
 expect(mutations).toEqual([]);
});

test('Request explicit accounting for unused sources through the conversation',async({page,request})=>{
 const jid='b68d916b137b4030ac30d3a573d3c413';const job=await (await request.get('/api/workspace/source-jobs/'+jid)).json();
 expect(job.status).toBe('awaiting_confirmation');
 await page.setExtraHTTPHeaders({'X-Eval-Actor':'codex-development-source-accounting'});
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[job]}}));
 let child:any;await page.route('**/api/workspace/source-jobs/'+jid+'/revise',async route=>{
   expect(route.request().postDataJSON().review_unused_sources).toBe(true);
   const response=await route.fetch();expect(response.ok()).toBe(true);child=await response.json();await route.fulfill({response});
 });
 await page.goto('/#/workspace');const nav=page.getByRole('navigation',{name:'Workstream sections'});
 await nav.getByRole('button',{name:/^Files(?: · \d+)?$/}).click();await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(job.source_id);await nav.getByRole('button',{name:'Conversation',exact:true}).click();
 await page.getByRole('button',{name:'Ask Bonsai to check unused sources',exact:true}).click();
 const check=page.getByRole('checkbox',{name:'Require an observation or a quoted exclusion explanation for each unused source',exact:true});await expect(check).toBeChecked();
 await page.reload();await expect(check).toBeChecked();
 await page.getByRole('button',{name:'Discuss this change',exact:true}).click();await expect.poll(()=>Boolean(child)).toBe(true);
 expect(child.source_review_record_ids).toHaveLength(1);expect(child.status).toMatch(/queued|running/);
 await fs.writeFile(path.resolve('.cache/source-accounting-browser-job.json'),JSON.stringify(child,null,2));
});

test('Source accounting revision exposes both recovered observations',async({page,request},info)=>{
 const job=await (await request.get('/api/workspace/source-jobs/223169cf554e4ad89f66df243bfa1b67')).json();
 expect(job.status).toBe('awaiting_confirmation');expect(job.source_coverage.structured_usage.cited_records).toBe(2);
 await page.route('**/api/workspace/source-jobs',route=>route.fulfill({json:{jobs:[job]}}));
 await page.goto('/#/workspace');const nav=page.getByRole('navigation',{name:'Workstream sections'});
 await nav.getByRole('button',{name:/^Files(?: · \d+)?$/}).click();await page.getByRole('combobox',{name:'Saved source',exact:true}).selectOption(job.source_id);await nav.getByRole('button',{name:'Conversation',exact:true}).click();
 await expect(page.getByText('2 of 2 supplied source records are cited by the proposed data.',{exact:false})).toBeVisible();
 await page.getByText('Review 2 proposed records',{exact:true}).click();const records=page.locator('.structured-records');await expect(records.locator('article')).toHaveCount(2);await expect(records).toContainText('2026-09-20');await expect(records).toContainText('Ready for review');
 await records.scrollIntoViewIfNeeded();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/81-source-accounting-revision.'+info.project.name+'.png'),fullPage:true});
});
