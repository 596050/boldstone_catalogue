const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test');
const tick=()=>new Promise(setImmediate);
function harness(){
  const nodes=new Map(),listeners={},messages=[];
  const node=s=>{if(!nodes.has(s))nodes.set(s,{innerHTML:'',textContent:'',value:'',open:false,disabled:false,
    close(){this.open=false;},showModal(){this.open=true;},addEventListener(){},classList:{toggle(){}},querySelector:()=>null,querySelectorAll:()=>[]});return nodes.get(s);};
  function form(id,values,checkboxes=[]){
    const elements=Object.fromEntries(Object.entries(values).map(([name,value])=>[name,{name,value,disabled:false}]));
    const button={disabled:false},status={textContent:''};
    const f={id,elements,checkboxes,inert:false,setAttribute(){},removeAttribute(){},
      querySelector:s=>s==='button[type=submit]'?button:s==='.save-state'?status:null,
      querySelectorAll:s=>checkboxes.filter(x=>(s.includes('name=use')?x.name==='use':s.includes('name=image_type')?x.name==='image_type':true)&&(!s.includes(':checked')||x.checked))};
    nodes.set('#'+id,f);return f;
  }
  const uses=['listing','advertising','social','reference'].map(value=>({name:'use',value,checked:false}));
  const imageForm=form('image-form',{decision:'pending',order:'0',alt:'',caption:'',edit_notes:'',notes:''},uses);
  imageForm.elements.primary={name:'primary',type:'checkbox',checked:false};
  const assetForm=form('asset-form',{tags:'',collection:'',rights:'unknown',notes:''},[{name:'image_type',value:'product',checked:true}]);
  nodes.set('#image-decision',imageForm.elements.decision);
  const context=vm.createContext({console,URL,URLSearchParams,
    FormData:class{constructor(f){this.f=f;}entries(){return [
      ...Object.values(this.f.elements).filter(x=>x.type!=='checkbox').map(x=>[x.name,x.value]),
      ...Object.values(this.f.elements).filter(x=>x.type==='checkbox'&&x.checked).map(x=>[x.name,'on']),
      ...this.f.checkboxes.filter(x=>x.checked).map(x=>[x.name,x.value])];}},
    document:{querySelector:node,querySelectorAll:()=>[],addEventListener:(type,fn)=>(listeners[type]||=[]).push(fn)},
    window:{addEventListener:(type,fn)=>(listeners[type]||=[]).push(fn),confirm:()=>false},
    location:{hash:'#A'},history:{replaceState:(_,__,hash)=>{context.location.hash=hash;}},
    localStorage:{getItem:()=>null,setItem(){}},setTimeout(){},clearTimeout(){},setInterval(){},clearInterval(){}});
  const run=s=>vm.runInContext(s,context);
  for(const name of ['app.js','image-tools.js'])run(fs.readFileSync(path.join(__dirname,'../static',name),'utf8').replace(/\nboot\(\);\s*$/,'\n'));
  const image={id:'one',name:'one.jpg',source:'Dropbox',types:['product'],original:{dropbox_content_hash:'old-hash'},association:{tier:'accepted',qualifications:[]}};
  context.image=image;context.report=message=>messages.push(message);
  run(`state.pid='A';state.request=1;state.routeHash='#A';state.boot={products:[{id:'A'},{id:'B'}],families:[],image_types:{product:'Product',in_situ:'In situ'}};
    state.current={id:'A',name:'Original sculpture',images:[image]};toast=report;scheduleCoverageRefresh=()=>{};
    renderGrid=()=>{};renderList=()=>{};renderMain=()=>{};renderDeleteControl=()=>{};initImageSort=()=>{};`);
  context.api=async(url,body)=>body?{...body,version:1}:{id:'B',name:'Other sculpture',images:[image],reviews:[]};
  return {run,context,node,listeners,messages,image,imageForm,assetForm,uses,open:()=>run("openImage('one')")};
}

test('navigating with a clean image editor closes it before changing sculpture',async()=>{
  const h=harness();h.open();h.context.location.hash='#B';h.listeners.hashchange[0]();await tick();
  assert.equal(h.run('state.pid'),'B');assert.equal(h.node('#image-dialog').open,false);assert.equal(h.run('state.image'),null);
});

