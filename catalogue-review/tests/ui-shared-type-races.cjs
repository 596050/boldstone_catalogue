const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test');
const tick=()=>new Promise(setImmediate);
function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};}
function harness(){
  const nodes=new Map(),messages=[],menus=[];
  const node=s=>{if(!nodes.has(s))nodes.set(s,{innerHTML:'',textContent:'',open:false,disabled:false,
    querySelector:()=>null,querySelectorAll:()=>[],addEventListener(){},setAttribute(){},removeAttribute(){},
    close(){this.open=false;},showModal(){this.open=true;}});return nodes.get(s);};
  const context=vm.createContext({console,URL,URLSearchParams,document:{querySelector:node,querySelectorAll:s=>s==='[data-card-types]'?menus:[],addEventListener(){}},
    window:{addEventListener(){}},setTimeout(){},clearTimeout(){},setInterval(){},clearInterval(){}});
  const run=s=>vm.runInContext(s,context);
  for(const name of ['app.js','image-tools.js','component-tools.js'])run(fs.readFileSync(path.join(__dirname,'../static',name),'utf8').replace(/\nboot\(\);\s*$/,'\n'));
  context.report=message=>messages.push(message);
  run(`state.pid='A';state.request=1;state.boot={products:[],image_types:{product:'Product',in_situ:'In situ',detail:'Detail'}};
    state.current={images:[{id:'one',name:'one.jpg',types:['product'],original:{dropbox_content_hash:'old-hash'}},
      {id:'two',name:'two.jpg',types:['product'],original:{dropbox_content_hash:'second-hash'}}]};
    state.reviews.set(key('asset','','one'),{kind:'asset',product_id:'',item_id:'one',version:0,data:{tags:['garden'],rights:'owned',notes:'Keep these notes'}});
    renderGrid=()=>{};renderCategories=()=>{};scheduleCoverageRefresh=()=>{};toast=report;`);
  function menu(aid='one',types=['product','detail'],changed='detail'){
    const status={textContent:''},summary={textContent:''},role={textContent:''},attributes=new Set();
    const situ={pressed:'false',selected:false,setAttribute(name,value){if(name==='aria-pressed')this.pressed=value;}};
    situ.classList={toggle(name,value){if(name==='selected')situ.selected=value;}};
    const badges={outerHTML:''};
    const card={querySelector:s=>s==='.role-name'?role:s==='[data-in-situ]'?situ:s==='.image-role-badges'?badges:null};
    const inputs=['product','in_situ','detail'].map(type=>({dataset:{cardType:type},checked:types.includes(type),disabled:false}));
    const value={dataset:{cardTypes:aid},open:true,isConnected:true,contains:()=>false,
      setAttribute:name=>attributes.add(name),removeAttribute:name=>attributes.delete(name),hasAttribute:name=>attributes.has(name),
      closest:s=>s==='.image-card'?card:null,
      querySelector:s=>s==='.card-type-status'?status:s==='summary span'?summary:null,
      querySelectorAll:s=>s==='input:checked'?inputs.filter(x=>x.checked):inputs};
    inputs.forEach(input=>input.closest=()=>value);
    menus.push(value);
    return {value,status,summary,inputs,situ,badges,input:inputs.find(x=>x.dataset.cardType===changed)};
  }
  function card(m){context.input=m.input;return run('saveCardTypes(input)');}
  function situ(aid='one'){context.button={dataset:{inSitu:aid},disabled:false};return run('toggleInSitu(button)');}
  function slow(fail=false){
    const gate=deferred(),bodies=[],saved=new Map();
    context.api=async(url,body)=>{
      bodies.push(body);if(bodies.length===1){await gate.promise;if(fail)throw Error('Connection lost');}
      const old=saved.get(body.item_id),version=old?.version||0;
      if(body.version!==version)throw Error('Review changed; reload before saving');
      const result={...body,version:version+1};saved.set(body.item_id,result);return result;
    };
    return {gate,bodies,saved};
  }
  return {context,run,node,messages,menu,card,situ,slow};
}

