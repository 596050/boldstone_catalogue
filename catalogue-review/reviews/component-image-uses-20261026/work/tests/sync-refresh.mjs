// Pure refresh-controller tests. No browser or production review database.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source=fs.readFileSync(new URL('../static/sync-tools.js',import.meta.url),'utf8');
function fixture(){
  const main={scrollTop:180},calls=[],renders=[];
  const state={pid:'one',request:1,tab:'images',boot:{},reviews:new Map(),dirty:new Set(),selected:new Set()};
  const document={hidden:false,activeElement:{matches:()=>false},querySelector:()=>null};
  const fresh={products:[],assignments:[],dropbox_sync:{generation:2}};
  const payload={images:[{id:'new'}],reviews:[]};
  const ctx=vm.createContext({state,document,window:{scrollY:80,scrollTo:(...args)=>calls.push(['scroll',...args])},
    $:()=>main,api:async(...args)=>{calls.push(args);return args[0]==='/api/bootstrap'?fresh:payload;},
    absorb:()=>{},key:()=>'',renderList:()=>renders.push('list'),renderMain:()=>{main.scrollTop=0;renders.push('main');}});
  vm.runInContext(source,ctx);
  return {ctx,state,document,main,calls,renders,payload,fresh};
}
test('fresh images update the open gallery and retain scroll and view filters',async()=>{
  const f=fixture();f.state.imageFilter='in_situ';
  await f.ctx.refreshDropboxView({generation:2});
  assert.equal(f.state.current,f.payload);
  assert.equal(f.main.scrollTop,180);
  assert.equal(f.state.imageFilter,'in_situ');
  assert.deepEqual(f.renders,['list','main']);
  assert.ok(f.calls.filter(x=>x[0].startsWith('/api/')).every(x=>x.length===1));
  assert.equal(vm.runInContext('dropboxShownGeneration',f.ctx),2);
});
test('selection, dirty fields, open modal, focused input, save and load defer refresh',async()=>{
  for(const block of [f=>f.state.selected.add('image'),f=>f.state.dirty.add('field'),
    f=>f.document.querySelector=()=>({open:true}),f=>f.document.activeElement.matches=()=>true,
    f=>f.state.saving=true,f=>f.state.loading=true]){
    const f=fixture();block(f);await f.ctx.refreshDropboxView({generation:2});
    assert.equal(f.calls.length,0);assert.equal(f.state.current,undefined);
  }
});
test('an edit starting during a fetch keeps the current view and pending generation',async()=>{
  const f=fixture();const read=f.ctx.api;
  f.ctx.api=async(...args)=>{const result=await read(...args);f.state.dirty.add('Depth');return result;};
  await f.ctx.refreshDropboxView({generation:2});
  assert.equal(f.state.current,undefined);assert.equal(f.renders.length,0);
  assert.equal(vm.runInContext('dropboxShownGeneration',f.ctx),0);
});
test('navigation during a fetch cannot replace the next sculpture with old content',async()=>{
  const f=fixture();const read=f.ctx.api;
  f.ctx.api=async(...args)=>{const result=await read(...args);f.state.pid='two';f.state.request++;return result;};
  await f.ctx.refreshDropboxView({generation:2});
  assert.equal(f.state.pid,'two');assert.equal(f.state.current,undefined);assert.equal(f.renders.length,0);
});
test('specification tab remains mounted while gallery data refreshes',async()=>{
  const f=fixture();f.state.tab='specs';
  await f.ctx.refreshDropboxView({generation:2});
  assert.equal(f.state.current,f.payload);assert.deepEqual(f.renders,['list']);
});
test('the same generation does not reload the gallery repeatedly',async()=>{
  const f=fixture();await f.ctx.refreshDropboxView({generation:2});const n=f.calls.length;
  await f.ctx.refreshDropboxView({generation:2});assert.equal(f.calls.length,n);
});