test('cancelled navigation retains the original image draft and exact route',async()=>{
  const h=harness();h.open();h.imageForm.elements.caption.value='Draft caption';h.run("markDirty(document.querySelector('#image-form'))");
  h.context.location.hash='#B';h.listeners.hashchange[0]();await tick();
  assert.equal(h.run('state.pid'),'A');assert.equal(h.node('#image-dialog').open,true);
  assert.equal(h.context.location.hash,'#A');assert.equal(h.imageForm.elements.caption.value,'Draft caption');
});

test('accepted navigation discards an image draft once and closes the editor',async()=>{
  const h=harness();let confirmations=0;h.context.window.confirm=()=>{confirmations++;return true;};
  h.open();h.imageForm.elements.caption.value='Draft caption';h.run("markDirty(document.querySelector('#image-form'))");
  h.context.location.hash='#B';h.listeners.hashchange[0]();await tick();
  assert.equal(confirmations,1);assert.equal(h.run('state.pid'),'B');assert.equal(h.node('#image-dialog').open,false);
  assert.equal(h.run('state.dirty.size'),0);
});

test('Back during an image save stays on its original sculpture until the save finishes',async()=>{
  const h=harness();h.open();let release;h.context.api=async()=>new Promise(resolve=>{release=resolve;});
  const saving=h.run("saveImageDetails('image-form')");
  h.context.location.hash='#B';h.listeners.hashchange[0]();await tick();
  assert.equal(h.run('state.pid'),'A');assert.equal(h.context.location.hash,'#A');
  assert.equal(h.node('#image-dialog').open,true);assert.match(h.messages.join(' '),/saving/i);
  release({kind:'image',product_id:'A',item_id:'one',version:1,data:{decision:'reviewed',uses:[]}});await saving;
  h.context.api=async()=>({id:'B',name:'Other sculpture',images:[],reviews:[]});
  h.context.location.hash='#B';h.listeners.hashchange[0]();await tick();assert.equal(h.run('state.pid'),'B');
});

test('image details save to their opening sculpture even if page state changes',async()=>{
  const h=harness(),bodies=[];h.open();h.run("state.pid='B'");
  h.context.api=async(url,body)=>{bodies.push(body);return {...body,version:1};};
  await h.run("saveImageDetails('image-form')");
  assert.equal(bodies[0].product_id,'A');assert.equal(bodies[0].item_id,'one');
});

for(const kind of ['image','asset'])test(kind+' saves bind the content hash of the displayed image',async()=>{
  const h=harness(),bodies=[];h.context.api=async(url,body)=>{bodies.push(body);return {...body,version:1};};
  await h.run(kind==='image'?"quick('one','listing')":"save('asset','','one',{types:['product','in_situ']})");
  assert.equal(bodies[0].expected_content_hash,'old-hash');
});

test('an unknown displayed hash cannot silently approve newly discovered bytes',async()=>{
  const h=harness(),bodies=[];delete h.image.original.dropbox_content_hash;
  h.context.api=async(url,body)=>{bodies.push(body);return {...body,version:1};};await h.run("quick('one','listing')");
  assert.equal(bodies[0].expected_content_hash,null);assert(Object.hasOwn(bodies[0],'expected_content_hash'));
});

test('an open editor retains the original hash if gallery data is replaced',async()=>{
  const h=harness(),bodies=[];h.open();h.image.original.dropbox_content_hash='new-hash';
  h.context.api=async(url,body)=>{bodies.push(body);return {...body,version:1};};await h.run("saveImageDetails('image-form')");
  assert.equal(bodies[0].expected_content_hash,'old-hash');
});

test('bulk choices keep the selected file hashes across navigation',async()=>{
  const h=harness(),bodies=[];let release;
  h.run("state.current.images.push({...image,id:'two',original:{dropbox_content_hash:'second-hash'}});state.selected=new Set(['one','two']);");
  h.context.api=async(url,body)=>{bodies.push(body);if(bodies.length===1)await new Promise(resolve=>release=resolve);return {...body,version:1};};
  const target={dataset:{bulk:'advertising'},disabled:false};
  const pending=h.listeners.click[0]({target:{closest:s=>s==='.select-box'?null:target}});
  h.run("state.pid='B';state.current={id:'B',images:[]};state.request++;");release();await pending;
  assert.deepEqual(bodies.map(b=>[b.product_id,b.item_id,b.expected_content_hash]),[['A','one','old-hash'],['A','two','second-hash']]);
});

