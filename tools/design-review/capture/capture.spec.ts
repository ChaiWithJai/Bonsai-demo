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
