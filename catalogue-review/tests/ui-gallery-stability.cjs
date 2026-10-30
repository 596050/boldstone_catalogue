const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test');

function harness(){
  const nodes=new Map(),timers=[];
  const node=s=>{if(!nodes.has(s))nodes.set(s,{innerHTML:'',textContent:'',scrollTop:0,addEventListener(){},querySelector:()=>null,querySelectorAll:()=>[]});return nodes.get(s);};
  const context=vm.createContext({console,URL,URLSearchParams,ImageSort:require('../static/sort-core.js'),
    document:{querySelector:s=>s.includes('[open]')?null:node(s),querySelectorAll:()=>[],addEventListener(){}},
    window:{addEventListener(){},innerHeight:800,scrollY:0,scrollTo(x,y){this.scrollY=y;}},
    location:{hash:''},history:{replaceState(){}},localStorage:{getItem:()=>null,setItem(){}},
    setTimeout:f=>{timers.push(f);return timers.length;},clearTimeout(){},setInterval(){},clearInterval(){}});
  const run=s=>vm.runInContext(s,context);
  for(const file of ['app.js','image-tools.js','sort-tools.js','sync-tools.js','jobs.js'])
    run(fs.readFileSync(path.join(__dirname,'../static',file),'utf8').replace(/\nboot\(\);\s*$/,'\n'));
  run(`state.pid='P';state.request=1;state.boot={products:[],families:[],image_types:{product:'Product',in_situ:'In situ'},dropbox_sync:{generation:1}};
    state.current={images:Array.from({length:60},(_,i)=>({id:'im'+i,name:'Image '+i,source:'Dropbox',types:['product'],association:{tier:'accepted'}}))};
    scheduleCoverageRefresh=()=>{};renderList=()=>{};renderMain=()=>{};toast=()=>{};initImageSort('');`);
  return {context,run,node,nodes,timers,ids:()=>JSON.parse(run('JSON.stringify(filteredImages().map(im=>im.id))'))};
}

test('Listing and Ads edits hold the entire order, including cards behind Show more',async()=>{
  const h=harness(),before=h.ids();
  h.context.api=async(url,body)=>({...body,version:1});
  await h.run("quick('im40','listing')");
  assert.deepEqual(h.ids(),before);assert.equal(h.run('state.heldImageOrder.length'),60);
  assert.equal(h.run('state.limit'),24);
  await h.run("quick('im40','advertising')");await h.run("quick('im40','listing')");
  assert.deepEqual(h.ids(),before);
  assert.deepEqual(JSON.parse(h.run("JSON.stringify(activeImageUses(data('image','P','im40')))")),['advertising']);
  h.run('state.limit=48');assert.equal(h.run('filteredImages().slice(0,state.limit)[40].id'),'im40');
});

test('shared type edits hold similarity order through a filename, folder and preview refresh',async()=>{
  const h=harness();
  h.run("state.imageSort=[{key:'folder',direction:'asc'},{key:'similarity',direction:'asc'}];filteredImages();");
  h.run("similarityJobs.set(state.sortJobKey,{state:'ready',order:state.current.images.map(im=>im.id).reverse()});");
  const before=h.ids();assert.equal(before[0],'im59');
  h.context.api=async(url,body)=>({...body,version:1});
  await h.run("save('asset','','im40',{types:['product','in_situ']})");
  h.run("Object.assign(state.current.images[40],{name:'Renamed.jpg',folder_label:'New In Situ folder',local_preview:true,cached_file:{stamp:999}})");
  assert.deepEqual(h.ids(),before);assert.equal(h.run('state.sortJobKey'),'');
  assert.equal(h.run("imageTypes(state.current.images[40]).includes('in_situ')"),true);
});

test('a late similarity response cannot reorder cards after review starts',async()=>{
  const h=harness();let release,renders=0;
  h.context.api=async()=>new Promise(resolve=>{release=resolve;});h.context.renderGrid=()=>{renders++;};
  h.run("state.imageSort=[{key:'similarity',direction:'asc'}]");const before=h.ids();
  const signature=h.run('state.sortJobKey');h.timers.shift()();await new Promise(setImmediate);
  h.run("holdImageOrder('im20')");
  release({state:'ready',order:[...before].reverse(),analysed:60,total:60,missing_ids:[]});await new Promise(setImmediate);
  assert.equal(h.run(`similarityJobs.get(${JSON.stringify(signature)}).state`),'ready');
  assert.equal(renders,0);assert.deepEqual(h.ids(),before);
});

