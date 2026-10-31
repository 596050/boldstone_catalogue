const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const read=n=>fs.readFileSync(path.join(__dirname,n),'utf8');
const M=vm.runInNewContext(read('review-model.js')+';PhotoReview;');
const html=read('wall-sculpture-photo-decisions.htm');
const data=JSON.parse(html.match(/<script id="review-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const ids=new Set(data.products.map(p=>p.id));
const products=Object.fromEntries(data.products.map(p=>[p.id,p]));
const clean=d=>M.clean(d,ids),plain=x=>JSON.parse(JSON.stringify(x));
const empty=clean({});
const filters={group:'attention',product:'',review:'all',tag:'',search:''};
test('wall-only inventory contains all 444 unique remote photographs and 808 Dropbox locations',()=>{
 assert.equal(data.records.length,444);assert.equal(new Set(data.records.map(r=>r.url)).size,444);assert.equal(new Set(data.records.map(r=>r.id)).size,444);
 assert.equal(data.records.reduce((n,r)=>n+r.locations.length,0),808);
 for(const r of data.records){assert.equal(new URL(r.url).protocol,'https:');assert.ok(r.old_products.length);for(const m of r.locations)assert.equal(new URL(m.folder_url).hostname,'www.dropbox.com');}
 assert.equal(data.records.filter(r=>r.local_backup_verified).length,90);
 assert.equal(data.records.some(r=>r.title==='Wallpaper'),false);
});
test('default filter shows exactly the 171 audit flags, all filter shows 444',()=>{
 assert.equal(data.records.filter(r=>M.matches(r,empty,filters,products)).length,171);
 assert.equal(data.records.filter(r=>M.matches(r,empty,{...filters,group:'all'},products)).length,444);
 for(const [group,n] of Object.entries({missing:55,unmatched:35,elsewhere:81,wall:273}))assert.equal(data.records.filter(r=>M.matches(r,empty,{...filters,group},products)).length,n);
});
test('listing, advertising and reference can coexist with multiple image types',()=>{
 const d=clean({uses:['listing','advertising','reference','listing'],types:['product','in_situ','group']});
 assert.deepEqual(plain(d.uses),['listing','advertising','reference']);assert.equal(d.types.length,3);
});
test('primary selection requires a valid component and listing use',()=>{
 const id=data.products[0].id;const d=clean({components:[id],primary_for:[id,'invalid']});
 assert.deepEqual(plain(d.primary_for),[id]);assert.ok(d.uses.includes('listing'));
 const removed=clean({...d,components:[]});assert.equal(removed.primary_for.length,0);
});
test('exclude and duplicate do not carry listing or primary assignments',()=>{
 const id=data.products[0].id;for(const action of ['exclude','duplicate']){const d=clean({action,uses:['listing','advertising'],components:[id],primary_for:[id]});assert.equal(d.uses.length,0);assert.equal(d.primary_for.length,0);}
});
test('copy, duplicate and listing decisions are incomplete until required detail is entered',()=>{
 const r=data.records[0];assert.ok(M.detailsNeeded(r,clean({action:'copy_to_wall'})).length);
 assert.equal(M.complete(r,clean({action:'copy_to_wall',destination:'Acanthus'})),true);
 assert.ok(M.detailsNeeded(r,clean({action:'duplicate'})).length);
 assert.ok(M.detailsNeeded(r,clean({action:'keep_reference',uses:['listing']})).length);
 assert.equal(M.complete(r,clean({action:'check'})),false);
 assert.equal(M.complete(r,clean({action:'exclude'})),true);
});
test('JSON round trip preserves choices, source URLs, Unicode notes and cleared decisions',()=>{
 const r=data.records[0],r2=data.records[1];const d=clean({action:'copy_to_wall',components:[data.products[0].id],uses:['listing','advertising'],types:['product','detail'],notes:'White & Gold £: <script> is plain text',updated_at:'2026-10-30T23:00:00Z'});
 const cleared=clean({updated_at:'2026-10-30T23:01:00Z'});const out=M.exportDocument(data,{[r.id]:d,[r2.id]:cleared});
 assert.equal(out.records.length,2);const imported=M.importDocument(JSON.parse(JSON.stringify(out)),data);assert.deepEqual(plain(imported[r.id]),plain(d));assert.deepEqual(plain(imported[r2.id]),plain(cleared));
 assert.equal(out.records[0].url,r.url);assert.match(out.execution,/No app, Dropbox or Squarespace change/);
});
test('import rejects unrelated files, changed source URLs, unknown components and duplicate entries',()=>{
 assert.throws(()=>M.importDocument({records:[]},data),/not a Boldstone/);
 const r=data.records[0];const out=M.exportDocument(data,{[r.id]:clean({action:'exclude'})});
 const changed=plain(out);changed.records[0].url='https://example.com/wrong.jpg';assert.throws(()=>M.importDocument(changed,data),/does not match/);
 const unknown=plain(out);unknown.records[0].decision.components=['unknown'];assert.throws(()=>M.importDocument(unknown,data),/not in this catalogue/);
 const duplicate=plain(out);duplicate.records.push(duplicate.records[0]);assert.throws(()=>M.importDocument(duplicate,data),/Duplicate decision/);
});
test('import rejects invalid lists and conflicting primary proposals',()=>{
 const component=data.products[0].id;const [r,r2]=data.records;
 const out=M.exportDocument(data,{[r.id]:clean({action:'keep_reference',components:[component],primary_for:[component]})});
 const malformed=plain(out);malformed.records[0].decision.components='invalid';assert.throws(()=>M.importDocument(malformed,data),/invalid components list/);
 const conflict=plain(out);conflict.records.push({...conflict.records[0],id:r2.id,url:r2.url});assert.throws(()=>M.importDocument(conflict,data),/More than one photograph/);
});
test('import replaces the prior primary proposal while preserving other feedback and uses',()=>{
 const component=data.products[0].id;const [r,r2]=data.records;
 const before={[r.id]:clean({action:'keep_reference',components:[component],primary_for:[component],uses:['listing','advertising'],notes:'retain this note'})};
 const incoming={[r2.id]:clean({action:'copy_to_wall',components:[component],primary_for:[component]})};
 const merged=M.mergeImport(before,incoming,ids,'2026-10-30T23:55:00Z');
 assert.equal(merged[r.id].primary_for.length,0);assert.equal(merged[r.id].notes,'retain this note');assert.ok(merged[r.id].uses.includes('advertising'));assert.ok(merged[r2.id].primary_for.includes(component));
});
test('search includes chosen components and notes; purpose and state filters use new feedback',()=>{
 const r=data.records[0],d=clean({action:'keep_reference',uses:['advertising'],notes:'needs a tighter crop'});
 assert.equal(M.matches(r,d,{...filters,search:'tighter crop'},products),true);assert.equal(M.matches(r,d,{...filters,tag:'use:listing'},products),false);assert.equal(M.matches(r,d,{...filters,tag:'use:advertising'},products),true);assert.equal(M.matches(r,d,{...filters,review:'undecided'},products),false);
});
test('portable page and CSV serializers do not allow injected markup or formula execution',()=>{
 assert.equal(M.safeJson({notes:'</script><script>alert(1)</script>'}).includes('</script>'),false);
 assert.match(M.csvCell('=SUM(A1:A4)'),/^"'/);assert.equal(M.csvCell('white, gold'),'"white, gold"');
 assert.equal(html.includes('legacy-unresolved-photo-backup/'),false);assert.equal(html.includes('data:image/'),false);
 assert.equal(fs.readdirSync(__dirname).some(n=>/\.(png|jpe?g|webp|gif)$/i.test(n)),false);
});
