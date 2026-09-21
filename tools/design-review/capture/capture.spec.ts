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
 await expect(page.getByRole('heading',{name:'Your source data'})).toBeVisible();
 await expect(page.getByText(/Describe a question to create a source-bound visualization/)).toBeVisible();
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
 await expect(page.getByRole('button',{name:'Create visualization',exact:true})).toBeVisible();
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
