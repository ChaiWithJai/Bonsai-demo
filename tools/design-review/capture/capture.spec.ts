import {test,expect} from '@playwright/test';
import path from 'node:path';
import fs from 'node:fs/promises';
test('Workspace screens',async({page},info)=>{
 const shots=path.resolve(import.meta.dirname,'../shots');await fs.mkdir(shots,{recursive:true});
 await page.goto('/#/workspace');
 await expect(page.getByRole('heading',{name:'Build on what you know.'})).toBeVisible();
 await expect(page.getByRole('status',{name:'Opening Workspace…'})).toHaveCount(0);
 const empty=page.getByRole('button',{name:'Open source explorer'});
 if(await empty.isVisible())await empty.click();
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
 await expect(page.getByLabel('Describe the next change')).toBeVisible();
});

test('Workspace uploaded data and persisted review',async({page},info)=>{
 await page.goto('http://127.0.0.1:5258/#/workspace');
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
