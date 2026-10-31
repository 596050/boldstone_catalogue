const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test');
function harness(){
  const nodes=new Map(),listeners={};
  const node=s=>{if(!nodes.has(s))nodes.set(s,{innerHTML:'',textContent:'',open:true,querySelector:()=>null});return nodes.get(s);};
  const context=vm.createContext({console,Number,JSON,FormData:class{
    constructor(form){this.values=form.values||{};}get(k){return this.values[k]??null;}getAll(k){const v=this.values[k];return Array.isArray(v)?v:[];}
  },document:{addEventListener:(k,f)=>(listeners[k]||=[]).push(f)},window:{confirm:()=>false},
    $:node,$$:()=>[],esc:x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;'),
    safeURL:s=>s,formSnapshot:()=>'',state:{dirty:new Set(),writeEpoch:0},reviewRequests:new Set(),toast:()=>{}});
  const run=s=>vm.runInContext(s,context);
  run(fs.readFileSync(path.join(__dirname,'../static/costs.js'),'utf8'));
  const config={default_pricing_mode:'markup',default_markup_percent:100,materials:{gfrc:{label:'GFRC'}},finishes:{white:{label:'White'}},notes:''};
  const cost={status:'calculated',total_cost:38.33,material_label:'GFRC',finish_lines:[],inputs:{fixing_count:1,pricing_mode:'default',markup_percent:null},labour_hours:1,pricing:{mode:'markup',markup_percent:100,listing_value:'£76.66',fixed_value:'£250'}};
  context.cost=cost;context.config=config;
  run("costEditor={pid:'A',rates:{settings:config,version:3},product:{costing:{version:4}},saving:false};");
  return {context,run,node,listeners,cost,config};
}

function materialEditor(h){
  const form=h.node('#cost-form');
  form.values={pricing_mode:'default',markup_percent:'',width_cm:'120',height_cm:'60',depth_cm:'6',shape_factor:'1',casting_factor:'1',material:'gfrc',fixing_count:'2',labour_hours_override:'',other_cost:'0',notes:'',finish:['white']};
  form.querySelector=()=>({value:'1'});
  h.config.materials.jesmonite={label:'Jesmonite AC730'};
  const change=material=>{
    form.values.material=material;
    return Promise.all(h.listeners.change.map(listener=>listener({type:'change',target:{name:'material',closest:()=>form}})));
  };
  const result=material=>({...h.cost,total_cost:material==='jesmonite'?321.57:112.87,
    material_label:material==='jesmonite'?'Jesmonite AC730':'GFRC',inputs:{...h.cost.inputs,fixing_count:2},
    pricing:{...h.cost.pricing,listing_value:material==='jesmonite'?'£643.14':'£225.74'}});
  return {form,change,result};
}

test('switching Large Ammonite material updates cost and markup preview without saving',async()=>{
  const h=harness(),e=materialEditor(h),calls=[];
  h.context.api=async(url,body)=>{calls.push({url,body});return e.result(body.data.material);};
  await e.change('jesmonite');
  assert.match(h.node('#cost-result').innerHTML,/Manufacturing cost <strong>£321.57/);
  assert.match(h.node('#cost-result').innerHTML,/Selling price £643.14/);
  assert.match(h.node('#cost-result').innerHTML,/Jesmonite AC730/);
  await e.change('gfrc');
  assert.match(h.node('#cost-result').innerHTML,/Manufacturing cost <strong>£112.87/);
  assert.match(h.node('#cost-result').innerHTML,/Selling price £225.74/);
  assert.deepEqual(calls.map(c=>c.body.data.material),['jesmonite','gfrc']);
  assert(calls.every(c=>c.url==='/api/costs/preview'&&c.body.product_id==='A'&&c.body.settings_version===3));
  assert.match(h.node('#cost-status').textContent,/Save to keep/);
  assert.equal(h.run('costEditor.dirty'),true);
  assert.equal(h.run('costEditor.product.costing.version'),4);
});

test('an older material preview failure cannot overwrite a newer successful preview',async()=>{
  const h=harness(),e=materialEditor(h);let reject;
  h.context.api=(_url,body)=>body.data.material==='jesmonite'?new Promise((_resolve,r)=>reject=r):Promise.resolve(e.result('gfrc'));
  const old=e.change('jesmonite');await e.change('gfrc');
  const status=h.node('#cost-status').textContent;
  reject(new Error('Earlier preview failed'));await old;
  assert.equal(h.node('#cost-status').textContent,status);
  assert.match(h.node('#cost-result').innerHTML,/£112.87/);
});

test('a preview cannot replace the result after its editor closes or starts saving',async()=>{
  for(const update of ['costEditor=null','costEditor.saving=true']){
    const h=harness(),e=materialEditor(h);let resolve;
    h.context.api=()=>new Promise(r=>resolve=r);
    const pending=e.change('jesmonite');h.run(update);
    resolve(e.result('jesmonite'));await pending;
    assert.equal(h.node('#cost-result').innerHTML,'');
  }
});

