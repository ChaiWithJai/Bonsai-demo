import {defineConfig,devices} from '@playwright/test';
export default defineConfig({testDir:'.',timeout:60000,workers:1,reporter:'list',use:{baseURL:'http://127.0.0.1:5257',reducedMotion:'reduce'},projects:[{name:'desktop',use:{...devices['Desktop Chrome'],viewport:{width:1440,height:1000}}},{name:'mobile',use:{...devices['Desktop Chrome'],viewport:{width:390,height:844},hasTouch:true}}]});
