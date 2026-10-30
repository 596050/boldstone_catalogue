const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test');
function harness(){
 const nodes=new Map(),listeners={},messages=[];
 const node=s=>{if(!nodes.has(s))nodes.set(s,{innerHTML:'',textContent:'',value:'',open:false,disabled:false,
   addEventListener(){},showModal(){this.open=true;},close(){this.open=false;},setAttribute(){},removeAttribute(){},classList:{toggle(){}}});return nodes.get(s);};
 const context=vm.createContext({console,URL,URLSearchParams,FormData:class{},document:{querySelector:node,querySelectorAll:()=>[],addEventListener:(k,f)=>(listeners[k]||=[]).push(f)},window:{addEventListener(){},confirm:()=>true},location:{hash:'#A'},history:{replaceState(){}},localStorage:{getItem:()=>null,setItem(){}},setTimeout(){},clearTimeout(){},setInterval(){},clearInterval(){}});
 const run=s=>vm.runInContext(s,context);
 for(const file of ['app.js','image-tools.js','family-tools.js','component-tools.js','sort-tools.js'])run(fs.readFileSync(path.join(__dirname,'../static',file),'utf8').replace(/\nboot\(\);\s*$/,'\n'));
 context.report=message=>messages.push(message);
 run("state.pid='A';state.request=1;state.current={images:[]};state.boot={products:[],image_types:{},families:[]};toast=report;scheduleCoverageRefresh=()=>{};sortImages=x=>x;");
 return {run,context,node,listeners,messages};
}
const payload=(id='photo')=>({image:{id,name:id+'.jpg',family:'Panels',types:[]},content_hash:'hash',rows:[{product_id:'A',name:'Panel White',family:'Panels',shown:true,listing:false,advertising:false}]});
const defer=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};};
function pendingPhoto(h){h.run(`state.current.images=[{id:'photo',name:'draft.jpg',association:{tier:'related'},component_ids:[],types:[]}];state.reviews.set(key('image','A','photo'),{version:1,data:{decision:'pending',uses:['listing','advertising','social'],notes:'Keep note'}});`);}

test('draft listing stays in related candidates until reviewed',()=>{
 const h=harness();pendingPhoto(h);
 assert.equal(h.run('Boolean(matchScope(state.current.images[0]))'),false);
 h.run("state.scope='related'");assert(h.run('matchScope(state.current.images[0])'));
});
test('pending purposes do not light up Listing or Ads or create approved-use chips',()=>{
 const h=harness();pendingPhoto(h);
 const html=h.run('imageActions(state.current.images[0])');assert(!html.includes('aria-pressed="true"'));
 assert(!h.run("chips(state.current.images[0])").includes('chip good'));
});
test('Listing filter excludes saved Not reviewed drafts',()=>{
 const h=harness();pendingPhoto(h);h.run("state.scope='all';state.use='listing'");assert.equal(h.run('filteredImages().length'),0);
});
test('default ordering does not promote unreviewed draft purposes',()=>{
 const h=harness();pendingPhoto(h);
 assert.equal(h.run("defaultImageOrder([{id:'ordinary'},{id:'photo'}])[0].id"),'ordinary');
});
test('multi-sort treats pending purposes as unselected',()=>{
 const h=harness();pendingPhoto(h);
 assert.equal(h.run("sortValue(state.current.images[0],'listing')[0]"),2);
 assert.equal(h.run("sortValue(state.current.images[0],'purpose')"),'');
});
test('scope summary still reports the pending image as a related candidate',()=>{
 const h=harness();pendingPhoto(h);h.run('updateScopeSummary()');assert.match(h.node('#image-scope-summary').innerHTML,/1 related candidate/);
});
test('clicking Ads approves Ads only, not saved pending purposes',async()=>{
 const h=harness();pendingPhoto(h);let saved;h.context.save=async(k,p,id,v)=>{saved=v;};
 await h.run("quick('photo','advertising')");assert.equal(JSON.stringify(saved.uses),'["advertising"]');assert.equal(saved.notes,'Keep note');assert.equal(saved.decision,'reviewed');
});
test('toggling an already reviewed purpose preserves other approved uses',async()=>{
 const h=harness();pendingPhoto(h);h.run("data('image','A','photo').decision='reviewed'");let saved;h.context.save=async(k,p,id,v)=>{saved=v;};
 await h.run("quick('photo','advertising')");assert.equal(JSON.stringify(saved.uses),'["listing","social"]');
});
test('component loading opens immediately so it can be cancelled',async()=>{
 const h=harness(),d=defer();h.context.api=()=>d.promise;const p=h.run("openComponents('photo')");
 assert(h.node('#component-dialog').open);assert.match(h.node('#component-dialog').innerHTML,/Loading component choices/);
 h.run('closeComponents()');d.resolve(payload());await p;assert(!h.node('#component-dialog').open);
});
test('closing a component load prevents its late response reopening it',async()=>{
 const h=harness(),d=defer();h.context.api=()=>d.promise;const p=h.run("openComponents('photo')");
 h.run('closeComponents()');d.resolve(payload());await p;assert(!h.node('#component-dialog').open);assert.equal(h.run('componentReview'),null);
});
test('a new chooser can open after cancelling an earlier slow read',async()=>{
 const h=harness(),a=defer(),b=defer();let calls=0;h.context.api=()=>++calls===1?a.promise:b.promise;
 const old=h.run("openComponents('old')");h.run('closeComponents()');const current=h.run("openComponents('new')");assert.equal(calls,2);
 b.resolve(payload('new'));await current;a.resolve(payload('old'));await old;assert.equal(h.run('componentReview.image.id'),'new');
});
test('late errors from closed component requests stay out of the current page',async()=>{
 const h=harness(),d=defer();h.context.api=()=>d.promise;const p=h.run("openComponents('photo')");h.run('closeComponents()');
 d.reject(new Error('Old timeout'));await p;assert.equal(h.messages.length,0);assert(!h.node('#component-dialog').open);
});
test('component read failure leaves a visible retry instead of a silent closed window',async()=>{
 const h=harness();h.context.api=async()=>{throw new Error('Temporary lookup failure');};await h.run("openComponents('photo','listing')");
 assert(h.node('#component-dialog').open);assert.match(h.node('#component-dialog').innerHTML,/Temporary lookup failure/);assert.match(h.node('#component-dialog').innerHTML,/Retry/);
 h.context.api=async()=>payload();await h.run("openComponents('photo','listing')");assert.equal(h.run('componentReview.rows[0].listing'),true);
});
test('navigation during a component read closes the stale chooser',async()=>{
 const h=harness(),d=defer();h.context.api=()=>d.promise;const p=h.run("openComponents('photo')");h.run('state.request++');
 d.resolve(payload());await p;assert(!h.node('#component-dialog').open);assert.equal(h.run('componentReview'),null);
});
test('opening components while image edits are dirty preserves those edits',async()=>{
 const h=harness();let reads=0;h.context.api=async()=>{reads++;return payload();};h.run("state.dirty.add('image-form')");await h.run("openComponents('photo')");assert.equal(reads,0);assert(h.run("state.dirty.has('image-form')"));
});
