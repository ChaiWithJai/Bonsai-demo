import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {compile} from 'svelte/compiler';
import {build} from 'esbuild';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)));
export async function render(source,outdir){
 await fs.mkdir(outdir,{recursive:true});
 const compilerWarnings=[];
 const result=await build({stdin:{contents:`import {mount} from 'svelte'; import App from 'candidate:App'; mount(App,{target:document.getElementById('app')});`,resolveDir:root},bundle:true,write:false,format:'iife',platform:'browser',conditions:['browser'],plugins:[{name:'candidate',setup(b){
 b.onResolve({filter:/^candidate:App$/},()=>({path:'App.svelte',namespace:'candidate'}));
 b.onLoad({filter:/.*/,namespace:'candidate'},()=>{
  try{const compiled=compile(source,{filename:'App.svelte',generate:'client',css:'injected',dev:true});compilerWarnings.push(...compiled.warnings.map(w=>({code:w.code,message:w.message,start:w.start})));return {contents:compiled.js.code,resolveDir:root};}
  catch(e){return {errors:[{text:e.message,location:e.start?{file:'App.svelte',line:e.start.line,column:e.start.column,lineText:source.split('\n')[e.start.line-1]}:undefined,notes:e.frame?[{text:e.frame}]:[]}]};}
 });
 b.onResolve({filter:/.*/},args=>{if(args.namespace==='candidate' && !/^svelte(?:\/|$)/.test(args.path))return {errors:[{text:'Candidate imports are limited to Svelte. Use the supplied HTTP query API.'}]};});
 }}]});
 await fs.writeFile(path.join(outdir,'app.js'),result.outputFiles[0].contents);
 await fs.writeFile(path.join(outdir,'index.html'),'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Generated data interface</title></head><body><div id="app"></div><script src="/app.js"></script></body></html>');
 return {bundle_bytes:result.outputFiles[0].contents.length,warnings:result.warnings.map(w=>w.text),svelte_warnings:compilerWarnings};
}
if(process.argv[1]===fileURLToPath(import.meta.url)){
 try{const result=await render(await fs.readFile(process.argv[2],'utf8'),path.resolve(process.argv[3]));console.log(JSON.stringify(result));}catch(e){console.error(e.message);process.exitCode=1;}
}
