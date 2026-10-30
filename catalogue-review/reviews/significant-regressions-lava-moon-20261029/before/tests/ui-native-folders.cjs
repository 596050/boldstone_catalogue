const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test');

function harness(){
  const nodes=new Map(),listeners={};
  const node=s=>{if(!nodes.has(s))nodes.set(s,{value:'',innerHTML:'',textContent:'',scrollTop:0,addEventListener(){}});return nodes.get(s);};
  const ctx=vm.createContext({URL,URLSearchParams,console,location:{hash:'#library?family=Frozen%20Fish'},
    localStorage:{getItem(){return null;},setItem(){}},history:{replaceState(){}},
    document:{querySelector:node,querySelectorAll:()=>[],addEventListener:(type,fn)=>{(listeners[type]??=[]).push(fn);}},
    window:{addEventListener(){}},setTimeout,clearTimeout,setInterval,clearInterval});
  const run=s=>vm.runInContext(s,ctx);
  for(const name of ['image-tools.js','family-tools.js','app.js'])run(fs.readFileSync(path.join(__dirname,'../static',name),'utf8').replace(/\nboot\(\);\s*$/,''));
  run(`state.boot={family_inventory:{family_folders:{'Frozen Fish':[
    {id:'white',name:'Frozen Fish White',relative_name:'Frozen Fish White',url:'https://www.dropbox.com/home/Root/Frozen%20Fish%20White',image_count:6,direct_image_count:6},
    {id:'situ',name:'Frozen Fish White In Situ',relative_name:'Frozen Fish White In Situ',url:'https://www.dropbox.com/home/Root/Frozen%20Fish%20White%20In%20Situ',image_count:20,direct_image_count:20},
    {id:'terracotta',name:'Frozen Fish Terracotta',relative_name:'Frozen Fish Terracotta',url:'https://www.dropbox.com/home/Root/Frozen%20Fish%20Terracotta',image_count:9,direct_image_count:9},
    {id:'verdigris',name:'Frozen Fish Verdigris',relative_name:'Frozen Fish Verdigris',url:'https://www.dropbox.com/home/Root/Frozen%20Fish%20Verdigris',image_count:8,direct_image_count:8}
  ]}},products:[{id:'P1',name:'Frozen Fish One - White',family:'Frozen Fish',image_count:9}],coverage:{products:{},families:{}}};
  state.pid='__library__';state.libraryFamily='Frozen Fish';state.imageFolder='white';state.library={images:[]};`);
  run("sidebarMode='folders'");
  return {run,node,listeners,ctx};
}

test('folder-first sidebar shows four native folders and keeps saved records separate',()=>{
  const h=harness(),html=h.run('groupedProductList(state.boot.products)');
  assert.equal((html.match(/class="native-folder-link/g)||[]).length,4);
  assert.match(html,/4 folders/);
  assert.match(html,/Specifications &amp; saved components|Specifications & saved components/);
  assert.match(html,/<details[^>]*data-component-family="Frozen Fish"\s*>/);
  assert.match(html,/href="#library\?family=Frozen%20Fish&folder=white"/);
});

test('White includes its subfolders, never White In Situ or platform copies',()=>{
  const h=harness();
  assert.equal(h.run("imageMatchesFolder({source:'Dropbox',folder_url:'https://www.dropbox.com/home/Root/Frozen%20Fish%20White'})"),true);
  assert.equal(h.run("imageMatchesFolder({source:'Dropbox',folder_url:'https://www.dropbox.com/home/Root/Frozen%20Fish%20White/Detail'})"),true);
  assert.equal(h.run("imageMatchesFolder({source:'Dropbox',folder_url:'https://www.dropbox.com/home/Root/Frozen%20Fish%20White%20In%20Situ'})"),false);
  assert.equal(h.run("imageMatchesFolder({source:'Squarespace',folder_url:'https://www.dropbox.com/home/Root/Frozen%20Fish%20White'})"),false);
});

test('stable folder link follows renamed path and removed folder never shows all images',()=>{
  const h=harness();
  h.run("state.boot.family_inventory.family_folders['Frozen Fish'][0].url='https://www.dropbox.com/home/Root/White%20renamed'");
  assert.equal(h.run("imageMatchesFolder({source:'Dropbox',folder_url:'https://www.dropbox.com/home/Root/White%20renamed'})"),true);
  assert.equal(h.run("imageMatchesFolder({source:'Dropbox',folder_url:'https://www.dropbox.com/home/Root/Frozen%20Fish%20White'})"),false);
  h.run("state.boot.family_inventory.family_folders['Frozen Fish'].shift()");
  assert.equal(h.run("imageMatchesFolder({source:'Dropbox',folder_url:'https://www.dropbox.com/home/Root/White%20renamed'})"),false);
  assert.match(h.run('folderControls()'),/Folder no longer in current inventory/);
});

test('search finds folders without inventing a component record',()=>{
  const h=harness();h.node('#search').value='Terracotta';
  const html=h.run('groupedProductList([])');
  assert.match(html,/Frozen Fish Terracotta/);
  assert.equal((html.match(/class="native-folder-link/g)||[]).length,1);
  assert.doesNotMatch(html,/data-product=/);
});

test('component browsing and review filters retain existing product navigation',()=>{
  const h=harness();h.run("sidebarMode='components'");
  assert.match(h.run('groupedProductList(state.boot.products)'),/data-product="P1"/);
  assert.doesNotMatch(h.run('groupedProductList(state.boot.products)'),/native-folder-link/);
  h.run("sidebarMode='folders'");h.node('#review-filter').value='reviewed';
  assert.doesNotMatch(h.run('groupedProductList(state.boot.products)'),/native-folder-link/);
});

test('folder dropdown includes empty native folders and does not duplicate URL entries',()=>{
  const h=harness();h.run(`state.boot.family_inventory.family_folders['Frozen Fish'][0].image_count=0;
    state.library.images=[{folder_url:state.boot.family_inventory.family_folders['Frozen Fish'][1].url,folder_label:'Frozen Fish White In Situ'}]`);
  const html=h.run('folderControls()');
  assert.match(html,/value="white">Frozen Fish White \(0\)/);
  assert.equal((html.match(/>Frozen Fish White In Situ \(/g)||[]).length,1);
});
