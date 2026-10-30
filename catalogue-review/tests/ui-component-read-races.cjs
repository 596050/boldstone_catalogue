const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test');
const tick=()=>new Promise(setImmediate);
function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};}
const response=value=>({ok:true,json:async()=>value});
function harness(){
  const nodes=new Map(),listeners={},messages=[];
  const node=s=>{if(!nodes.has(s))nodes.set(s,{id:s.slice(1),value:'',innerHTML:'',textContent:'',open:false,disabled:false,dataset:{},
    addEventListener(){},setAttribute(){},removeAttribute(){},querySelector:()=>null,querySelectorAll:()=>[],classList:{toggle(){}},
    close(){this.open=false;},showModal(){this.open=true;}});return nodes.get(s);};
  const context=vm.createContext({console,URL,URLSearchParams,
    document:{querySelector:node,querySelectorAll:()=>[],addEventListener:(type,fn)=>(listeners[type]||=[]).push(fn)},
    window:{addEventListener(){},confirm:()=>true},location:{hash:'#A'},history:{replaceState(){}},
    setTimeout(){},clearTimeout(){},setInterval(){},clearInterval(){}});
  const run=s=>vm.runInContext(s,context);
  for(const file of ['app.js','image-tools.js','component-tools.js','component-overview.js'])run(fs.readFileSync(path.join(__dirname,'../static',file),'utf8').replace(/\nboot\(\);\s*$/,'\n'));
  context.report=message=>messages.push(message);
  run(`state.pid='A';state.request=1;state.boot={csrf_token:'test-only',products:[],image_types:{}};
    state.current={id:'A',images:[{id:'one',original:{dropbox_content_hash:'shown-hash'}}]};
    toast=report;scheduleCoverageRefresh=()=>{};renderGrid=()=>{};renderComponentRows=()=>{};
    renderComponentOverview=payload=>'review version '+payload.version;
    refreshNativeView=async()=>true;refreshAllSpecifications=()=>{};`);
  return {run,context,node,listeners,messages};
}
const payload=version=>({version,product:{id:'A'},images:[],related_images:[],image:{id:'one',name:'one.jpg',types:[]},rows:[]});
function server(h){
  const gate=deferred(),reads=[];let version=0;
  h.context.fetch=async(url,options={})=>{
    if(options.method==='POST'){
      const body=JSON.parse(options.body);await gate.promise;
      return response({...body,version:++version});
    }
    reads.push(url);return response(payload(version));
  };
  return {gate,reads};
}
const views=[
  {name:'component preview',start:"selectOverviewComponent('A')",dialog:'#component-overview-dialog',version:'overviewPayload.version',close:'closeComponentOverview()'},
  {name:'component chooser',start:"openComponents('one')",dialog:'#component-dialog',version:'componentReview.version',close:'closeComponents()'}
];
for(const view of views){
  test(view.name+' waits for queued image choices before reading saved purposes',async()=>{
    const h=harness(),s=server(h);h.node(view.dialog).open=true;
    const saving=h.run("quick('one','listing')"),saving2=h.run("quick('one','advertising')"),opening=h.run(view.start);
    await tick();const before=s.reads.length;s.gate.resolve();await Promise.all([saving,saving2,opening]);
    assert.equal(before,0);assert.equal(h.run(view.version),2);
  });
  test(view.name+' re-reads a response overtaken by a saved choice',async()=>{
    const h=harness(),s=server(h),old=deferred(),underlying=h.context.fetch;let count=0;
    h.node(view.dialog).open=true;
    h.context.fetch=(url,options={})=>options.method!=='POST'&&++count===1?old.promise:underlying(url,options);
    const opening=h.run(view.start);await tick();const saving=h.run("quick('one','listing')");s.gate.resolve();await saving;
    old.resolve(response(payload(0)));await opening;assert.equal(count,2);assert.equal(h.run(view.version),1);
  });
  test('closing '+view.name+' while saves are pending skips the obsolete read',async()=>{
    const h=harness(),s=server(h);h.node(view.dialog).open=true;
    const saving=h.run("quick('one','listing')"),opening=h.run(view.start);h.run(view.close);
    s.gate.resolve();await Promise.all([saving,opening]);assert.deepEqual(s.reads,[]);assert.equal(h.node(view.dialog).open,false);
  });
}

test('switching components while a save finishes reads only the latest preview',async()=>{
  const h=harness(),s=server(h);h.node('#component-overview-dialog').open=true;
  const saving=h.run("quick('one','listing')"),first=h.run("selectOverviewComponent('A')"),second=h.run("selectOverviewComponent('B')");
  s.gate.resolve();await Promise.all([saving,first,second]);assert.deepEqual(s.reads,['/api/component-overview/B']);
});

test('preview can display current server choices after a failed save',async()=>{
  const h=harness(),s=server(h);h.node('#component-overview-dialog').open=true;
  const saving=Promise.allSettled([h.run("quick('one','listing')")]),opening=h.run("selectOverviewComponent('A')");
  s.gate.reject(Error('Temporary save error'));await Promise.all([saving,opening]);assert.equal(h.run('overviewPayload.version'),0);
});

test('original request is pinned to the hash of the displayed photo',async()=>{
  const h=harness(),calls=[],button={dataset:{fetchOriginal:'one'},textContent:'Fetch original',hasAttribute:()=>false};
  h.context.api=async(url,body)=>{calls.push({url,body});throw Error('Isolated fetch failure');};
  await h.listeners.click[1]({target:{closest:()=>button}});
  assert.equal(calls[0].url,'/api/original');assert.equal(calls[0].body.expected_content_hash,'shown-hash');
});
