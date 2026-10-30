const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test');
function harness(){
  const nodes=new Map(),listeners={};
  const node=s=>{if(!nodes.has(s))nodes.set(s,{innerHTML:'',textContent:'',value:'',scrollTop:0,disabled:false,classList:{toggle(){}},addEventListener(){}});return nodes.get(s);};
  const context=vm.createContext({console,URL,URLSearchParams,FormData:class{entries(){return [];}},
    document:{querySelector:node,querySelectorAll:()=>[],getElementById:id=>nodes.get('#'+id),addEventListener:(type,fn)=>(listeners[type]||=[]).push(fn)},
    window:{addEventListener:(type,fn)=>(listeners[type]||=[]).push(fn),confirm:()=>false,scrollY:0,scrollTo(){}},
    location:{hash:''},history:{replaceState:(_,__,hash)=>{context.location.hash=hash;}},localStorage:{getItem:()=>null,setItem(){}},setTimeout(){},clearTimeout(){},setInterval(){},clearInterval(){}});
  const run=s=>vm.runInContext(s,context),base=path.resolve(__dirname,'../static');
  for(const file of ['app.js','image-tools.js','family-tools.js','sync-tools.js','jobs.js','specifications.js'])run(fs.readFileSync(path.join(base,file),'utf8').replace(/\nboot\(\);\s*$/,'\n'));
  run("state.boot={products:[{id:'A'},{id:'B'}],families:[],image_types:{}};state.pid='__specifications__';state.request=1;state.tab='specs';toast=()=>{};syncCanRefresh=()=>true;initImageSort=()=>{};renderList=()=>{};renderProductCoverage=()=>{};");
  return {context,run,node,listeners};
}
const field=(value,decision='edit')=>({key:'Weight',label:'Weight',value,source_value:'4 kg - original',section:'Specifications',decision,version:1});
const product=(id,name,family,value,decision='pending')=>({id,name,original_name:name,number:1,family,listing_decision:decision,fields:[field(value)],listing_fields:[],missing_count:value===''?1:0,omitted_count:value===null?1:0});
const payload=()=>({products:[product('A','Moon White','Moon','6 kg'),product('B','Palm Bronze','Palm','', 'exclude'),product('C','Moon Gold','Moon',null,'include')],families:['Moon','Palm'],totals:{products:3,fields:3,missing:1,omitted:1},revision:'1',checked_at:'2026-10-27T13:00:00Z'});
function seed(h){h.context.payload=payload();h.run('state.specifications=payload;initSpecificationFilters();');}

