const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test');
function harness(){
  const nodes=new Map(),listeners={},timers=[];
  const node=s=>{if(!nodes.has(s))nodes.set(s,{innerHTML:'',textContent:'',open:true,valid:true,checkValidity(){return this.valid;},reportValidity(){return this.valid;},close(){this.open=false;},showModal(){this.open=true;},setAttribute(){}});return nodes.get(s);};
  const context=vm.createContext({Number,JSON,Date,setTimeout:f=>(timers.push(f),timers.length),clearTimeout:()=>{},
    FormData:class{constructor(form){this.values=form.values;}get(k){return this.values[k]??null;}has(k){return !!this.values[k];}},
    document:{addEventListener:(k,f)=>(listeners[k]||=[]).push(f)},window:{confirm:()=>false},$:node,
    esc:x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;'),safeURL:x=>x,
    formSnapshot:form=>JSON.stringify(form.values),state:{dirty:new Set()},toast:()=>{}});
  const run=s=>vm.runInContext(s,context);run(fs.readFileSync(path.join(__dirname,'../static/delivery.js'),'utf8'));
  node('#delivery-form').values={length_cm:'45',width_cm:'35',depth_cm:'16',weight_kg:'2',packaging_gbp:'0',collection:false,destination:'uk'};
  const tariff={verified_at:'2026-10-30T18:55:29Z',effective_date:'2026-10-05',collection_pence:50,compensation_gbp:75,tiers:[],source_url:'https://www.royalmail.com/sending/uk/tracked-48',guide_url:'https://www.royalmail.com/guide.pdf'};
  context.payload={product_id:'A',name:'Sculpture A',package:{version:0,data:{}},tariff,last_attempt:null};
  run("deliveryEditor={pid:'A',payload,quoteRequest:0,dirty:false,saving:false,baseline:formSnapshot($('#delivery-form'))};");
  const result={status:'calculated',rates:{needs_confirmation:false},tier:{label:'Small parcel up to 2 kg'},postage_pence:375,collection_pence:0,packaging_pence:0,total_pence:375};
  return {context,run,node,listeners,timers,result};
}

