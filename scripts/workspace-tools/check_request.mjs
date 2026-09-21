import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium,expect} from '@playwright/test';
const [url,contractPath,output]=process.argv.slice(2);
const contract=JSON.parse(await fs.readFile(contractPath,'utf8'));
const browser=await chromium.launch();
const report={passed:false,scope:'Only the supplied request checks, not full semantic correctness',viewports:[]};
try {
 for(const width of [1440,390]) {
  const page=await browser.newPage({viewport:{width,height:900},extraHTTPHeaders:{'X-Eval-Actor':'workspace-request-check'}});
  page.setDefaultTimeout(5000);
  const result={width,steps:[]};report.viewports.push(result);
  try {
   await page.goto(url);
   for(const [index,step] of contract.entries()) {
    const target=step.target.test_id ? page.getByTestId(step.target.test_id) : page.getByRole(step.target.role,{name:step.target.name,exact:true});
    try {
     if(step.action==='click')await target.click();
     else if(step.action==='visible')await expect(target)[step.value?'toBeVisible':'toBeHidden']();
     else if(step.action==='text')await expect(target).toHaveText(step.value);
     else if(step.action==='pressed')await expect(target).toHaveAttribute('aria-pressed',String(step.value));
     else if(step.action==='count')await expect(target).toHaveCount(step.value);
     else throw new Error('Unknown request check action');
     result.steps.push({index,passed:true});
    } catch(error) {result.steps.push({index,passed:false,error:String(error)});throw error;}
   }
  } finally {await page.screenshot({path:path.join(output,`request-${width}.png`),fullPage:true});await page.close();}
 }
 report.passed=true;
} catch(error) {report.error=String(error);process.exitCode=1;}
finally {await browser.close();await fs.writeFile(path.join(output,'report.json'),JSON.stringify(report,null,2));}
console.log(JSON.stringify(report));