for(const first of ['dropdown','button'])test(`rapid ${first} then the other type control saves both choices`,async()=>{
  const h=harness(),s=h.slow(),m=h.menu();
  const pending=first==='dropdown'?[h.card(m),h.situ()]:[h.situ(),h.card(m)];
  s.gate.resolve();await Promise.all(pending);
  assert.deepEqual(s.bodies.map(b=>b.version),[0,1]);
  assert.deepEqual([...h.run("data('asset','','one').types")].sort(),['detail','in_situ','product']);
  assert.equal(h.run("data('asset','','one').notes"),'Keep these notes');
  assert.equal(h.run("data('asset','','one').rights"),'owned');
  assert.deepEqual([...h.run("data('asset','','one').tags")],['garden']);
  assert.deepEqual(m.inputs.filter(x=>x.checked).map(x=>x.dataset.cardType).sort(),['detail','in_situ','product']);
  assert(!h.messages.some(m=>m.includes('Review changed')));
});

test('rapid In situ toggles retain their click order',async()=>{
  const h=harness(),s=h.slow(),pending=[h.situ(),h.situ()];
  s.gate.resolve();await Promise.all(pending);
  assert.deepEqual(s.bodies.map(b=>b.version),[0,1]);
  assert.deepEqual([...h.run("data('asset','','one').types")],['product']);
});

test('unchecking one type preserves another type added by a pending button save',async()=>{
  const h=harness(),s=h.slow(),m=h.menu('one',[],'product');
  const pending=[h.situ(),h.card(m)];s.gate.resolve();await Promise.all(pending);
  assert.deepEqual([...h.run("data('asset','','one').types")],['in_situ']);
  assert.equal(m.inputs.find(x=>x.dataset.cardType==='in_situ').checked,true);
});

test('a dropdown In situ choice updates the button and badges while the menu remains open',async()=>{
  const h=harness(),s=h.slow(),m=h.menu('one',['product','in_situ'],'in_situ');
  const pending=h.card(m);s.gate.resolve();await pending;
  assert.equal(m.value.open,true);assert.equal(m.situ.pressed,'true');assert.equal(m.situ.selected,true);
  assert.match(m.badges.outerHTML,/role-in_situ/);
  m.input.checked=false;await h.card(m);
  assert.equal(m.value.open,true);assert.equal(m.situ.pressed,'false');assert.equal(m.situ.selected,false);
  assert.doesNotMatch(m.badges.outerHTML,/role-in_situ/);
});

test('a failed type save prevents its queued follow-up from overwriting an unknown result',async()=>{
  const h=harness(),s=h.slow(true),m=h.menu();
  const pending=[h.situ(),h.card(m)];s.gate.resolve();await Promise.all(pending);
  assert.equal(s.bodies.length,1);
  assert.equal(m.status.textContent,'Not saved');
  assert(h.messages.some(m=>/previous|earlier/i.test(m)));
  assert.deepEqual(m.inputs.filter(x=>x.checked).map(x=>x.dataset.cardType),['product']);
});

test('a slow type save does not hold up a different image',async()=>{
  const h=harness(),s=h.slow(),first=h.situ();await h.situ('two');
  assert.equal(s.bodies.length,2);assert(h.run("data('asset','','two').types.includes('in_situ')"));
  s.gate.resolve();await first;
});

test('queued shared choices keep the displayed original hash after navigation',async()=>{
  const h=harness(),s=h.slow(),m=h.menu(),pending=[h.situ(),h.card(m)];
  h.run("state.pid='B';state.request++;state.current={images:[]}");s.gate.resolve();await Promise.all(pending);
  assert.deepEqual(s.bodies.map(b=>b.expected_content_hash),['old-hash','old-hash']);
  assert.deepEqual(s.bodies.map(b=>b.product_id),['','']);
});

test('opening image details waits for pending shared-type choices',async()=>{
  const h=harness(),s=h.slow(),pending=h.situ();
  try{h.run("openImage('one')");assert.equal(h.node('#image-dialog').open,false);assert(h.messages.some(m=>/saving/i.test(m)));}
  finally{s.gate.resolve();await pending;}
});

test('finishing pending reviews waits for all queued shared choices',async()=>{
  const h=harness(),s=h.slow(),m=h.menu(),pending=[h.situ(),h.card(m)];let finished=false;
  const finishing=h.run('finishReviewWrites()').then(()=>{finished=true;});
  await tick();assert.equal(finished,false);s.gate.resolve();await Promise.all([...pending,finishing]);
  assert.equal(finished,true);assert.equal(s.bodies.at(-1).version,1);
  assert.equal(h.run('pendingReviewWrites().length'),0);
});
