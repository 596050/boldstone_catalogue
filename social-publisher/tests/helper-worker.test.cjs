const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname,'../browser-helper/service-worker.js'),'utf8').replace(/^import .*;$/gm,'');

function fixture(options={}) {
  const request={request_id:'1'.repeat(32),job_id:'fixture',sha256:'a'.repeat(64),window_id:10,tab_id:11,
    expected_url:'https://www.linkedin.com/sharing/compose',owner:'owner',lease:'private-lease',name:'photo.png',size:4};
  const calls={injections:[],media:0,acks:0,network:0};
  const storage={};
  let failAck=!!options.failAck;
  const noop={addListener(){}};
  const chrome={
    tabs:{get:async()=>({id:11,windowId:10,url:request.expected_url,incognito:false,active:true,...options.tab})},
    windows:{get:async()=>({type:'normal',focused:false,...options.window})},
    scripting:{executeScript:async value=>{calls.injections.push(value);if(options.lostResult)throw new Error('response lost');
      return [{frameId:0,result:{ok:true,request_id:request.request_id,sha256:request.sha256,phase:'FILE_EVENTS_DISPATCHED'}}];}},
    storage:{local:{get:async key=>({[key]:storage[key]}),set:async value=>Object.assign(storage,value),remove:async key=>{delete storage[key];}}},
    alarms:{create:async()=>{},onAlarm:noop},runtime:{id:'a'.repeat(32),onInstalled:noop,onStartup:noop,onMessage:noop}
  };
  const fetch=async (url,options)=>{
    calls.network++;
    assert.ok(url.startsWith('http://127.0.0.1:8768/'));
    assert.equal(options.credentials,'omit');
    assert.equal(options.headers.Authorization,'Bearer fixture-secret');
    const endpoint=new URL(url).pathname;
    if(endpoint.startsWith('/claim/')) return {ok:true,json:async()=>request};
    if(endpoint.startsWith('/media/')) {calls.media++;return {ok:true,arrayBuffer:async()=>Uint8Array.from([1,2,3,4]).buffer};}
    if(endpoint.startsWith('/result/')) {
      calls.acks++;calls.result=JSON.parse(options.body);
      if(failAck){failAck=false;return {ok:false,status:503};}
      return {ok:true,json:async()=>({ok:true})};
    }
    throw new Error('unexpected endpoint '+endpoint);
  };
  const context=vm.createContext({chrome,fetch,BRIDGE:{baseURL:'http://127.0.0.1:8768',token:'fixture-secret'},
    uploadPhoto:async function uploadPhoto(){},Uint8Array,URL,AbortSignal,setTimeout,clearTimeout,
    btoa:value=>Buffer.from(value,'binary').toString('base64')});
  const worker=vm.runInContext(source+'\n;({processOne,acknowledgePending,wake});',context);
  return {request,calls,storage,worker};
}

test('the helper injects only into the exact normal background tab and keeps the lease private',async()=>{
  const f=fixture();await f.worker.processOne({request_id:f.request.request_id});
  assert.equal(f.calls.injections.length,1);
  const injection=f.calls.injections[0];
  assert.equal(injection.world,'MAIN');assert.equal(injection.target.tabId,11);
  assert.equal(injection.args[0].base64,'AQIDBA==');
  assert.equal('lease' in injection.args[0],false);
  assert.equal(JSON.stringify(injection.args).includes('fixture-secret'),false);
  assert.equal(f.storage.pendingAck,undefined);
});

test('changed, incognito, popup and foreground contexts receive no image and no injection',async()=>{
  for(const options of [{tab:{windowId:99}},{tab:{url:'https://example.com/'}},{tab:{incognito:true}},
    {window:{type:'popup'}},{window:{focused:true}}]) {
    const f=fixture(options);await f.worker.processOne({request_id:f.request.request_id});
    assert.equal(f.calls.injections.length,0);assert.equal(f.calls.media,0);
    assert.equal(f.calls.result.ok,false);assert.equal(f.calls.result.phase,'NOT_STARTED');
  }
});

test('a lost acknowledgement is saved and retried without injecting or uploading twice',async()=>{
  const f=fixture({failAck:true});
  await assert.rejects(f.worker.processOne({request_id:f.request.request_id}),/BRIDGE_HTTP_503/);
  assert.ok(f.storage.pendingAck);assert.equal(f.calls.injections.length,1);
  await f.worker.acknowledgePending();
  assert.equal(f.storage.pendingAck,undefined);assert.equal(f.calls.acks,2);
  assert.equal(f.calls.injections.length,1);assert.equal(f.calls.media,1);
});

test('a lost injection result remains uncertain',async()=>{
  const f=fixture({lostResult:true});await f.worker.processOne({request_id:f.request.request_id});
  assert.equal(f.calls.result.phase,'OUTCOME_UNKNOWN');assert.equal(f.calls.result.ok,false);
});
test('the background worker stays idle until the local setup connection succeeds',async()=>{
  const f=fixture();await f.worker.wake();
  assert.equal(f.calls.network,0);assert.equal(f.calls.injections.length,0);
});

function popupFixture(options={}) {
  const popupSource=fs.readFileSync(path.join(__dirname,'../browser-helper/popup.js'),'utf8').replace(/^import .*;$/gm,'');
  const calls={fetches:0,worker:0,stored:{}};const output={};let click;
  const health={version:'1.0.0',extension_id:'a'.repeat(32),bind:'127.0.0.1',...options.health};
  const context=vm.createContext({
    document:{getElementById:id=>id==='result'?output:{addEventListener:(_,handler)=>{click=handler;}}},
    navigator:{permissions:{query:async()=>({state:options.permission||'granted'})}},
    chrome:{runtime:{id:'a'.repeat(32),sendMessage:async()=>{calls.worker++;return {ok:true,health};}},
      storage:{local:{set:async value=>Object.assign(calls.stored,value)}}},
    BRIDGE:{baseURL:'http://127.0.0.1:8768',token:'fixture-secret'},AbortSignal,
    fetch:async(url,init)=>{
      calls.fetches++;assert.equal(url,'http://127.0.0.1:8768/health');
      assert.equal(init.credentials,'omit');assert.equal(init.targetAddressSpace,'loopback');
      return {ok:true,json:async()=>health};
    }
  });
  vm.runInContext(popupSource,context);
  return {calls,output,click:()=>click()};
}
test('the setup popup authenticates the exact local bridge before waking background work',async()=>{
  const f=popupFixture();await f.click();
  assert.equal(f.calls.fetches,1);assert.equal(f.calls.stored.bridgeConnected,true);assert.equal(f.calls.worker,1);
});
test('denied local access and a mismatched bridge identity leave background work disabled',async()=>{
  for(const options of [{permission:'denied'},{health:{extension_id:'wrong-extension'}}]) {
    const f=popupFixture(options);await f.click();
    assert.equal(f.calls.stored.bridgeConnected,undefined);assert.equal(f.calls.worker,0);
    assert.match(f.output.textContent,/Allow loopback|identity did not match/);
  }
});
