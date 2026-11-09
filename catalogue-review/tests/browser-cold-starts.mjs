// Exercise cold-start HTTP bursts against independent disposable fake servers.
// Every failed load fails the run; there are no reloads or application retries.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

let chromium;
try{({chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright'));}
catch(error){throw new Error('Install Playwright or set PLAYWRIGHT_MODULE to its index.mjs before running browser-cold-starts.mjs.',{cause:error});}
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const count=Number(process.env.REVIEW_COLD_STARTS||20),parallel=Number(process.env.REVIEW_BROWSER_CONCURRENCY||2);
assert(Number.isInteger(count)&&count>=2&&count<=100,'REVIEW_COLD_STARTS must be an integer from 2 to 100.');
assert(Number.isInteger(parallel)&&parallel>=1&&parallel<=4,'REVIEW_BROWSER_CONCURRENCY must be an integer from 1 to 4.');
const output=process.env.REVIEW_BROWSER_OUTPUT?path.join(process.env.REVIEW_BROWSER_OUTPUT,'cold-starts'):
  await fs.mkdtemp(path.join(os.tmpdir(),'boldstone-browser-cold-starts-'));
await fs.mkdir(output,{recursive:true});
const python=process.env.REVIEW_BROWSER_PYTHON||path.join(root,'application/.venv/bin/python');
const html=await fs.readFile(path.join(root,'catalogue-review/static/index.html'),'utf8');
const expected=new Map();
for(const [,url] of html.matchAll(/<script\s+src="([^"]+)"/g)){
  const raw=await fs.readFile(path.join(root,'catalogue-review/static',url.slice(1)));
  expected.set(url,crypto.createHash('sha256').update(raw).digest('hex'));
}
assert(expected.size>0,'The review page must declare its application scripts.');
let executablePath=process.env.CHROME_PATH;
if(!executablePath)try{await fs.access('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome');executablePath='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';}catch{}
const browser=await chromium.launch({headless:true,...(executablePath?{executablePath}:{})});

async function coldStart(index){
  const child=spawn(python,[path.join(root,'catalogue-review/tests/isolated_jobs_server.py'),
    '--port','0','--cost-model','--gallery-layout','--component-controls','--browser-smoke'],{cwd:root,stdio:['ignore','pipe','pipe']});
  const result={index,status:'RUNNING',script_responses:[],failed_requests:[],console_errors:[],page_errors:[],api_failures:[],blocked_external_requests:[]};
  let context,page,serverLog='';const pendingBodies=[];
  child.stderr.on('data',chunk=>{serverLog+=chunk;});
  try{
    const ready=await new Promise((resolve,reject)=>{
      let buffer='';const timer=setTimeout(()=>reject(new Error('The disposable fixture did not start.')),15000);
      child.once('error',error=>{clearTimeout(timer);reject(error);});
      child.once('exit',code=>{clearTimeout(timer);reject(new Error('Fixture exited before readiness: '+code));});
      child.stdout.on('data',chunk=>{buffer+=chunk;for(const line of buffer.split('\n'))try{
        const record=JSON.parse(line);if(record.native==='in-memory fake only'&&record.url){clearTimeout(timer);resolve(record);return;}
      }catch{}});
    });
    const base=new URL(ready.url).origin;assert.equal(new URL(base).hostname,'127.0.0.1');result.fixture_url=base;
    context=await browser.newContext();
    await context.route('**/*',async route=>{
      const url=new URL(route.request().url());
      if(['http:','https:'].includes(url.protocol)&&url.origin!==base){result.blocked_external_requests.push(url.origin);await route.abort();}
      else await route.continue();
    });
    page=await context.newPage();page.setDefaultTimeout(10000);
    page.on('console',message=>{if(message.type()==='error')result.console_errors.push(message.text());});
    page.on('pageerror',error=>result.page_errors.push(error.message));
    page.on('requestfailed',request=>result.failed_requests.push({url:request.url(),error:request.failure()?.errorText}));
    page.on('response',response=>{
      const url=new URL(response.url());
      if(url.pathname.startsWith('/api/')&&response.status()>=400)result.api_failures.push({path:url.pathname,status:response.status()});
      if(!expected.has(url.pathname))return;
      const row={path:url.pathname,status:response.status(),type:response.headers()['content-type']};
      result.script_responses.push(row);
      pendingBodies.push((async()=>{try{
        const body=await response.body();row.bytes=body.length;row.sha256=crypto.createHash('sha256').update(body).digest('hex');
        row.matches_source=row.sha256===expected.get(url.pathname);
      }catch(error){row.error=error.message;}})());
    });
    await page.goto(base+'/#L1',{waitUntil:'networkidle'});
    await page.waitForFunction(()=>typeof startDropboxSync==='function'&&
      [...document.querySelectorAll('#image-grid img')].some(image=>image.complete&&image.naturalWidth>0));
    await Promise.all(pendingBodies);
    for(const url of expected.keys()){
      const response=result.script_responses.find(row=>row.path===url);
      assert(response,'Missing script response: '+url);
      assert.equal(response.status,200,url);assert(response.matches_source,'Script bytes changed: '+url);
      assert(['text/javascript','application/javascript','application/x-javascript'].includes(response.type?.split(';')[0]),'Invalid script MIME: '+url);
    }
    assert.deepEqual(result.failed_requests,[]);assert.deepEqual(result.page_errors,[]);
    assert.deepEqual(result.api_failures,[]);assert.deepEqual(result.blocked_external_requests,[]);
    result.status='PASS';
  }catch(error){
    result.status='FAIL';result.error=error.stack||String(error);
    await Promise.allSettled(pendingBodies);
    if(page)try{result.page_text=(await page.locator('body').innerText()).slice(0,4000);await page.screenshot({path:path.join(output,'failure-'+index+'.png')});}catch{}
  }finally{
    if(context)await context.close();
    if(child.exitCode===null&&child.signalCode===null){child.kill('SIGINT');await new Promise(resolve=>{
      child.once('exit',resolve);setTimeout(()=>{child.kill('SIGKILL');resolve();},5000).unref();
    });}
    await fs.writeFile(path.join(output,'run-'+index+'.json'),JSON.stringify(result,null,2));
    await fs.writeFile(path.join(output,'server-'+index+'.log'),serverLog);
    console.log(result.status+' cold start '+(index+1)+'/'+count);
  }
  return result;
}

const results=[];
try{
  for(let index=0;index<count;index+=parallel)
    results.push(...await Promise.all(Array.from({length:Math.min(parallel,count-index)},(_,offset)=>coldStart(index+offset))));
}finally{await browser.close();}
const summary={status:results.every(result=>result.status==='PASS')?'PASS':'FAIL',runs:count,parallel,
  passed:results.filter(result=>result.status==='PASS').length,failed:results.filter(result=>result.status!=='PASS').map(result=>result.index),
  scripts_per_load:expected.size,native:'in-memory fake only',live_dropbox_calls:0,output};
await fs.writeFile(path.join(output,'cold-start-checks.json'),JSON.stringify(summary,null,2));
console.log(JSON.stringify(summary,null,2));if(summary.status!=='PASS')process.exitCode=1;
