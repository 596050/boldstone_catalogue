'use strict';
const typeLabels = () => state.boot.image_types || {};
const imageTypes = image => data('asset','',image.id).types ?? image.types ?? [];
function bytesLabel(value) {
  if(!Number.isFinite(value)) return 'File size unavailable';
  return (value/1048576>=1?(value/1048576).toFixed(2)+' MB':(value/1024).toFixed(1)+' KB')+' · '+value.toLocaleString()+' bytes';
}
function originalSize(image, compact=false) {
  const o=image.original||{}, d=o.dimensions;
  const pixels=d?d.join(' × ')+' px':'Pixel dimensions not available';
  return pixels+(compact?' · ': ' — ')+bytesLabel(o.bytes);
}
function sizePanel(image) {
  const o=image.original||{}, c=image.cached_file||{};
  return `<div class="size-panel"><strong>${image.source==='Dropbox'?'Dropbox original':'Retained platform source'}</strong><span>${esc(originalSize(image))}</span><small>${esc(o.dimension_basis||'Original metadata unavailable')}</small>${!o.dimensions&&c.dimensions?`<small>Displayed cached file: ${esc(c.dimensions.join(' × '))} px. These are not the original dimensions.</small>`:''}${image.source==='Dropbox'&&o.dropbox_content_hash&&o.bytes&&(!o.locally_verified||!o.dimensions)?`<button class="button" data-fetch-original="${esc(image.id)}">Fetch Dropbox original · ${esc(bytesLabel(o.bytes).split(' · ')[0])}</button><small>Reads the original using your existing Dropbox connection.</small>`:''}</div>`;
}
function typeControls(image) {
  const types=imageTypes(image);
  return `<fieldset class="type-controls"><legend>Image type · choose all that apply</legend>${Object.entries(typeLabels()).map(([value,label])=>`<label class="check-line"><input type="checkbox" name="image_type" value="${esc(value)}" ${types.includes(value)?'checked':''}>${esc(label)}</label>`).join('')}</fieldset><p class="small muted">Type describes what is shown. Listing, advertising and social uses are separate choices above.</p>`;
}
function duplicateDetails(image) {
  const members=image.duplicates||[], conflicts=image.duplicate_conflicts||[];
  if(!members.length&&!conflicts.length)return '';
  return `<details class="duplicate-details"><summary>${members.length||1} source records · one exact-byte image${conflicts.length?' · conflicting reviews':''}</summary><p>Dropbox is preferred. Original source records and review history are retained. Saving choices here applies them to these identical copies for this sculpture; shared tags apply across titles.</p>${members.map(a=>`<p><strong>${esc(a.source)}</strong> · ${esc(a.name)}<br>${a.url?`<a href="${safeURL(a.url)}" target="_blank" rel="noopener">Source image ↗</a>`:''} ${a.folder_url?` · <a href="${safeURL(a.folder_url)}" target="_blank" rel="noopener">Folder ↗</a>`:''}</p>`).join('')}${(image.duplicate_review_details||[]).map(r=>`<p>${esc(r.kind)} · ${esc(r.item_id)}<br>${esc(JSON.stringify(r.data))}</p>`).join('')}</details>${conflicts.length?`<p class="conflict-note">${esc(conflicts.join('. '))}. Check the retained choices above and save the image choices and shared tags to resolve them. Conflicts are withheld from export.</p>`:''}`;
}
function tierLabel(image) {
  return ({accepted:'Accepted reference',folder:'Reference folder · review image',related:'Related candidate · identity unconfirmed',manual:'Assigned by you',removed:'Removed from this title'})[image.association?.tier]||'';
}
function matchScope(image) {
  if(state.pid==='__library__')return true;
  const tier=image.association?.tier;
  if(state.scope==='removed')return tier==='removed';
  if(tier==='removed')return false;
  if(state.scope==='all')return true;
  const choice=data('image',state.pid,image.id);
  const selected=choice.decision!=='exclude'&&(choice.uses||[]).includes('listing');
  if(state.scope==='related')return tier==='related'&&!selected;
  return tier!=='related'||selected||(image.duplicate_conflicts||[]).length;
}
function routeState() {
  const [id,query='']=location.hash.slice(1).split('?');
  if(id.startsWith('family='))return {pid:'__family__',family:decodeURIComponent(id.slice(7))};
  const params=new URLSearchParams(query);
  return {pid:decodeURIComponent(id)==='library'?'__library__':decodeURIComponent(id),role:params.get('type')||'',scope:params.get('scope')||'sculpture',use:params.get('use')||''};
}
function updateFilterRoute() {
  const params=new URLSearchParams();
  if(state.role)params.set('type',state.role);
  if(state.scope!=='sculpture')params.set('scope',state.scope);
  if(state.use)params.set('use',state.use);
  history.replaceState(null,'','#'+(state.pid==='__library__'?'library':state.pid)+(params.size?'?'+params:''));
}
function renderCategories() {
  const root=$('#image-categories');if(!root)return;
  const images=filteredImages(true);
  const labels={'':'All types',product:'Product',in_situ:'In situ',group:'Group / series',detail:'Detail',rear:'Rear / fixings',workshop:'Workshop',design_reference:'Design reference',mockup:'Mock-up',packaging:'Packaging',other:'Other'};
  root.innerHTML='<span class="category-heading">Image categories <small>Multiple types can apply to one image. Use Types on a card to edit.</small></span><div class="category-buttons">'+Object.entries(labels).filter(([k])=>!k||['product','in_situ','group','detail'].includes(k)||state.role===k||images.some(a=>imageTypes(a).includes(k))).map(([k,label])=>`<button class="category-button ${state.role===k?'active':''}" data-category="${esc(k)}" aria-pressed="${state.role===k}">${label} <span>${images.filter(a=>!k||imageTypes(a).includes(k)).length}</span></button>`).join('')+'</div>';
  const hidden=state.pid==='__library__'||state.scope==='all'||state.scope==='removed'?0:filteredImages(false,true).filter(a=>!matchScope(a)).length;
  if(hidden)root.innerHTML+=`<p class="category-hint">${hidden} more ${state.role?esc(labels[state.role]||typeLabels()[state.role]).toLowerCase():'source'} images outside this scope. <button class="text-button" id="show-category-all">Show all associations</button> · Check the exact sculpture and finish before selecting.</p>`;
}
function scopeControls() {
  if(state.pid==='__library__')return '';
  const images=currentImages(), candidates=images.filter(a=>a.association?.tier==='related'&&!(data('image',state.pid,a.id).decision!=='exclude'&&data('image',state.pid,a.id).uses?.includes('listing'))).length, removed=images.filter(a=>a.association?.tier==='removed').length;
  return `<select id="image-scope" aria-label="Image association scope"><option value="sculpture">This sculpture</option><option value="related">Related candidates (${candidates})</option><option value="all">All retained associations</option><option value="removed">Removed from this title (${removed})</option></select>`;
}
function dedupeNotice() {
  const d=state.boot.source.dedupe||{};
  return `<div class="dedupe-notice"><span>✓ Exact-byte duplicates filtered</span><span>${d.hidden_records||0} repeated records hidden across the library; ${d.non_dropbox_copies_filtered||0} platform copies replaced by Dropbox.</span><button class="text-button" id="transfer-history">Transfer history</button><button class="text-button" id="delete-history">Deletion history</button></div>`;
}
let transferIDs=[];
function openTransfer(ids, mode) {
  if(state.dirty.size){toast('Save your edits before transferring images.',true);return;}
  transferIDs=ids;
  if(!ids.length)return;
  if($('#image-dialog').open)closeImage();
  const library=state.pid==='__library__';
  $('#transfer-dialog').innerHTML=`<button class="close" data-close="transfer-dialog" aria-label="Close transfer">×</button><span class="eyebrow">ORGANISE IMAGES</span><h2>${ids.length===1?'Transfer this image':`Transfer ${ids.length} images`}</h2><p class="small muted transfer-intro">Move the association to the correct sculpture, or share the same image with another title. Original files and source links stay intact. Image uses remain attached to their original title; review uses at the destination.</p><form id="transfer-form"><label>Action<select name="mode" id="transfer-mode">${library?'':'<option value="move">Move to another title</option>'}<option value="copy">Also use under another title</option>${library?'':'<option value="remove">Remove from this title</option><option value="restore">Restore to this title</option>'}</select></label><div id="transfer-destination"><label>Find destination<input id="transfer-search" type="search" placeholder="Search sculpture title or family…"></label><label>Destination sculpture<select id="transfer-target" name="target" size="8" aria-label="Destination sculpture"></select></label></div><p id="transfer-summary" class="small muted"></p><button class="button dark" type="submit">Apply transfer</button></form>`;
  $('#transfer-mode').value=mode||(library?'copy':'move');
  renderTransferTargets();updateTransferMode();$('#transfer-dialog').showModal();
}
function renderTransferTargets() {
  const q=$('#transfer-search').value.toLowerCase(), before=$('#transfer-target').value;
  const products=state.boot.products.filter(p=>p.id!==state.pid&&(!q||[p.name,p.family,p.id].join(' ').toLowerCase().includes(q)));
  $('#transfer-target').innerHTML=products.map(p=>`<option value="${esc(p.id)}">${esc(p.name)} · ${esc(p.family)}</option>`).join('');
  if(products.some(p=>p.id===before))$('#transfer-target').value=before;
  else $('#transfer-target').selectedIndex=-1;
}
function updateTransferMode() {
  const mode=$('#transfer-mode').value;
  $('#transfer-destination').hidden=['remove','restore'].includes(mode);
  $('#transfer-summary').textContent=mode==='remove'?'The image will stay in the library and other titles. You can undo this change.':mode==='restore'?'The image will reappear under this title.':'Select the exact destination finish. No product specifications are transferred.';
}
async function refreshAfterTransfer() {
  state.boot=await api('/api/bootstrap');absorb(state.boot.assignments||[]);
  const payload=await api(state.pid==='__library__'?'/api/library':'/api/products/'+encodeURIComponent(state.pid));
  absorb(payload.reviews);if(state.pid==='__library__')state.library=payload;else state.current=payload;
  state.selected.clear();renderMain();renderList();
}
async function performTransfer(form) {
  const button=$('button[type=submit]',form),mode=form.elements.mode.value,target=form.elements.target.value;
  if(['move','copy'].includes(mode)&&!target){toast('Select a destination sculpture.',true);return;}
  button.disabled=true;
  try{
    const versions={};for(const pid of [state.pid,target].filter(Boolean))versions[pid]=Object.fromEntries(transferIDs.map(aid=>[aid,review('assignment',pid,aid).version]));
    const result=await api('/api/assignments',{asset_ids:transferIDs,from_product_id:state.pid,to_product_id:['move','copy'].includes(mode)?target:'',mode,versions});
    state.dirty.delete('transfer-form');$('#transfer-dialog').close();await refreshAfterTransfer();toast(result.description+' · saved locally');
  }catch(e){toast(e.message,true);}finally{button.disabled=false;}
}
function showTransferHistory() {
  $('#history-dialog').innerHTML=`<button class="close" data-close="history-dialog" aria-label="Close history">×</button><span class="eyebrow">REVERSIBLE IMAGE ASSIGNMENTS</span><h2>Transfer history</h2><p class="small muted transfer-intro">Undo restores the previous title associations. Later conflicting transfers must be undone first. Image choices and original files are preserved.</p>${(state.boot.operations||[]).map(op=>`<div class="operation-row"><p>${esc(op.description)}<br><small class="muted">${esc(new Date(op.at).toLocaleString())}</small></p>${op.undone?'<span class="chip">Undone</span>':`<button class="button" data-undo-transfer="${esc(op.id)}">Undo</button>`}</div>`).join('')||'<p>No transfers yet.</p>'}`;$('#history-dialog').showModal();
}
document.addEventListener('click',async e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.hasAttribute('data-category')||b.id==='show-category-all'){
    if(b.id==='show-category-all')state.scope='all';else state.role=b.dataset.category;
    state.limit=24;state.selected.clear();renderImages();return;
  }
  if(b.dataset.imageTypes){openImage(b.dataset.imageTypes);if(state.image?.id===b.dataset.imageTypes){$('#asset-form').scrollIntoView({block:'start'});$('#asset-form input').focus({preventScroll:true});}return;}
  if(b.dataset.fetchOriginal){
    if(state.dirty.size){toast('Save your edits before fetching the original.',true);return;}
    b.disabled=true;const aid=b.dataset.fetchOriginal;b.textContent='Fetching and verifying original…';
    try{const result=await api('/api/original',{asset_id:aid});const index=currentImages().findIndex(a=>a.id===aid);if(index>=0)Object.assign(currentImages()[index],result.asset);renderGrid();openImage(aid);toast('Dropbox original verified; dimensions and full-resolution preview loaded');}
    catch(err){toast(err.message,true);b.textContent='Retry original lookup';}finally{b.disabled=false;}return;
  }
  if(b.dataset.transferImage){openTransfer([b.dataset.transferImage],b.dataset.transferMode);return;}
  if(b.id==='bulk-transfer'){openTransfer([...state.selected]);return;}
  if(b.id==='transfer-history'){showTransferHistory();return;}
  if(b.dataset.undoTransfer){b.disabled=true;try{await api('/api/assignments/undo',{operation_id:b.dataset.undoTransfer});await refreshAfterTransfer();$('#history-dialog').close();toast('Transfer undone');}catch(err){toast(err.message,true);}finally{b.disabled=false;}}
});
document.addEventListener('input',e=>{if(e.target.id==='transfer-search')renderTransferTargets();});
document.addEventListener('change',e=>{if(e.target.id==='transfer-mode')updateTransferMode();});
document.addEventListener('submit',e=>{if(e.target.id==='transfer-form'){e.preventDefault();performTransfer(e.target);}});
