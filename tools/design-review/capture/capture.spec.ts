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
 await page.screenshot({path:path.resolve(import.meta.dirname,'../shots/14-docx.'+info.project.name+'.png'),fullPage:true});
});