test('filters and native deletion still remove images; imports append without reshuffling retained cards',()=>{
  const h=harness();h.run("holdImageOrder('im30');state.imageSearch='Image 2'");
  assert.deepEqual(h.ids(),['im2',...Array.from({length:10},(_,i)=>'im'+(20+i))]);
  h.run("state.imageSearch='';state.current.images=state.current.images.filter(im=>im.id!=='im10');state.current.images.unshift({id:'new',name:'A new photo',association:{tier:'accepted'}})");
  const ids=h.ids();assert.equal(ids.length,60);assert.equal(ids.includes('im10'),false);assert.equal(ids.at(-1),'new');
  assert.deepEqual(ids.slice(0,-1),Array.from({length:60},(_,i)=>'im'+i).filter(id=>id!=='im10'));
});

test('removing Listing in the Listing filter hides the image without shuffling other cards',async()=>{
  const h=harness();h.context.api=async(url,body)=>({...body,version:1});
  for(const id of ['im1','im5','im8'])h.run(`absorb([{kind:'image',product_id:'P',item_id:'${id}',version:1,data:{decision:'reviewed',uses:['listing']}}])`);
  h.run("state.use='listing'");assert.deepEqual(h.ids(),['im1','im5','im8']);
  await h.run("quick('im5','listing')");assert.deepEqual(h.ids(),['im1','im8']);
});

test('Reapply sort deliberately uses current review choices and releases the hold',async()=>{
  const h=harness();h.context.api=async(url,body)=>({...body,version:1});let options;
  h.context.renderGrid=value=>{options=value;};
  await h.run("quick('im40','listing')");assert.equal(h.ids()[40],'im40');
  h.run('applyImageSort(state.imageSort)');assert.equal(h.run('state.heldImageOrder'),null);
  assert.equal(h.ids()[0],'im40');assert.equal(options.preservePosition,false);
  h.run("holdImageOrder('im20');initImageSort('name:desc')");assert.equal(h.run('state.heldImageOrder'),null);
  assert.equal(h.ids()[0],'im59');
});

// A small DOM model checks node identity and updates. Browser QA additionally
// exercises the actual template parsing, native events, focus and layout.
class Node{
  constructor(name,attrs={},children=[]){this.nodeName=name;this.nodeType=name==='#text'?3:1;this.attrs={...attrs};this.childNodes=[];this.nodeValue=attrs.text||'';this.checked=Object.hasOwn(attrs,'checked');this.disabled=Object.hasOwn(attrs,'disabled');this.type=attrs.type;for(const c of children)this.append(c);}
  get attributes(){return Object.entries(this.attrs).map(([name,value])=>({name,value}));}
  get children(){return this.childNodes.filter(n=>n.nodeType===1);}
  get dataset(){return {asset:this.attrs['data-asset']};}
  hasAttribute(k){return Object.hasOwn(this.attrs,k);}
  getAttribute(k){return this.attrs[k]??null;}
  setAttribute(k,v){this.attrs[k]=v;}
  removeAttribute(k){delete this.attrs[k];}
  append(n){n.remove();this.childNodes.push(n);n.parent=this;}
  remove(){if(this.parent){this.parent.childNodes.splice(this.parent.childNodes.indexOf(this),1);this.parent=null;}}
  replaceWith(n){this.parent.insertBefore(n,this);this.remove();}
  insertBefore(n,before){n.remove();const i=before?this.childNodes.indexOf(before):this.childNodes.length;this.childNodes.splice(i,0,n);n.parent=this;}
}
const text=s=>new Node('#text',{text:s});
const card=(id,selected=false)=>new Node('ARTICLE',{'data-asset':id,class:selected?'chosen':''},[
  new Node('IMG',{src:'/preview/'+id,alt:'Photo '+id}),
  new Node('INPUT',{type:'checkbox',...(selected?{checked:''}:{})}),
  new Node('BUTTON',{'aria-pressed':String(selected)},[text('Listing')]),
  new Node('DIV',{},selected?[new Node('SPAN',{},[text('Listing')])]:[])]);