test('overview keeps every component and distinguishes missing and omitted fields',()=>{
  const h=harness();seed(h);h.run('renderAllSpecifications();');
  assert.match(h.node('#specification-results').innerHTML,/Moon White/);assert.match(h.node('#specification-results').innerHTML,/Palm Bronze/);
  assert.match(h.node('#specification-results').innerHTML,/Not provided/);assert.match(h.node('#specification-results').innerHTML,/Omitted from listing/);
  assert.equal(h.node('#spec-result-count').textContent,'3 of 3 components shown');
});
test('combined name value family listing and missing filters select exact components',()=>{
  const h=harness();seed(h);h.run("state.specSearch='moon 6';state.specFamily='Moon';state.specListing='pending';");
  assert.equal(h.run('JSON.stringify(filteredSpecifications().map(p=>p.id))'),'["A"]');
  h.run("initSpecificationFilters({specDetails:'missing',specListing:'exclude'});");
  assert.equal(h.run('JSON.stringify(filteredSpecifications().map(p=>p.id))'),'["B"]');
  h.run("initSpecificationFilters({specDetails:'omitted'});");assert.equal(h.run('JSON.stringify(filteredSpecifications().map(p=>p.id))'),'["C"]');
});
test('specification content is escaped and source links reject unsafe protocols',()=>{
  const h=harness();seed(h);h.run("payload.products[0].name='<img src=x>';payload.products[0].fields[0].value='<script>bad</script>';payload.products[0].folder_url='javascript:bad()';");
  const html=h.run('specificationCard(payload.products[0])');assert(!html.includes('<script>'));assert(!html.includes('javascript:'));assert.match(html,/&lt;img/);assert.match(html,/#A\?tab=specs/);
});
test('overview filters and specification edit routes survive URL parsing',()=>{
  const h=harness();seed(h);h.run("state.specSearch='white & gold';state.specFamily='Moon';state.specDetails='missing';specificationRoute();");
  assert.equal(h.run('routeState().pid'),'__specifications__');assert.equal(h.run('routeState().specSearch'),'white & gold');
  h.run("location.hash='#A?tab=specs';");assert.equal(h.run('routeState().tab'),'specs');
});
test('loading overview uses one overview request and no product or image requests',async()=>{
  const h=harness(),calls=[];h.context.api=async url=>{calls.push(url);return payload();};h.context.renderAllSpecifications=()=>{};
  await h.run("load('__specifications__',{specFamily:'Moon'})");assert.deepEqual(calls,['/api/specifications']);assert.equal(h.run('state.specFamily'),'Moon');assert.equal(h.run('state.tab'),'specs');
});
test('a late overview response cannot replace a different sculpture',async()=>{
  const h=harness();seed(h);let release;h.context.api=async()=>new Promise(r=>{release=r;});
  const pending=h.run('refreshAllSpecifications(true)');h.run("state.pid='B';state.request++;");release({...payload(),revision:'2'});await pending;
  assert.equal(h.run('state.specifications.revision'),'1');assert.equal(h.node('#specification-results').innerHTML,'');
});
test('refresh preserves filters and renders newly saved details',async()=>{
  const h=harness();seed(h);h.run("state.specFamily='Moon';");const fresh=payload();fresh.revision='2';fresh.products[0].fields[0].value='9 kg';
  h.context.api=async()=>fresh;await h.run('refreshAllSpecifications(true)');
  assert.match(h.node('#specification-results').innerHTML,/9 kg/);assert(!h.node('#specification-results').innerHTML.includes('Palm Bronze'));
  assert.equal(h.run('state.specFamily'),'Moon');assert.equal(h.node('#spec-refresh').disabled,false);
});
test('failed refresh retains last details and visibly marks them stale',async()=>{
  const h=harness();seed(h);h.context.api=async()=>{throw Error('Network failed');};await h.run('refreshAllSpecifications(true)');
  assert.equal(h.run('state.specifications.revision'),'1');assert.match(h.node('#spec-checked').textContent,/last loaded/);assert.equal(h.node('#spec-refresh').disabled,false);
});
test('a local write invalidates an overlapping overview refresh',async()=>{
  const h=harness();seed(h);let release;h.context.api=async()=>new Promise(r=>{release=r;});
  const pending=h.run('refreshAllSpecifications(true)');h.run('state.writeEpoch++;');release({...payload(),revision:'2'});await pending;assert.equal(h.run('state.specifications.revision'),'1');
});
test('Next sculpture preserves specification or listing review tab',async()=>{
  const h=harness();h.run("state.pid='A';state.tab='specs';");
  const target={id:'next-product',dataset:{}};await h.listeners.click[0]({target:{closest:s=>s==='.select-box'?null:target}});
  assert.equal(h.context.location.hash,'B?tab=specs');
});
test('discard cancellation restores the exact prior specification URL',()=>{
  const h=harness();h.run("state.pid='A';state.routeHash='#A?tab=specs&type=product';state.dirty.add('field-Weight');location.hash='#B';");
  h.listeners.hashchange[0]();assert.equal(h.context.location.hash,'#A?tab=specs&type=product');
});
for(const action of ['refreshNativeView()','refreshDropboxView({generation:2})'])test(action+' does not treat overview as a product',async()=>{
  const h=harness(),calls=[];seed(h);h.context.api=async url=>{calls.push(url);return {products:[],families:[],assignments:[],dropbox_sync:{generation:2}};};
  await h.run(action);assert.deepEqual(calls,['/api/bootstrap']);assert.equal(h.run('state.specifications.revision'),'1');
});
const photoSummary=()=>({primary_listing:{status:'set',image_id:'photo'},listing:{count:8,images:[{id:'photo',name:'Selected.jpg',local_preview:true,original:{dropbox_content_hash:'abc'},withheld_reasons:[]}]},in_situ:{count:1,target:2,missing:1,images:[{id:'scene',name:'Scene.jpg',local_preview:true,original:{dropbox_content_hash:'def'},withheld_reasons:[]}]}});
test('component cards show separate listing and in-situ previews with primary and complete totals',()=>{
 const h=harness();seed(h);h.context.photos=photoSummary();h.run('payload.products[0].photos=photos');const html=h.run('specificationCard(payload.products[0])');
 for(const text of ['Listing photos','In-situ photos','Primary set','1/2 in situ','Selected.jpg','Scene.jpg','Showing 1 of 8','View all 8'])assert(html.includes(text),text);
 assert.match(html,/data-component-overview="A" data-overview-section="listing"/);assert.match(html,/loading="lazy"/);assert.match(html,/&amp;size=thumb/);
 assert.match(html,/preview-photo-label">Primary/);
});
test('empty preview sections remain explicit without promoting source images',()=>{
 const h=harness();seed(h);const photos=photoSummary();photos.primary_listing={status:'missing'};photos.listing={count:0,images:[]};photos.in_situ={count:0,missing:2,target:2,images:[]};h.context.photos=photos;h.run('payload.products[0].photos=photos');
 const html=h.run('specificationCard(payload.products[0])');assert(html.includes('Primary missing'));assert(html.includes('No photos selected for listing'));assert(html.includes('No qualifying in-situ photos assigned'));assert(!html.includes('component-preview-photo '));
});
test('photo-only refresh updates the cards while keeping filters and scroll position',async()=>{
 const h=harness();seed(h);h.run("state.specFamily='Moon';");const fresh=payload();fresh.revision='photo-revision';fresh.products[0].photos=photoSummary();h.context.api=async()=>fresh;
 await h.run('refreshAllSpecifications(true)');assert(h.node('#specification-results').innerHTML.includes('Selected.jpg'));assert.equal(h.run('state.specFamily'),'Moon');
});
test('thumbnail labels and image URLs escape hostile names and preserve preview hashes',()=>{
 const h=harness();seed(h);const photos=photoSummary();photos.listing.images[0].name='<img src=x onerror=bad()>"';h.context.photos=photos;h.run('payload.products[0].photos=photos');
 const html=h.run('componentPhotoPreviews(payload.products[0])');assert(!html.includes('<img src=x'));assert(html.includes('&lt;img'));assert(html.includes('v=abc'));
});