test('calculates the current form without saving a package or booking',async()=>{
  const h=harness(),calls=[];h.context.api=async(url,body)=>(calls.push({url,body}),h.result);
  await h.run('previewDelivery()');assert.match(h.node('#delivery-result').innerHTML,/£3.75/);
  assert.equal(calls.length,1);assert.equal(calls[0].url,'/api/delivery/quote');assert.equal(calls[0].body.data.weight_kg,2);
});
test('saved tariff quotes visibly require confirmation after a failed refresh',async()=>{
  const h=harness();h.result.rates.needs_confirmation=true;h.context.api=async()=>h.result;
  await h.run('previewDelivery()');assert.match(h.node('#delivery-result').innerHTML,/CONFIRM CURRENT RATE/);
  h.context.payload.last_attempt={status:'failed',at:'2026-10-30T19:00:00Z',message:'Royal Mail blocked the check (HTTP 403).'};
  h.run('renderDeliveryRates()');assert.match(h.node('#delivery-rates').innerHTML,/HTTP 403/);
});
test('invalid or incomplete measurements clear old quotes without requesting a rate',async()=>{
  const h=harness();h.node('#delivery-form').valid=false;h.context.api=()=>{throw new Error('must not call');};
  h.node('#delivery-result').innerHTML='£3.75';await h.run('previewDelivery()');
  assert(!h.node('#delivery-result').innerHTML.includes('£3.75'));
});
test('out-of-order quote responses cannot replace the latest price',async()=>{
  const h=harness();let resolve;
  h.context.api=(_url,body)=>body.data.weight_kg===2?new Promise(r=>resolve=r):Promise.resolve({...h.result,total_pence:755});
  const old=h.run('previewDelivery()');h.node('#delivery-form').values.weight_kg='3';await h.run('previewDelivery()');
  resolve(h.result);await old;assert.match(h.node('#delivery-result').innerHTML,/£7.55/);
});
test('typing immediately invalidates a pending quote before debounce fires',async()=>{
  const h=harness();let resolve;h.context.api=()=>new Promise(r=>resolve=r);
  const old=h.run('previewDelivery()');h.node('#delivery-form').values.weight_kg='3';
  for(const listener of h.listeners.input)listener({target:{closest:()=>h.node('#delivery-form')}});
  const html=h.node('#delivery-result').innerHTML;resolve(h.result);await old;
  assert.equal(h.node('#delivery-result').innerHTML,html);assert.equal(h.run('deliveryEditor.dirty'),true);
});
test('blur change after the same input does not replace a quote or move Save during its click',()=>{
  const h=harness();h.node('#delivery-form').values.packaging_gbp='3.5';
  const event={target:{closest:()=>h.node('#delivery-form')}};
  for(const listener of h.listeners.input)listener(event);
  const request=h.run('deliveryEditor.quoteRequest'),timers=h.timers.length;
  h.node('#delivery-result').textContent='£7.25 current quote';
  for(const listener of h.listeners.change)listener(event);
  assert.equal(h.run('deliveryEditor.quoteRequest'),request);
  assert.equal(h.timers.length,timers);
  assert.equal(h.node('#delivery-result').textContent,'£7.25 current quote');
});
test('older errors and closed dialogs cannot receive a stale response',async()=>{
  for(const action of ['deliveryEditor.quoteRequest++','deliveryEditor=null']){
    const h=harness();let reject;h.context.api=()=>new Promise((_r,j)=>reject=j);
    const old=h.run('previewDelivery()');h.run(action);const text=h.node('#delivery-result').textContent;
    reject(new Error('old error'));await old;assert.equal(h.node('#delivery-result').textContent,text);
  }
});
test('save preserves sculpture identity and expected version and clears dirty only on success',async()=>{
  const h=harness(),calls=[];h.run("deliveryEditor.dirty=true;state.dirty.add('delivery-editor');");
  h.context.api=async(url,body)=>{calls.push({url,body});return url==='/api/reviews'?{version:1,data:body.data,updated_at:'2026-10-30T19:00:00Z'}:h.result;};
  await h.run('saveDelivery()');assert.equal(calls[0].body.product_id,'A');assert.equal(calls[0].body.version,0);assert.equal(calls[0].body.kind,'delivery');
  assert.equal(h.run('deliveryEditor.payload.package.version'),1);assert.equal(h.run('deliveryEditor.dirty'),false);assert.equal(h.context.state.dirty.size,0);assert.equal(h.node('#delivery-form').inert,false);
});
test('conflicting saves keep entered inputs and dirty state for recovery',async()=>{
  const h=harness();h.run("deliveryEditor.dirty=true;state.dirty.add('delivery-editor');");
  h.context.api=async url=>{if(url==='/api/reviews')throw new Error('Changed in another tab');return h.result;};
  await h.run('saveDelivery()');assert.equal(h.run('deliveryEditor.dirty'),true);assert.equal(h.run('deliveryEditor.payload.package.version'),0);
  assert.match(h.node('#delivery-save-status').textContent,/another tab/);assert.equal(h.node('#delivery-form').inert,false);
});
test('closing during a rate refresh does not reopen or update the dialog',async()=>{
  const h=harness();let resolve;h.context.api=()=>new Promise(r=>resolve=r);
  const pending=h.run('refreshDelivery(false)');h.run('closeDelivery()');const html=h.node('#delivery-rates').innerHTML;
  resolve({tariff:h.context.payload.tariff,last_attempt:{status:'ok'}});await pending;
  assert.equal(h.node('#delivery-dialog').open,false);assert.equal(h.node('#delivery-rates').innerHTML,html);
});
test('close honours unsaved package edits and stays open during save',()=>{
  const h=harness();h.run('deliveryEditor.dirty=true;closeDelivery()');assert.equal(h.node('#delivery-dialog').open,true);
  h.context.window.confirm=()=>true;h.run('deliveryEditor.saving=true;closeDelivery()');assert.equal(h.node('#delivery-dialog').open,true);
  h.run('deliveryEditor.saving=false;closeDelivery()');assert.equal(h.node('#delivery-dialog').open,false);
});
test('rapid opens bind only the latest sculpture and retain no previous pending result',async()=>{
  const h=harness(),renders=[];let resolve;
  h.run('renderDelivery=()=>renders.push(deliveryEditor.pid);previewDelivery=()=>{};refreshDelivery=()=>{};');h.context.renders=renders;
  h.context.api=url=>url.endsWith('=A')?new Promise(r=>resolve=r):Promise.resolve({...h.context.payload,product_id:'B'});
  const old=h.run("openDelivery('A')");await h.run("openDelivery('B')");resolve(h.context.payload);await old;
  assert.deepEqual(renders,['B']);assert.equal(h.run('deliveryEditor.pid'),'B');
});
test('edited package measurements hide the previous USA estimate until saved',()=>{
  const h=harness();h.context.payload.us_shipping={status:'available',packing_basis:'Saved packed measurements',packed_cm:[45,35,16],packed_kg:2,quotes:[]};
  h.run('renderUSDelivery()');assert.match(h.node('#us-delivery-estimates').innerHTML,/2 kg packed/);
  h.node('#delivery-form').values.weight_kg='8';
  for(const listener of h.listeners.input)listener({target:{closest:()=>h.node('#delivery-form')}});
  assert(!h.node('#us-delivery-estimates').innerHTML.includes('2 kg packed'));
  assert.match(h.node('#us-delivery-estimates').innerHTML,/Save.*refresh/i);
  h.node('#delivery-form').values.weight_kg='2';
  for(const listener of h.listeners.input)listener({target:{closest:()=>h.node('#delivery-form')}});
  assert.match(h.node('#us-delivery-estimates').innerHTML,/2 kg packed/);
});
test('failed USA refresh after saving does not retain a quote for the previous package',async()=>{
  const h=harness();h.context.payload.us_shipping={status:'available',packing_basis:'Saved packed measurements',packed_cm:[45,35,16],packed_kg:2,quotes:[]};
  h.run('renderUSDelivery()');h.node('#delivery-form').values.weight_kg='8';
  h.context.api=async(url,body)=>{if(url==='/api/reviews')return {version:1,data:body.data,updated_at:'2026-11-09T09:00:00Z'};throw Error('Refresh unavailable');};
  await h.run('saveDelivery()');
  assert(!h.node('#us-delivery-estimates').innerHTML.includes('2 kg packed'));
  assert.match(h.node('#delivery-save-status').textContent,/saved.*could not refresh/i);
});
