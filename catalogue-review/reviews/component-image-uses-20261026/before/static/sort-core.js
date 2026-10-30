'use strict';
// Pure comparison helpers shared by the UI and behaviour tests.
const ImageSort = (() => {
  const labels={similarity:'Visual similarity',listing:'Listing priority',folder:'Folder',type:'Image type',purpose:'Purpose',name:'File name',pixels:'Original pixel count',bytes:'Original file size',source:'Source'};
  const collator=new Intl.Collator(undefined,{numeric:true,sensitivity:'base'});
  const clean=rows=>Array.isArray(rows)?rows.filter((r,i)=>r&&Object.hasOwn(labels,r.key)&&['asc','desc'].includes(r.direction)&&rows.findIndex(x=>x?.key===r.key)===i).slice(0,5).map(r=>({key:r.key,direction:r.direction})):[];
  const parse=text=>clean(String(text||'').split(',').map(x=>{const [key,direction='asc']=x.split(':');return {key,direction};}));
  const encode=rows=>clean(rows).map(r=>r.key+':'+r.direction).join(',');
  const missing=value=>value===null||value===undefined||value==='';
  function compareValue(a,b,direction='asc') {
    // Missing original dimensions/bytes always stay last, including descending.
    if(missing(a)||missing(b))return missing(a)===missing(b)?0:missing(a)?1:-1;
    const sign=direction==='desc'?-1:1;
    if(Array.isArray(a)) {
      for(let i=0;i<Math.max(a.length,b.length);i++){const d=compareValue(a[i],b[i],direction);if(d)return d;}
      return 0;
    }
    return sign*(typeof a==='number'&&typeof b==='number'?a-b:collator.compare(String(a),String(b)));
  }
  const fallback=(a,b)=>collator.compare(a.name||'',b.name||'')||String(a.id).localeCompare(String(b.id));
  const compare=(rows,value)=>(a,b)=>{for(const r of rows){const d=compareValue(value(a,r.key),value(b,r.key),r.direction);if(d)return d;}return 0;};
  function plan(images,rows,value) {
    rows=clean(rows);
    const index=rows.findIndex(r=>r.key==='similarity');
    if(index<0)return {images:[...images].sort((a,b)=>compare(rows,value)(a,b)||fallback(a,b)),groups:null};
    const before=compare(rows.slice(0,index),value),after=compare(rows.slice(index+1),value);
    const ordered=[...images].sort((a,b)=>before(a,b)||after(a,b)||fallback(a,b)),groups=[];
    for(const image of ordered){const last=groups.at(-1);if(!last||before(last[0],image))groups.push([image]);else last.push(image);}
    return {images:ordered,groups:groups.map(g=>g.map(a=>a.id)),reverse:rows[index].direction==='desc'};
  }
  return {labels,clean,parse,encode,compareValue,plan};
})();
if(typeof module!=='undefined')module.exports=ImageSort;
