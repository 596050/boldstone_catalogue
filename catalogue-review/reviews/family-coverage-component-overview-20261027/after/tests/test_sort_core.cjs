const assert=require('node:assert/strict');
const S=require('../static/sort-core.js');
const images=[
 {id:'a',name:'panel10',folder:'X',bytes:100},
 {id:'b',name:'panel2',folder:'X',bytes:200},
 {id:'c',name:'panel1',folder:'Y',bytes:null},
 {id:'d',name:'panel3',folder:'Y',bytes:50}
];
const value=(a,key)=>a[key], ids=plan=>plan.images.map(a=>a.id);
assert.deepEqual(ids(S.plan(images,S.parse('folder:asc,bytes:desc'),value)),['b','a','d','c']);
assert.deepEqual(ids(S.plan(images,S.parse('folder:desc,bytes:asc'),value)),['d','c','a','b']);
assert.deepEqual(ids(S.plan(images,S.parse('name:asc'),value)),['c','b','d','a']);
const sim=S.plan(images,S.parse('folder:asc,similarity:desc,bytes:desc'),value);
assert.deepEqual(sim.groups,[['b','a'],['d','c']]);assert.equal(sim.reverse,true);
assert.deepEqual(S.plan([...images].reverse(),S.parse('folder:asc,similarity:desc,bytes:desc'),value),sim);
assert.equal(S.encode(S.parse('bad:asc,name:desc,name:asc,pixels:invalid,similarity:asc')),'name:desc,similarity:asc');
assert.deepEqual(S.plan(images,S.parse('similarity:asc'),value).groups,[['c','b','d','a']]);
assert.equal(S.compareValue(null,100,'desc'),1);assert.equal(S.compareValue(100,null,'asc'),-1);
assert.equal(S.compareValue(['a','b'],['a','c'],-1),-1);
console.log('9 multi-sort behaviour checks passed');