test('patching a card retains its preview and clicked button, updates choices and removes obsolete badges',()=>{
  const h=harness(),old=card('one'),next=card('one',true),[img,checkbox,button]=old.children;
  button.disabled=true;button.attrs.disabled='';h.context.old=old;h.context.next=next;
  h.run('patchGalleryNode(old,next)');
  assert.equal(old.children[0],img);assert.equal(old.children[2],button);assert.equal(checkbox.checked,true);
  assert.equal(button.getAttribute('aria-pressed'),'true');assert.equal(button.hasAttribute('disabled'),true);
  assert.equal(old.children[3].children.length,1);
  h.context.next=card('one');h.run('patchGalleryNode(old,next)');
  assert.equal(old.children[0],img);assert.equal(old.children[2],button);assert.equal(checkbox.checked,false);
  assert.equal(old.children[3].children.length,0);
});

test('keyed gallery updates retain unchanged nodes and reconcile real additions, deletions and explicit reorders',()=>{
  const h=harness(),a=card('a'),b=card('b'),c=card('c'),root=new Node('DIV',{},[a,b,c]);
  h.context.root=root;h.context.document.createElement=()=>({content:{children:[card('c',true),card('a'),card('d')]}});
  h.run("renderGalleryCards(root,'test template')");
  assert.deepEqual(root.children.map(c=>c.dataset.asset),['c','a','d']);
  assert.equal(root.children[0],c);assert.equal(root.children[1],a);assert.equal(b.parent,null);
});

test('a type dropdown remains open when another card updates',()=>{
  const h=harness(),old=new Node('DETAILS',{open:''},[text('Types')]);h.context.old=old;h.context.next=new Node('DETAILS',{},[text('Types')]);
  h.run('patchGalleryNode(old,next)');assert.equal(old.hasAttribute('open'),true);
});

test('an open type menu retains its pending choices and busy state during another save',()=>{
  const h=harness(),input=new Node('INPUT',{type:'checkbox',checked:'',disabled:''});
  const old=new Node('DETAILS',{'data-card-types':'one',open:'','aria-busy':'true'},[input]);
  h.context.old=old;h.context.next=new Node('DETAILS',{'data-card-types':'one'},[new Node('INPUT',{type:'checkbox'})]);
  h.run('patchGalleryNode(old,next)');assert.equal(old.getAttribute('aria-busy'),'true');
  assert.equal(old.children[0],input);assert.equal(input.checked,true);assert.equal(input.disabled,true);
});

function positions(h){
  const view={cards:[],offsets:{one:200,two:400}};
  const make=id=>({dataset:{asset:id},getBoundingClientRect:()=>({top:view.offsets[id]-h.context.window.scrollY,bottom:view.offsets[id]+150-h.context.window.scrollY}),
    querySelector:()=>({getBoundingClientRect:()=>({top:view.offsets[id]+100-h.context.window.scrollY,bottom:view.offsets[id]+150-h.context.window.scrollY})})});
  view.cards=[make('one'),make('two')];
  h.node('#image-grid').getBoundingClientRect=()=>({top:0});h.node('#image-grid').querySelectorAll=()=>view.cards;
  h.node('.masthead').getBoundingClientRect=()=>({bottom:80});
  h.context.document.querySelectorAll=selector=>selector==='#image-grid .image-card'?view.cards:[];
  return view;
}

test('scroll anchoring keeps the edited controls still and falls back to another surviving card',()=>{
  const h=harness(),view=positions(h);h.run("state.lastEditedImageId='one';var position=captureGalleryPosition()");
  view.offsets.one+=70;view.offsets.two+=70;h.run('restoreGalleryPosition(position)');assert.equal(h.context.window.scrollY,70);
  h.run('position=captureGalleryPosition()');view.cards=view.cards.filter(c=>c.dataset.asset!=='one');view.offsets.two-=150;
  h.run('restoreGalleryPosition(position)');assert.equal(h.context.window.scrollY,-80);
});

for(const call of ['refreshNativeView()','refreshDropboxView({generation:2})'])test(call+' anchors the latest scroll after asynchronous reads, not the old position',async()=>{
  const h=harness(),view=positions(h);let release;
  h.run('dropboxShownGeneration=1;syncCanRefresh=()=>true');
  h.context.api=async url=>url==='/api/bootstrap'?{products:[{id:'P',review:{version:0}}],families:[],assignments:[],dropbox_sync:{generation:2}}:new Promise(resolve=>{release=resolve;});
  h.context.renderMain=()=>{view.offsets.one+=50;view.offsets.two+=50;};
  const pending=h.run(call);await new Promise(setImmediate);
  h.context.window.scrollY=100;release({id:'P',images:[],reviews:[]});await pending;
  assert.equal(h.context.window.scrollY,150);
});
