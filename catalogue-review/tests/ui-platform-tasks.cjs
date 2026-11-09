const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test');
function harness(){
 const nodes=new Map(),listeners={};
 const node=s=>{if(!nodes.has(s))nodes.set(s,{innerHTML:'',textContent:'',value:'',scrollTop:0,disabled:false,classList:{toggle(){}},addEventListener(){},insertAdjacentHTML(_,html){this.innerHTML+=html;}});return nodes.get(s);};
 const context=vm.createContext({console,URL,URLSearchParams,FormData:class{entries(){return [];}},
  document:{querySelector:node,querySelectorAll:()=>[],getElementById:id=>nodes.get('#'+id),addEventListener:(type,fn)=>(listeners[type]||=[]).push(fn)},
  window:{addEventListener(){},confirm:()=>false,scrollY:0,scrollTo(){}},location:{hash:''},history:{replaceState:(_,__,hash)=>{context.location.hash=hash;}},localStorage:{getItem:()=>null,setItem(){}},setTimeout(){},clearTimeout(){},setInterval(){},clearInterval(){}});
 const run=s=>vm.runInContext(s,context),base=path.resolve(__dirname,'../static');
 for(const file of ['app.js','image-tools.js','specifications.js','platform-tasks.js','component-overview.js'])run(fs.readFileSync(path.join(base,file),'utf8').replace(/\nboot\(\);\s*$/,'\n'));
 run("state.boot={products:[],families:[],image_types:{}};state.pid='__specifications__';state.request=1;state.tab='specs';initSpecificationFilters();");
 return {context,run,node,listeners};
}
const entry=(id,tasks)=>({id,label:id==='pinterest'?'Pinterest':'Google Manufacturer',state:'action',open_count:tasks.length,checked_at:'2026-11-08T17:00:00Z',tasks});
const imageTask={id:'primary_image_size',state:'action',title:'Review primary image resolution',detail:'2048 × 1360 pixels; review a genuine higher-resolution selected photograph',scope:'photos',url:'https://www.pinterest.com/business/catalogs/'};
const wait={id:'merchant_approval',state:'waiting',title:'Merchant approval',detail:'Pinterest has not approved the merchant.'};
const product=(id,small)=>({id,name:'Panel '+id,number:1,family:'Panels',listing_decision:'include',fields:[],listing_fields:[],missing_count:0,omitted_count:0,platform_tasks:{open_count:small?2:1,platforms:[entry('pinterest',small?[imageTask,wait]:[wait])]}});
function seed(h){h.context.payload={products:[product('A',true),product('B',false)],families:['Panels'],totals:{products:2,fields:0,missing:0,omitted:0},platform_task_summary:{platforms:[{id:'pinterest',label:'Pinterest'}]}};h.run('state.specifications=payload;');}
test('each component shows platform badges, and task details are rendered only when opened',()=>{
 const h=harness();seed(h);const card=h.run('specificationCard(payload.products[0])');
 assert.match(card,/Pinterest/);assert.match(card,/data-platform-product="A"/);assert(!card.includes('2048 × 1360'));
 const details=h.run('platformTaskContent(payload.products[0].platform_tasks)');assert.match(details,/2048 × 1360/);assert.match(details,/Merchant approval/);
});
test('the platform and exact task filters isolate only products requiring that task',()=>{
 const h=harness();seed(h);h.run("state.specPlatform='pinterest';state.specTask='primary_image_size';");
 assert.equal(h.run('JSON.stringify(filteredSpecifications().map(p=>p.id))'),'["A"]');
 h.run("state.specTask='merchant_approval';");assert.equal(h.run('filteredSpecifications().length'),2);
 h.run("state.specTask='not_a_task';");assert.equal(h.run('filteredSpecifications().length'),0);
});
test('task filters survive a copied specification URL and clearing restores all products',()=>{
 const h=harness();seed(h);h.run("state.specPlatform='pinterest';state.specTask='primary_image_size';specificationRoute();");
 assert.equal(h.run('routeState().specPlatform'),'pinterest');assert.equal(h.run('routeState().specTask'),'primary_image_size');
 h.run('initSpecificationFilters();');assert.equal(h.run('filteredSpecifications().length'),2);
});
test('platform names task text and action URLs cannot inject markup or script links',()=>{
 const h=harness();seed(h);h.run("payload.products[0].platform_tasks.platforms[0].label='<img src=x>';payload.products[0].platform_tasks.platforms[0].tasks[0]={id:'bad',state:'action',title:'<script>bad()</script>',detail:'<img onerror=bad()>',url:'javascript:bad()'};");
 const markup=h.run('platformTaskContent(payload.products[0].platform_tasks)');assert(!markup.includes('<script>'));assert(!markup.includes('javascript:'));assert.match(markup,/&lt;script/);
});
test('component at a glance includes the same per-platform checklist',()=>{
 const h=harness();seed(h);h.context.modal={product:h.context.payload.products[0],images:[],related_images:[],in_situ_ids:[],listing_ids:[]};
 const html=h.run('renderComponentOverview(modal)');assert.match(html,/data-platform-context="overview"/);assert.match(html,/Pinterest/);
});
