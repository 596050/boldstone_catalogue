const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test');
const source=fs.readFileSync(path.resolve(__dirname,'../../Boldstone_Relief_Layout_Lab (1).html'),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
function geometry(){const module={exports:{}};vm.runInNewContext(source,{module});return module.exports.calculateLayout;}
function harness(){
  const nodes=new Map(),downloads=[],blobs=new Map();let printed=0;
  function node(id){
    if(!nodes.has(id))nodes.set(id,{id,value:'',disabled:false,textContent:'',innerHTML:'',className:'',listeners:{},
      addEventListener(type,fn){this.listeners[type]=fn;}});
    return nodes.get(id);
  }
  for(const [id,value] of Object.entries({wallW:'2400',wallH:'1800',gap:'50',axis:'row'}))node(id).value=value;
  const context={Blob,setTimeout:fn=>fn(),document:{getElementById:node,body:{appendChild(){}},
    createElement:()=>({click(){downloads.push({name:this.download,blob:blobs.get(this.href)});},remove(){}})},
    URL:{createObjectURL:blob=>{const key='blob:'+blobs.size;blobs.set(key,blob);return key;},revokeObjectURL(){}},window:{print:()=>printed++}};
  vm.runInNewContext(source,context);
  return {node,downloads,printed:()=>printed,
    change(id,value){node(id).value=String(value);node(id).listeners.input();},
    panel(index,field,value){node('panels').listeners.input({target:{dataset:{index:String(index),field},type:field==='rotate'?'checkbox':'number',value:String(value),checked:!!value}});},
    click(id){if(!node(id).disabled)node(id).listeners.click();}};
}

test('standalone layout centres uneven rotated panels with the requested gaps',()=>{
  const result=geometry()(2000,1000,50,'row',[{width:400,height:300,rotate:true},{width:500,height:200}]);
  assert.equal(result.totalWidth,850);assert.equal(result.totalHeight,400);
  assert.equal(result.panels[0].x,575);assert.equal(result.panels[0].y,300);
  assert.equal(result.panels[1].x,925);assert.equal(result.panels[1].y,400);
  assert.equal(result.panels[0].rotation,90);
});
test('standalone vertical layout keeps each differently sized panel on the wall centre line',()=>{
  const result=geometry()(1000,2000,50,'column',[{width:400,height:300},{width:200,height:500}]);
  assert.equal(result.totalWidth,400);assert.equal(result.totalHeight,850);
  assert.equal(result.panels[0].x,300);assert.equal(result.panels[0].y,575);
  assert.equal(result.panels[1].x,400);assert.equal(result.panels[1].y,925);
});
test('decimal exact fits do not become false overhang warnings through floating-point addition',()=>{
  const calculate=geometry();
  for(const axis of ['row','column']){
    const result=calculate(2000.3,2000.3,0,axis,[{width:1000.1,height:1000.1},{width:1000.2,height:1000.2}]);
    assert.equal(result.fits,true);assert.equal(axis==='row'?result.sideMargin:result.topMargin,0);
    assert.equal(axis==='row'?result.totalWidth:result.totalHeight,2000.3);
  }
});
test('a real fractional overhang remains visible',()=>{
  const result=geometry()(2000.3,2000,0,'row',[{width:1000.1,height:100},{width:1000.2001,height:100}]);
  assert.equal(result.fits,false);assert(result.sideMargin<0);
});
test('invalid and excessive inputs are rejected before generating a layout',()=>{
  const calculate=geometry(),panels=[{width:400,height:300}];
  for(const wall of [0,-1,NaN,Infinity,50001])assert.throws(()=>calculate(wall,1000,0,'row',panels));
  assert.throws(()=>calculate(1000,1000,-1,'row',panels));
  assert.throws(()=>calculate(1000,1000,0,'diagonal',panels));
  assert.throws(()=>calculate(1000,1000,0,'row',[]));
  assert.throws(()=>calculate(1000,1000,0,'row',Array(11).fill(panels[0])));
});
test('standalone SVG output stays finite for positive dimensions accepted by the calculator',async()=>{
  const h=harness();h.change('wallW','1e-320');h.change('wallH','1e-320');h.change('gap',0);
  for(let i=0;i<3;i++){h.panel(i,'width','1e-321');h.panel(i,'height','1e-321');}
  h.click('svg');assert.equal(h.downloads.length,1);
  assert(!/NaN|Infinity/.test(await h.downloads[0].blob.text()));
});
test('invalid edits disable exports and clear the previously calculated brief',()=>{
  const h=harness();assert.equal(h.node('json').disabled,false);
  h.change('gap','');h.click('json');h.click('print');
  assert.equal(h.downloads.length,0);assert.equal(h.printed(),0);assert.equal(h.node('brief').textContent,'');
  assert.match(h.node('error').textContent,/including 0/);assert.equal(h.node('svg').disabled,true);
  h.change('gap',0);assert.equal(h.node('json').disabled,false);
});
test('JSON export matches the currently entered orientation and footprint',async()=>{
  const h=harness();h.panel(0,'width',200);h.panel(0,'height',500);h.panel(0,'rotate',true);h.change('axis','column');
  h.click('json');const brief=JSON.parse(await h.downloads[0].blob.text());
  assert.equal(brief.arrangement,'column');assert.equal(brief.panels[0].rotation,90);
  assert.equal(brief.panels[0].width,500);assert.equal(brief.panels[0].height,200);
  assert.equal(brief.composition.height,1100);assert.equal(brief.composition.footprintFits,true);
});