test('primary refresh and shared tags use the same opening context',async()=>{
  const h=harness(),requests=[];h.open();h.imageForm.elements.primary.checked=true;
  h.assetForm.elements.tags.value='garden';
  h.context.api=async(url,body)=>{
    requests.push({url,body});h.run("state.pid='B';state.current={id:'B',images:[]};state.request++;");
    return body?{...body,version:1}:{reviews:[]};
  };
  await h.run("saveImageDetails('image-form')");
  assert.equal(requests[0].body.product_id,'A');assert.equal(requests[1].url,'/api/products/A');
  assert.equal(requests[2].body.item_id,'one');assert.equal(requests[2].body.expected_content_hash,'old-hash');
});

test('a rejected content change retains the editable draft and releases save controls',async()=>{
  const h=harness();h.open();h.imageForm.elements.caption.value='Draft for original image';
  h.run("markDirty(document.querySelector('#image-form'))");
  h.context.api=async()=>{throw new Error('This image changed. Reload its photos before saving.');};
  await assert.rejects(h.run("saveImageDetails('image-form')"),/image changed/);
  assert.equal(h.imageForm.elements.caption.value,'Draft for original image');
  assert.equal(h.run("state.dirty.has('image-form')"),true);assert.equal(h.run('state.savingImage'),false);
  assert.equal(h.imageForm.inert,false);assert.equal(h.assetForm.inert,false);assert.equal(h.node('#image-dialog').open,true);
});

test('partial saves retain unsaved shared tags and do not report all changes saved',async()=>{
  const h=harness();h.open();h.imageForm.elements.caption.value='Saved caption';h.assetForm.elements.tags.value='Unsaved tag';
  h.run("markDirty(document.querySelector('#image-form'));markDirty(document.querySelector('#asset-form'))");
  h.context.api=async(url,body)=>{if(body.kind==='asset')throw new Error('This image changed');return {...body,version:1};};
  await assert.rejects(h.run("saveImageDetails('image-form')"),/image changed/);
  assert.equal(h.run("state.dirty.has('image-form')"),false);assert.equal(h.run("state.dirty.has('asset-form')"),true);
  assert.equal(h.run("data('image','A','one').caption"),'Saved caption');assert.equal(h.assetForm.elements.tags.value,'Unsaved tag');
  assert.equal(h.messages.some(message=>message.includes('saved')),false);
});

test('transfer cannot open while an image save is still running',async()=>{
  const h=harness();h.open();h.run('state.savingImage=true');
  h.run("openTransfer(['one'])");
  assert.equal(h.node('#transfer-dialog').open,false);assert.equal(h.node('#image-dialog').open,true);
  assert.match(h.messages.join(' '),/saving/i);
});

test('double submission does not start another save and unload warns while saving',async()=>{
  const h=harness();h.open();let release,calls=0,warned=false;
  h.context.api=async(url,body)=>{calls++;await new Promise(resolve=>release=resolve);return {...body,version:1};};
  const pending=h.run("saveImageDetails('image-form')");await h.run("saveImageDetails('image-form')");
  h.listeners.beforeunload[0]({preventDefault:()=>warned=true});
  assert.equal(calls,1);assert.equal(warned,true);release();await pending;
});


test('library and component image editors both expose Listing and Primary component controls',()=>{
  const h=harness();h.open();assert.match(h.node('#image-detail').innerHTML,/data-components="one"/);
  assert.match(h.node('#image-detail').innerHTML,/Primary listing photograph/);
  h.run("state.pid='__library__';state.library={images:[image]}");h.open();
  assert.match(h.node('#image-detail').innerHTML,/Listing, Primary &amp; components/);
  assert.doesNotMatch(h.node('#image-detail').innerHTML,/Library use only/);
  assert.doesNotMatch(h.node('#image-detail').innerHTML,/<input name="primary"/);
});
