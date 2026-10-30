const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),test=require('node:test');
function harness(){
 const nodes=new Map();
 const node=s=>{if(!nodes.has(s))nodes.set(s,{innerHTML:'',textContent:'',open:false,scrollTop:0,value:'',
   querySelector:()=>null,querySelectorAll:()=>[],addEventListener(){},showModal(){this.open=true;},close(){this.open=false;},classList:{toggle(){}}});return nodes.get(s);};
 const c=vm.createContext({console,URL,URLSearchParams,document:{querySelector:node,querySelectorAll:()=>[],addEventListener(){}},
   window:{addEventListener(){}},setTimeout(){},clearTimeout(){},setInterval(){},clearInterval(){}});
 const run=s=>vm.runInContext(s,c);
 for(const file of ['app.js','image-tools.js','specifications.js','component-overview.js'])run(fs.readFileSync(path.join(__dirname,'../static',file),'utf8').replace(/\nboot\(\);\s*$/,'\n'));
 run("state.boot={products:[],image_types:{product:'Product',in_situ:'In situ'}};state.pid='other';state.current={images:[]};scheduleCoverageRefresh=()=>{};refreshNativeView=async()=>true;let nativeViewNeedsRefresh=false;");
 const image={id:'id:one',name:'one.jpg',selected_uses:['listing','advertising'],effective_types:['product'],withheld_reasons:[],
   content_hash:'original-hash',asset_review:{kind:'asset',product_id:'',item_id:'id:one',version:3,member_versions:{'id:one':3},data:{types:['product'],tags:['garden'],rights:'owned',notes:'retain'}},
   component_choice:{product_id:'A',shown:true,listing:true,advertising:true,primary:true,image_version:4,assignment_version:2,image_member_versions:{'id:one':4},assignment_member_versions:{'id:one':2}}};
 const payload={product:{id:'A',name:'Panel',family:'Panels',fields:[],listing_fields:[]},images:[image],related_images:[],in_situ_ids:[],listing_ids:['id:one'],primary_id:'id:one'};
 c.payload=payload;run('overviewPayload=payload;');node('#component-overview-dialog').open=true;
 const button=action=>({dataset:{overviewAsset:'id:one',overviewAction:action},getBoundingClientRect:()=>({top:100}),closest:()=>({id:'overview-associated'})});
 const save=action=>{c.button=button(action);return run('changeOverviewImage(button)');};
 return {c,run,node,image,payload,save};
}
test('overview exposes independent purpose, primary, association and shared type controls',()=>{
 const h=harness(),html=h.run('overviewControls(payload.images[0])');
 for(const role of ['shown','listing','advertising','in_situ','primary'])assert(html.includes('data-overview-action="'+role+'"'));
 assert(html.includes('aria-pressed="true"'));assert(html.includes('id:one'));
});
test('turning Listing off also clears Primary while preserving Ads and review versions',async()=>{
 const h=harness();let body;h.c.api=async(url,b)=>b?(body=b,{}):h.payload;
 await h.save('listing');const r=body.rows[0];assert.equal(r.listing,false);assert.equal(r.primary,false);assert.equal(r.advertising,true);
 assert.equal(r.image_version,4);assert.equal(body.content_hash,'original-hash');assert.equal(r.product_id,'A');
});
test('Primary on a related candidate also associates and selects Listing',async()=>{
 const h=harness();Object.assign(h.image.component_choice,{shown:false,listing:false,advertising:false,primary:false});
 let body;h.c.api=async(url,b)=>b?(body=b,{}):h.payload;await h.save('primary');
 assert.equal(body.rows[0].shown,true);assert.equal(body.rows[0].listing,true);assert.equal(body.rows[0].primary,true);
});
test('associated off clears component uses without changing shared types',async()=>{
 const h=harness();let body,url;h.c.api=async(u,b)=>b?(url=u,body=b,{}):h.payload;
 await h.save('shown');assert.equal(url,'/api/image-components');
 for(const k of ['shown','listing','advertising','primary'])assert.equal(body.rows[0][k],false);
 assert.deepEqual(h.image.effective_types,['product']);
});
test('In situ preserves other types, metadata, versions and binds the displayed bytes',async()=>{
 const h=harness();let body;h.c.api=async(url,b)=>b?(body=b,{...h.image.asset_review,version:4,data:b.data}):h.payload;
 await h.save('in_situ');assert.equal(body.kind,'asset');assert.equal(body.version,3);assert.equal(body.expected_content_hash,'original-hash');
 assert.deepEqual(Array.from(body.data.types),['product','in_situ']);assert.deepEqual(Array.from(body.data.tags),['garden']);assert.equal(body.data.notes,'retain');
 assert.equal(body.data.rights,'owned');assert.equal(body.product_id,'');
});
test('rapid duplicate clicks submit one action and closing never reopens the preview',async()=>{
 const h=harness();let release,calls=0;h.c.api=async()=>{calls++;return new Promise(r=>release=r);};
 const pending=h.save('listing');await h.save('listing');assert.equal(calls,1);
 h.run('closeComponentOverview()');h.node('#component-overview-content').innerHTML='Closed';release({});await pending;
 assert.equal(calls,1);assert.equal(h.node('#component-overview-dialog').open,false);assert.equal(h.node('#component-overview-content').innerHTML,'Closed');
});
test('saving for one component cannot replace a newer component preview',async()=>{
 const h=harness();let release;h.c.api=async()=>new Promise(r=>release=r);
 const pending=h.save('advertising');h.run("overviewRequest++;overviewPayload={product:{id:'B'}}");h.node('#component-overview-content').innerHTML='New component';
 release({});await pending;assert.equal(h.node('#component-overview-content').innerHTML,'New component');
});
test('failed save keeps displayed choices and tells user it was not saved',async()=>{
 const h=harness();h.c.api=async()=>{throw Error('Stale review version');};await h.save('listing');
 assert.equal(h.image.component_choice.listing,true);assert.match(h.node('#overview-save-status').textContent,/Not saved: Stale review version/);
 assert.equal(h.run('overviewSaving'),false);
});
test('unsaved detail edits block an overview mutation without discarding the draft',async()=>{
 const h=harness();let called=false;h.c.api=async()=>{called=true;};h.run("state.dirty.add('image-form')");await h.save('listing');
 assert.equal(called,false);assert(h.run("state.dirty.has('image-form')"));
});
test('gallery badges show multiple roles and exclude pending primary choices',()=>{
 const h=harness();h.run("state.pid='A';state.reviews.set(key('image','A','id:one'),{data:{decision:'reviewed',uses:['listing','advertising'],primary:true}})");
 h.c.image={id:'id:one',types:['product','in_situ']};let html=h.run('imageRoleBadges(image)');
 for(const k of ['primary','listing','advertising','in_situ','product'])assert(html.includes('role-'+k));
 h.run("state.reviews.set(key('image','A','id:one'),{data:{decision:'pending',uses:['listing'],primary:true}})");
 html=h.run('imageRoleBadges(image)');assert(!html.includes('role-primary'));assert(html.includes('role-in_situ'));
});
