// Exercise the shipped UI handlers with deferred saves and isolated DOM stubs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

function harness() {
  const listeners = {}, nodes = new Map();
  const node = selector => {
    if (!nodes.has(selector)) nodes.set(selector, {textContent:'', innerHTML:'', value:'', addEventListener(){}});
    return nodes.get(selector);
  };
  const context = vm.createContext({console, URL, URLSearchParams, setTimeout, clearTimeout,
    document: {querySelector:node, querySelectorAll:()=>[], addEventListener:(type,fn)=>{
      (listeners[type] ||= []).push(fn);
    }}, window:{addEventListener(){},confirm:()=>true},
    location:{hash:''}, history:{replaceState(){}},
    localStorage:{getItem:()=>null,setItem(){}}, FormData:class {entries(){return [];}}
  });
  const run = source => vm.runInContext(source, context);
  const base = path.resolve(__dirname, '..', 'static');
  run(fs.readFileSync(path.join(base,'app.js'),'utf8').replace(/\nboot\(\);\s*$/, '\n'));
  run(fs.readFileSync(path.join(base,'image-tools.js'),'utf8'));
  run(fs.readFileSync(path.join(base,'family-tools.js'),'utf8'));
  run("state.pid='A';state.request=1;state.boot={image_types:{},products:[],families:[]};state.current={images:[]};scheduleCoverageRefresh=()=>{};renderGrid=()=>{};toast=()=>{};");
  return {context, run, listeners, node};
}

test('bulk saves keep their original sculpture even if the user navigates', async () => {
  const h = harness(), calls = [];
  let release;
  h.context.save = async (kind,pid,aid,values) => {
    calls.push({pid,aid});
    if(calls.length===1) await new Promise(resolve=>{release=resolve;});
    return {version:1,data:values};
  };
  h.run("state.selected=new Set(['one','two']);");
  const target={dataset:{bulk:'advertising'},disabled:false};
  const pending=h.listeners.click[0]({target:{closest:s=>s==='.select-box'?null:target}});
  assert.equal(calls.length,1);
  h.run("state.pid='B';state.request=2;state.selected=new Set(['new-selection']);");
  release();await pending;
  assert.deepEqual(calls,[{pid:'A',aid:'one'},{pid:'A',aid:'two'}]);
  assert.equal(h.run("state.selected.has('new-selection')"),true);
});

test('a partial bulk failure keeps only unsuccessful items selected', async () => {
  const h=harness();let calls=0;
  h.context.save=async()=>{if(++calls===2)throw new Error('Version conflict');return {version:1,data:{}};};
  h.run("state.selected=new Set(['one','two','three']);");
  const target={dataset:{bulk:'advertising'},disabled:false};
  await h.listeners.click[0]({target:{closest:s=>s==='.select-box'?null:target}});
  assert.equal(calls,2);
  assert.equal(h.run('JSON.stringify([...state.selected])'),'["two","three"]');
  assert.equal(target.disabled,false);
});

test('finishing a specification save after navigation leaves the new page untouched', async () => {
  const h=harness();let release;
  h.context.FormData=class {*[Symbol.iterator](){yield ['decision','edit'];yield ['value','Original sculpture renamed'];}};
  h.context.save=async()=>new Promise(resolve=>{release=()=>resolve({version:1,data:{}});});
  const button={disabled:false};
  h.context.oldForm={id:'field-Name',dataset:{field:'Name'},querySelector:()=>button,matches:()=>true};
  const pending=h.run('submitForm(oldForm)');
  h.run("state.pid='B';state.request=2;state.current={id:'B',name:'New sculpture'};state.dirty.add('field-Name');");
  release();await pending;
  assert.equal(h.run('state.current.name'),'New sculpture');
  assert.equal(h.run("state.dirty.has('field-Name')"),true);
  assert.equal(button.disabled,false);
});

test('removed and unreviewed choices do not inflate listing totals', () => {
  const h=harness();
  h.run(`state.current.images=[{id:'one',association:{tier:'folder'}},{id:'removed',association:{tier:'removed'}},{id:'pending',association:{tier:'folder'}}];
    for(const aid of ['one','removed'])state.reviews.set(key('image','A',aid),{data:{decision:'reviewed',uses:['listing']}});
    state.reviews.set(key('image','A','pending'),{data:{decision:'pending',uses:['listing']}});
    updateCounts();updateScopeSummary();`);
  assert.equal(h.node('#listing-count').textContent,1);
  assert.equal(h.node('#image-reviewed-count').textContent,1);
  assert.match(h.node('#image-scope-summary').innerHTML,/2 retained associations/);
});

test('No component chosen filter includes related-only family candidates', () => {
  const h=harness();
  h.run(`state.pid='__library__';state.use='unassigned';state.library={images:[
    {id:'candidate',product_ids:['A','B'],component_ids:[]},
    {id:'shown',product_ids:['A'],component_ids:['A']}]};sortImages=x=>x;`);
  assert.equal(h.run("JSON.stringify(filteredImages().map(x=>x.id))"),'["candidate"]');
});

test('unchecking Listing also unchecks Primary while retaining Ads', async () => {
  const h=harness();
  const form={id:'image-form',elements:{primary:{checked:true}},querySelector:()=>null};
  const el={name:'use',value:'listing',checked:false,dataset:{},closest:s=>s==='form'||s==='#image-form'?form:null};
  await h.listeners.change[0]({target:el});
  assert.equal(form.elements.primary.checked,false);
});

test('returning a primary image to Not reviewed clears its primary choice', async () => {
  const h=harness();
  const form={id:'image-form',elements:{primary:{checked:true}},querySelector:()=>null};
  const el={id:'image-decision',name:'decision',value:'pending',dataset:{},closest:s=>s==='form'||s==='#image-form'?form:null};
  await h.listeners.change[0]({target:el});
  assert.equal(form.elements.primary.checked,false);
});