test('pricing summary shows markup on total cost including labour',()=>{
  const h=harness(),html=h.run('costPricingSummary(cost)');
  assert.match(html,/Selling price £76.66/);assert.match(html,/100% markup on £38.33, including labour/);
});
test('fixed pricing and omitted prices remain distinct',()=>{
  const h=harness();h.cost.pricing.mode='fixed';
  assert.match(h.run('costPricingSummary(cost)'),/Fixed price/);
  h.cost.pricing.price_omitted=true;
  const html=h.run('costPricingSummary(cost)');assert.match(html,/omitted/);assert(!html.includes('£76.66'));
});
test('controls distinguish shared method and individual override with a 100 percent default',()=>{
  const h=harness(),html=h.run('costPricingControls(cost,config)');
  assert.match(html,/value="default" selected/);assert.match(html,/blank uses 100%/);
  assert.match(html,/value="markup"/);assert.match(html,/value="fixed"/);
  assert.match(html,/Retained fixed price: <strong>£250/);
});
test('zero markup is retained and clearing an override restores inheritance',()=>{
  const h=harness(),form=h.node('#cost-form');
  form.values={pricing_mode:'markup',markup_percent:'0',width_cm:'20',height_cm:'35',depth_cm:'6',shape_factor:'1',casting_factor:'1',material:'gfrc',fixing_count:'1',labour_hours_override:'',other_cost:'0',notes:'',finish:['white']};
  form.querySelector=()=>({value:'1'});
  assert.equal(h.run('costFormData().markup_percent'),0);
  form.values.markup_percent='';assert.equal(h.run('costFormData().markup_percent'),null);
  assert.equal(h.run('costFormData().pricing_mode'),'markup');
});
test('populated markup and labour overrides can be cleared',()=>{
  const h=harness();
  assert(!h.run("costNumber('Markup','markup_percent',100,0,'any',true)").includes(' required'));
  assert(!h.run("costNumber('Labour','labour_hours_override',2,0,'any',true)").includes(' required'));
  assert(h.run("costNumber('Width','width_cm',20,.01)").includes(' required'));
});
test('a stale preview cannot replace inputs edited while it was calculating',async()=>{
  const h=harness();let resolve;
  h.run("costFormData=()=>({markup_percent:100});");h.context.api=()=>new Promise(r=>resolve=r);
  const pending=h.run('previewCosts()');h.run("costFormData=()=>({markup_percent:150});");
  resolve(h.cost);await pending;assert.equal(h.node('#cost-result').innerHTML,'');
});
test('preview carries the opening sculpture and shared-rate version without saving',async()=>{
  const h=harness(),calls=[];h.run("costFormData=()=>({markup_percent:100});");
  h.context.api=async(url,body)=>{calls.push({url,body});return h.cost;};
  await h.run('previewCosts()');assert.equal(calls.length,1);assert.equal(calls[0].url,'/api/costs/preview');
  assert.equal(calls[0].body.product_id,'A');assert.equal(calls[0].body.settings_version,3);
  assert.match(h.node('#cost-status').textContent,/Save to keep/);
});
test('markup price card shows the calculated price and preserves the fixed source separately',()=>{
  const h=harness(),source=fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
  const fn=source.slice(source.indexOf('function fieldHTML('),source.indexOf('function renderSpecs('));
  h.run(fn);h.run("review=()=>({version:1,data:{decision:'edit',value:'£250'}});state.pid='A';state.current={costing:cost};");
  h.context.field={key:'Price',label:'Individual price',value:'£200',basis:'Source',qualification:''};
  const html=h.run('fieldHTML(field)');
  assert.match(html,/£76.66/);assert.match(html,/Retained fixed price: £250/);assert.match(html,/Pricing options/);
  assert(!html.includes('spec-form'));
});
test('shared pricing refreshes the current sculpture without changing gallery selection or filters',async()=>{
  const h=harness(),rendered=[];
  h.context.state.current={id:'A',costing:{}};h.context.state.pid='A';h.context.state.request=3;h.context.state.tab='specs';
  h.context.state.selected=new Set(['photo']);h.context.state.role='in_situ';
  h.context.api=async()=>({costing:h.cost});h.context.renderSpecs=x=>rendered.push(x);
  await h.run("refreshCostViews('')");
  assert.equal(h.context.state.current.costing,h.cost);assert.deepEqual(rendered,[false]);
  assert.deepEqual([...h.context.state.selected],['photo']);assert.equal(h.context.state.role,'in_situ');
});
test('cost refresh preserves unsaved specifications and cannot overwrite a later navigation',async()=>{
  const h=harness(),rendered=[];
  h.context.state.current={id:'A',costing:{}};h.context.state.pid='A';h.context.state.request=3;h.context.state.tab='specs';
  h.context.state.dirty.add('field:Dimensions');h.context.renderSpecs=x=>rendered.push(x);
  h.context.api=async()=>({costing:h.cost});await h.run("refreshCostViews('A')");
  assert.equal(h.context.state.current.costing,h.cost);assert.deepEqual(rendered,[]);
  let resolve;h.context.api=()=>new Promise(r=>resolve=r);
  const pending=h.run("refreshCostViews('A')");
  const next={id:'B',costing:{sentinel:true}};h.context.state.current=next;h.context.state.pid='B';h.context.state.request++;
  resolve({costing:h.cost});await pending;assert.equal(h.context.state.current,next);assert.equal(next.costing.sentinel,true);
});
