'use strict';
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeURL = value => {try {const u = new URL(value); return u.protocol === 'https:' ? esc(value) : '#';} catch {return '#';}};
const state = {boot:null, current:null, library:null, pid:null, tab:'images', reviews:new Map(), image:null, limit:24, selected:new Set(), dirty:new Set(), request:0, source:'', role:'', use:'', imageSearch:'', scope:'sculpture'};
const key = (kind,pid='',item='') => JSON.stringify([kind,pid,item]);
const review = (kind,pid='',item='') => state.reviews.get(key(kind,pid,item)) || {version:0,data:{}};
const data = (kind,pid='',item='') => review(kind,pid,item).data;
const imageFormBaselines=new Map();
const formSnapshot=form=>JSON.stringify([...new FormData(form).entries()]);
function rememberImageForm(form){imageFormBaselines.set(form.id,formSnapshot(form));state.dirty.delete(form.id);}
function imageFormChanged(form){return imageFormBaselines.get(form.id)!==formSnapshot(form);}
function imageChoices(aid) {
  if(state.pid!=='__library__')return data('image',state.pid,aid);
  const attached=(state.library?.images||[]).find(a=>a.id===aid)?.component_ids||[];
  const records=[...state.reviews.values()].filter(r=>r.kind==='image'&&r.item_id===aid&&(r.product_id==='__library__'||attached.includes(r.product_id)));
  const active=records.filter(r=>r.data.decision==='reviewed');
  return {uses:[...new Set(active.flatMap(r=>r.data.uses||[]))],decision:active.length?'reviewed':records.length&&records.every(r=>r.data.decision==='exclude')?'exclude':'pending',edit_notes:active.some(r=>r.data.edit_notes)?'Requested':''};
}
const readable = value => ({CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED:'Current BOLDSTONE MASTER inventory',CURRENT_ACCEPTED_REFERENCE:'Accepted catalogue reference',RETAINED_SOURCE_SCOPE_SUPPORT:'Retained source relationship',FOLDER_CANDIDATE_REQUIRES_VISUAL_REVIEW:'Folder candidate — check this exact sculpture',HISTORICAL_REFERENCE_ABSENT_FROM_CURRENT_WALL_INVENTORY:'Historical reference — absent from current inventory',SAVED_REFERENCE_OUTSIDE_CURRENT_WALL_INVENTORY_SCOPE:'Reference outside current wall-sculpture inventory'})[value]||String(value||'').replaceAll('_',' ').toLowerCase();
const retainedImages = () => currentImages().filter(image=>image.association?.tier!=='removed');
const currentImages = () => state.pid === '__family__' ? [] : state.pid === '__library__' ? (state.library?.images || []) : (state.current?.images || []);
let toastTimer;
function toast(message, error=false) {const el=$('#toast');el.textContent=message;el.className='show'+(error?' error':'');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.className='',error?9000:3200);}
async function api(path, body) {
  const options = body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json','X-Review-Token':state.boot.csrf_token},body:JSON.stringify(body)};
  if(body!==undefined)state.saving=(state.saving||0)+1;
  try {
    const response = await fetch(path, options);const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Could not complete the request.');
    return result;
  } finally {if(body!==undefined)state.saving--;}
}
function absorb(rows) {for(const r of rows) state.reviews.set(key(r.kind,r.product_id,r.item_id),r);}
async function save(kind,pid,item,values) {
  const result = await api('/api/reviews',{kind,product_id:pid,item_id:item,version:review(kind,pid,item).version,member_versions:review(kind,pid,item).member_versions,data:values});
  state.reviews.set(key(kind,pid,item),result);scheduleCoverageRefresh();return result;
}
function imageURL(image, full=false) {return image.local_preview ? '/api/image?id='+encodeURIComponent(image.id)+'&v='+encodeURIComponent(image.original?.dropbox_content_hash||image.original?.sha256||'retained')+(full?'':'&size=thumb') : image.remote_preview;}
function picture(image, cls='', lazy=true) {const src=imageURL(image);return src ? `<img class="${cls}" src="${esc(src)}" alt="${esc(image.name)}" ${lazy?'loading="lazy"':''}>` : '<div class="placeholder">Preview unavailable<br>Open the source link to inspect</div>';}
function chips(image) {
  const r=imageChoices(image.id), a=data('asset','',image.id);
  return `${image.newly_discovered&&(!r.decision||r.decision==='pending')?'<span class="chip">New from Dropbox</span>':''}${r.primary?'<span class="chip good">Primary</span>':''}${r.decision==='exclude'?'<span class="chip bad">Excluded</span>':(r.uses||[]).map(x=>`<span class="chip good">${esc(x)}</span>`).join('')}${r.edit_notes?'<span class="chip warn">Edit requested</span>':''}${(a.tags||[]).slice(0,3).map(x=>`<span class="chip">${esc(x)}</span>`).join('')}`;
}
function dirtyOK() {return !state.dirty.size || window.confirm('You have unsaved edits. Discard those edits and continue?');}
function navigate(pid) {if(!dirtyOK())return;state.dirty.clear();location.hash=pid==='__library__'?'library':pid;if(state.pid===pid)load(pid);}
async function boot() {
  try {
    state.boot=await api('/api/bootstrap');absorb(state.boot.assignments||[]);
    for(const p of state.boot.products) if(p.review.version)state.reviews.set(key('product',p.id,''),p.review);
    $('#total-products').textContent=state.boot.products.length;
    $('#family-filter').innerHTML='<option value="">All families</option>'+state.boot.families.map(f=>`<option>${esc(f)}</option>`).join('');
    renderList();
    const filters=routeState(),pid=filters.pid;
    await load(pid==='__family__'&&state.boot.families.includes(filters.family)?'__family__':pid==='__library__'?'__library__':state.boot.products.some(p=>p.id===pid)||pid.startsWith('BSI-')?pid:state.boot.products[0].id,filters);
    startDropboxSync();
  } catch(e){$('#main').innerHTML=`<div class="empty-state">${esc(e.message)}<br>Check the local review server and reload.</div>`;}
}
function renderList() {
  const search=$('#search').value.toLowerCase(),family=$('#family-filter').value,filter=$('#review-filter').value;
  const all=state.boot.products;
  const products=all.filter(p=>{
    const r=data('product',p.id);
    return (!family||p.family===family)&&(!search||[p.name,p.family,p.id].join(' ').toLowerCase().includes(search))&&(!filter||(filter==='exclude'?r.decision==='exclude':(r.status||'unreviewed')===filter));
  });
  $('#list-count').textContent=products.length+' of '+all.length;
  $('#review-progress').textContent=all.filter(p=>data('product',p.id).status==='reviewed').length+' of '+all.length+' reviews complete';
  $('#product-list').innerHTML=groupedProductList(products);
}
async function load(pid,filters={}) {
  const request=++state.request;
  state.loading=true;
  state.pid=pid;if(pid==='__family__')state.family=filters.family||state.family;state.selected.clear();state.limit=24;state.source='';state.role='';state.use='';state.imageSearch='';state.scope='sculpture';state.tab='images';
  initImageSort(filters.sort);
  state.libraryFamily=pid==='__library__'?(filters.family||''):'';state.imageFolder=pid==='__library__'?(filters.folder||''):'';
  state.role=Object.hasOwn(typeLabels(),filters.role)||filters.role==='uncategorised'?filters.role:'';
  state.scope=['sculpture','related','all','removed'].includes(filters.scope)?filters.scope:'sculpture';
  state.use=['unreviewed','listing','advertising','social','reference','excluded','unassigned'].includes(filters.use)?filters.use:'';
  $('#main').innerHTML='<div class="loading">Opening images and review notes…</div>';
  $('#sculptures-view').classList.toggle('active',pid!=='__library__');$('#library-view').classList.toggle('active',pid==='__library__');
  try {
    const payload=await api(pid==='__family__'?'/api/coverage':pid==='__library__'?libraryAPI():'/api/products/'+encodeURIComponent(pid));
    if(request!==state.request)return;
    if(pid==='__family__')state.boot.coverage=payload;
    else {absorb(payload.reviews);if(pid==='__library__')state.library=payload;else state.current=payload;}
    renderList();renderMain();
  } catch(e){if(request===state.request)$('#main').innerHTML=`<div class="empty-state">${esc(e.message)}</div>`;}
  finally {if(request===state.request)state.loading=false;}
}
function renderMain() {
  if(state.pid==='__family__'){renderFamily();return;}
  if(state.pid==='__library__') {
    $('#main').innerHTML=`<div class="breadcrumb"><span>Collection / All source images</span><span>${state.library.images.length.toLocaleString()} images</span></div><div class="hero"><div class="hero-copy"><span class="eyebrow">THE IMAGE LIBRARY</span><h1>${state.libraryFamily?esc(state.libraryFamily)+' - all family images':'Every image has a place.'}</h1><p>${state.libraryFamily?'Browse every family photograph, including pairs, groups and installations. Use the folder filter to find the exact components together.':'Keep advertising, social and reference images in tagged collections. This library also includes photographs not yet assigned to an individual sculpture.'}</p>${state.libraryFamily?`<button class="text-button" data-family="${esc(state.libraryFamily)}">Family overview & image checklist →</button>`:''}</div></div><div class="tabs"><button class="active">Image library</button></div><div id="tab-content"></div>`;
  } else {
    const p=state.current,r=data('product',state.pid),images=retainedImages(),selected=images.filter(im=>data('image',state.pid,im.id).decision==='reviewed'&&data('image',state.pid,im.id).uses?.includes('listing')).length;
    $('#main').innerHTML=`<div class="breadcrumb"><span>Wall sculptures / ${esc(p.family)}</span><button class="button subtle" id="next-product">Next sculpture →</button></div><div class="hero"><div class="hero-copy"><span class="eyebrow">INDIVIDUAL SCULPTURE · ${esc(p.id)}</span><h1>${esc(p.name)}</h1><p>${esc(p.sale_unit)}</p><div class="hero-links">${p.folder_url?`<a href="${safeURL(p.folder_url)}" target="_blank" rel="noopener">Containing folder ↗</a>`:''}${p.image_url?`<a href="${safeURL(p.image_url)}" target="_blank" rel="noopener">Current reference ↗</a>`:''}</div></div><div class="review-state"><label for="product-decision">Ultimate listing</label><select id="product-decision"><option value="pending">Not decided</option><option value="include">Include in listing</option><option value="exclude">Exclude from listing</option></select><label for="product-status">Review progress</label><select id="product-status"><option value="unreviewed">Not reviewed</option><option value="in_progress">In progress</option><option value="reviewed">Review complete</option></select></div></div><div class="stats-strip"><div><strong>${images.length}</strong><span>All retained associations</span></div><div><strong id="listing-count">${selected}</strong><span>Selected for listing</span></div><div><strong>${p.fields.filter(x=>x.section!=='Listing copy').length}</strong><span>Specification items</span></div><div><strong id="image-reviewed-count">${images.filter(x=>data('image',state.pid,x.id).decision&&data('image',state.pid,x.id).decision!=='pending').length}</strong><span>Images reviewed</span></div></div><section id="product-coverage" class="product-coverage" aria-label="Product image checklist"></section><div class="tabs"><button data-tab="images" class="${state.tab==='images'?'active':''}">Images <span class="count">${images.length}</span></button><button data-tab="specs" class="${state.tab==='specs'?'active':''}">Specifications</button><button data-tab="listing" class="${state.tab==='listing'?'active':''}">Listing & notes</button></div><div id="tab-content"></div>`;
    $('#product-decision').value=r.decision||'pending';$('#product-status').value=r.status||'unreviewed';
  }
  renderTab();renderProductCoverage();
}
function renderTab(){if(state.tab==='images'||state.pid==='__library__')renderImages();else if(state.tab==='specs')renderSpecs(false);else renderSpecs(true);}
function filteredImages(ignoreType=false,ignoreScope=false) {
  const images=currentImages().filter(im=>{
    const r=imageChoices(im.id),a=data('asset','',im.id);
    const matchedUse=!state.use||(state.use==='unreviewed'?(!r.decision||r.decision==='pending'):state.use==='excluded'?r.decision==='exclude':state.use==='unassigned'?!(im.component_ids||[]).length:(r.uses||[]).includes(state.use));
    return (ignoreScope?im.association?.tier!=='removed':matchScope(im))&&(!state.source||im.source===state.source)&&(ignoreType||matchesImageType(im,state.role))&&(!state.imageFolder||imageFolderKey(im)===state.imageFolder)&&matchedUse&&(!state.imageSearch||[im.name,im.family,im.folder_label,a.collection,...imageTypes(im).map(t=>typeLabels()[t]),...(a.tags||[])].join(' ').toLowerCase().includes(state.imageSearch.toLowerCase()));
  });
  return ignoreType||ignoreScope?images:sortImages(images);
}
function defaultImageOrder(images){
  return [...images].sort((a,b)=>{
    if(state.pid==='__library__')return state.libraryFamily?(a.folder_label||'').localeCompare(b.folder_label||'')||a.name.localeCompare(b.name,undefined,{numeric:true}):0;
    const x=imageChoices(a.id),y=imageChoices(b.id);
    const rank=r=>r.primary?0:r.decision!=='exclude'&&r.uses?.includes('listing')?1:2;
    return rank(x)-rank(y)||(rank(x)<2?(x.order||0)-(y.order||0):0);
  });
}
function renderImages() {
  const images=currentImages();
  $('#tab-content').innerHTML=`${dedupeNotice()}<div class="family-folder-toolbar">${folderControls()}</div><div id="image-scope-summary" class="image-scope-summary"></div><section id="image-categories" class="image-categories" aria-label="Image categories"></section><div class="toolbar">${scopeControls()}<select id="image-source" aria-label="Filter image source"><option value="">All sources</option>${[...new Set(images.map(x=>x.source))].map(x=>`<option>${esc(x)}</option>`).join('')}</select><select id="image-role" aria-label="Filter image type"><option value="">All image types</option><option value="uncategorised">Uncategorised</option>${Object.entries(typeLabels()).map(([value,label])=>`<option value="${esc(value)}">${esc(label)}</option>`).join('')}</select><select id="image-use" aria-label="Filter image use"><option value="">All review choices</option><option value="unreviewed">Not reviewed</option><option value="listing">Listing</option><option value="advertising">Advertising</option><option value="social">Social</option><option value="reference">Reference only</option><option value="excluded">Excluded</option>${state.pid==='__library__'?'<option value="unassigned">No component chosen</option>':''}</select><input id="image-search" aria-label="Search image names and tags" placeholder="Find image, tag or collection…" value="${esc(state.imageSearch)}"><span class="spacer"></span><span id="shown-count"></span></div>${sortControls()}<p class="info-line">${state.pid==='__library__'?'Use Components, Listing or Ads on a card to choose the sculptures and their uses. In situ and image types follow the same photo across every component.':'This sculpture shows accepted references and images from their Dropbox folders. Related candidates holds broader family, other-finish and platform galleries for checking. Selecting a candidate for listing adds it here; excluding it keeps it in the candidate queue.'}</p><div class="bulk-bar" id="bulk-bar" hidden><strong id="bulk-count"></strong>${state.pid!=='__library__'?'<button class="button" data-bulk="listing">Listing</button>':''}<button class="button" data-bulk="advertising">${state.pid==='__library__'?'Library ads':'Advertising'}</button><button class="button" data-bulk="reference">Reference</button><button class="button" data-bulk="exclude">Exclude</button><button class="button" id="bulk-transfer">Move / copy…</button><button class="button danger" id="bulk-delete">Delete…</button><button class="button subtle" id="clear-selection">Clear</button></div><div id="image-grid" class="grid"></div><button id="load-more" class="button load-more">Show more images</button>`;
  if($('#image-folder'))$('#image-folder').value=state.imageFolder;if($('#image-scope'))$('#image-scope').value=state.scope;$('#image-source').value=state.source;$('#image-role').value=state.role;$('#image-use').value=state.use;renderGrid();
}
function renderGrid() {
  if(!$('#image-grid'))return;
  const images=filteredImages(),visible=images.slice(0,state.limit);
  $('#shown-count').textContent=visible.length+' of '+images.length;
  $('#image-grid').innerHTML=visible.map(im=>{
    const r=imageChoices(im.id), uses=r.uses||[],buttonUses=data('image',state.pid,im.id).uses||[],removed=im.association?.tier==='removed';
    return `<article class="image-card ${r.decision==='exclude'?'excluded':uses.length?'chosen':''}" data-asset="${esc(im.id)}">
      <div class="image-stage" data-open-image="${esc(im.id)}"><label class="select-box"><input type="checkbox" data-select-image="${esc(im.id)}" aria-label="Select ${esc(im.name)}" ${state.selected.has(im.id)?'checked':''}></label><span class="source-pill">${esc(im.source)}</span>${picture(im)}</div>
      <div class="image-card-body"><div class="role-line"><span class="role-name">${esc(imageTypes(im).map(t=>typeLabels()[t]).join(' · ')||'Type not assigned')}</span>${r.decision==='reviewed'?'<span class="muted">✓ Reviewed</span>':''}</div>
      <p class="image-name" title="${esc(im.name)}">${esc(im.name)}</p><p class="image-size">${esc(originalSize(im,true))}</p>
      <p class="association-label">${esc(state.pid==='__library__'?im.folder_label||im.family:tierLabel(im))}</p>${componentCard(im)}${cardTypeControls(im)}<div class="chips">${chips(im)}${im.duplicate_count?`<span class="chip">${im.duplicate_count} identical ${im.duplicate_count===1?'copy':'copies'} filtered</span>`:''}${im.duplicate_conflicts?.length?'<span class="chip warn">Conflicting duplicate reviews</span>':''}</div>${r.notes?`<p class="review-reason" title="${esc(r.notes)}">${esc(r.notes)}</p>`:''}</div>
      ${imageActions(im)}</article>`;
  }).join('')||'<div class="empty-state">No images match these filters.<br>Try Related candidates, another type or a different tag.</div>';
  $('#load-more').hidden=visible.length>=images.length;$('#bulk-bar').hidden=!state.selected.size;$('#bulk-count').textContent=state.selected.size+' selected';
  updateCounts();renderCategories();updateScopeSummary();updateFilterRoute();updateSortStatus();
}
function updateCounts(){if($('#listing-count'))$('#listing-count').textContent=retainedImages().filter(x=>data('image',state.pid,x.id).decision==='reviewed'&&data('image',state.pid,x.id).uses?.includes('listing')).length;if($('#image-reviewed-count'))$('#image-reviewed-count').textContent=retainedImages().filter(x=>['reviewed','exclude'].includes(data('image',state.pid,x.id).decision)).length;}
function fieldHTML(f) {
  const r=review('field',state.pid,f.key),v=r.data,id='field-'+encodeURIComponent(f.key);
  const listingValue=v.decision==='exclude'?'Omitted from listing':(v.decision==='edit'?v.value:f.value).replaceAll('\u2014','-');
  return `<article class="spec-card"><div class="spec-card-head"><h3>${esc(f.label)}</h3><span class="chip ${v.decision==='exclude'?'bad':v.decision&&v.decision!=='pending'?'good':''}" data-field-badge="${esc(f.key)}">${esc(v.decision||'Not reviewed')}</span></div><div class="spec-grid"><div><div class="field-label">${r.version?'Saved listing value':'Current value'}</div><p class="original" data-listing-value="${esc(f.key)}">${esc(listingValue||'Not yet written')}</p><details class="source-detail"><summary>Original source and qualification</summary><p>${esc(f.value||'No original value recorded.')}</p><p>${esc(f.qualification||'No extra qualification recorded.')}</p><p>${esc(f.basis)}</p></details></div><form class="spec-form" id="${id}" data-field="${esc(f.key)}"><div class="field-label">Your listing choice</div><div class="spec-controls"><select name="decision" aria-label="${esc(f.label)} decision"><option value="pending">Not decided</option><option value="keep">Keep source value</option><option value="edit">Use edited value</option><option value="exclude">Omit from listing</option></select><select name="certainty" aria-label="${esc(f.label)} certainty"><option value="retain">Retain source qualification</option><option value="estimate">Working value</option><option value="source_claim">Source claim</option><option value="confirmed">Confirmed with evidence</option></select></div><textarea name="value" aria-label="Edit ${esc(f.label)}" placeholder="Enter the value you want on the listing…">${esc(v.value??f.value)}</textarea><textarea name="notes" aria-label="Feedback for ${esc(f.label)}" placeholder="Feedback or a correction to check…">${esc(v.notes||'')}</textarea><input type="text" name="evidence" aria-label="Evidence for ${esc(f.label)}" placeholder="Evidence / measurement / confirmation (if applicable)" value="${esc(v.evidence||'')}"><div class="footer"><span class="save-state">${r.version?'Saved locally':'Not yet reviewed'}</span><button class="button" type="submit">Save item</button></div></form></div></article>`;
}
function renderSpecs(listing) {
  const fields=state.current.fields.filter(f=>(f.section==='Listing copy')===listing),sections=[...new Set(fields.map(f=>f.section))];
  $('#tab-content').innerHTML=(listing?'':`<p class="info-line spec-section">Keep, edit or omit each item. Listing text is separate from the original source and qualification. Confirmed values need an evidence note; working values are not recorded as measurements.</p>`)+sections.map(section=>`<section class="spec-section"><div class="section-title"><h3>${esc(section)}</h3><span class="small muted">Saved per item</span></div>${fields.filter(f=>f.section===section).map(fieldHTML).join('')}</section>`).join('')+(listing?`<section class="notes-panel"><h3>Private review notes</h3><form id="product-notes"><textarea name="notes" aria-label="Private product review notes" placeholder="Anything to resolve before this sculpture goes online…">${esc(data('product',state.pid).notes||'')}</textarea><button class="button" type="submit">Save notes</button><span class="save-state"></span></form><p class="fact"><strong>Catalogue context</strong><br>${esc(state.current.source_notes||'Existing component and finish identities are retained.')}</p><p class="small muted">Local edits are review decisions. Export them when you are ready to update the catalogue or an online store.</p></section>`:'');
  for(const form of $$('.spec-form')){const d=data('field',state.pid,form.dataset.field);form.elements.decision.value=d.decision||'pending';form.elements.certainty.value=d.certainty||'retain';}
}
async function quick(aid, use, mode='toggle', pid=state.pid) {
  const d={...data('image',pid,aid)};
  const uses=new Set(d.decision==='exclude'?[]:(d.uses||[]));
  if(use==='exclude')uses.clear();
  else if(mode==='toggle'&&uses.has(use))uses.delete(use);
  else uses.add(use);
  d.decision=use==='exclude'?'exclude':'reviewed';d.uses=[...uses];
  if(!uses.has('listing'))d.primary=false;
  await save('image',pid,aid,d);
}
function openImage(aid) {
  if($('#image-dialog').open&&!closeImage())return;
  const image=currentImages().find(x=>x.id===aid);if(!image)return;
  state.image=image;const r=data('image',state.pid,aid),a=data('asset','',aid),association=image.association;
  $('#image-detail').innerHTML=`<div class="detail-layout"><div class="detail-photo"><div class="detail-photo-top"><button class="button" data-image-nav="-1" aria-label="Previous image">←</button><button class="button" data-image-nav="1" aria-label="Next image">→</button><span class="spacer"></span>${image.url?`<a href="${safeURL(image.url)}" target="_blank" rel="noopener">Source image ↗</a>`:'<span class="muted">Historical reference · source unavailable</span>'}${image.folder_url?`<a href="${safeURL(image.folder_url)}" target="_blank" rel="noopener">Folder ↗</a>`:''}</div><div class="detail-photo-view">${imageURL(image,true)?`<img src="${esc(imageURL(image,true))}" alt="${esc(image.name)}">`:'<div class="placeholder">No local preview is available.<br>Open the source image above.</div>'}</div><div class="detail-photo-foot">${sizePanel(image)}<strong>${esc(image.name)}</strong><br>${esc(image.source)} · ${esc(image.role)} · ${esc(image.representation)}<br>${esc(readable(image.inventory_status))}${association?'<br>'+esc(association.qualifications.map(readable).join(' · ')):''}<br><span class="small">${esc(image.id)}</span>${duplicateDetails(image)}</div></div><div class="detail-controls"><button class="close" data-close="image-dialog" aria-label="Close image">×</button><span class="eyebrow">IMAGE REVIEW</span><h3>A place for this picture</h3><button class="button transfer-action" data-transfer-image="${esc(aid)}">Move / copy to another title</button><p class="small muted">${state.pid==='__library__'?'Library use only. Listing choices belong to a sculpture.':'These uses apply to '+esc(state.current.name)+'.'}</p><div class="preset-buttons">${state.pid!=='__library__'?'<button data-preset="listing">Listing only</button>':''}<button data-preset="advertising">Advertising only</button><button data-preset="reference">Reference only</button><button data-preset="exclude">Exclude</button></div><form id="image-form"><label for="image-decision">Decision</label><select id="image-decision" name="decision"><option value="pending">Not reviewed</option><option value="reviewed">Reviewed — choose uses below</option><option value="exclude">Exclude from every use here</option></select>${['listing','advertising','social','reference'].filter(x=>x!=='listing'||state.pid!=='__library__').map(x=>`<label class="check-line"><input type="checkbox" name="use" value="${x}" ${(r.uses||[]).includes(x)?'checked':''}>${({listing:'Product listing',advertising:'Advertising / campaigns',social:'Social media',reference:'Internal reference'})[x]}</label>`).join('')}${state.pid!=='__library__'?`<label class="check-line"><input name="primary" type="checkbox" ${r.primary?'checked':''}>Primary listing photograph</label>`:''}<label>Display order<input type="number" name="order" min="0" max="10000" value="${r.order||0}"></label><label>Alt text<input type="text" name="alt" value="${esc(r.alt||'')}" placeholder="Describe the sculpture and image"></label><label>Caption<textarea name="caption">${esc(r.caption||'')}</textarea></label><label>Image edits requested<textarea name="edit_notes" placeholder="For example: crop the edge, remove the label, correct the colour…">${esc(r.edit_notes||'')}</textarea></label><p class="small muted">Requests are saved for editing; this does not change the picture.</p><label>Feedback / exclusion reason<textarea name="notes">${esc(r.notes||'')}</textarea></label><button class="button dark" type="submit">Save all image changes</button><p class="save-state"></p></form><hr class="divider"><span class="eyebrow">SHARED IMAGE ORGANISATION</span><p class="small muted">Tags follow this file across every sculpture. Useful for finding advertising and reference images later.</p><form id="asset-form">${typeControls(image)}<label>Tags, separated by commas<input type="text" name="tags" value="${esc((a.tags||[]).join(', '))}" placeholder="campaign, garden, detail, workshop…"></label><label>Collection / campaign<input type="text" name="collection" value="${esc(a.collection||'')}" placeholder="For example: Autumn interiors"></label><label>Usage rights<select name="rights"><option value="unknown">Not checked</option><option value="owned">Our photograph</option><option value="permission">Permission recorded</option><option value="restricted">Restricted / do not publish</option></select></label><label>Shared image notes<textarea name="notes">${esc(a.notes||'')}</textarea></label><button class="button" type="submit">Save all image changes</button><p class="save-state"></p></form></div></div>`;
  if(image.association?.tier==='removed'){$$('#image-form input,#image-form textarea,#image-form select,#image-form button').forEach(el=>el.disabled=true);}
  $('#image-decision').value=r.decision||'pending';$('#asset-form').elements.rights.value=a.rights||'unknown';
  rememberImageForm($('#image-form'));rememberImageForm($('#asset-form'));$('#image-dialog').showModal();
  renderDeleteControl(image);
}
function closeImage() {
  if(state.savingImage){toast('Image changes are still saving. Please wait.');return false;}
  const changed=['image-form','asset-form'].some(id=>$('#'+id)&&imageFormChanged($('#'+id)));
  if(changed&&!window.confirm('Discard unsaved image edits?'))return false;
  state.dirty.delete('image-form');state.dirty.delete('asset-form');$('#image-dialog').close();state.image=null;return true;
}
function setImagePreset(use) {const form=$('#image-form');form.elements.decision.value=use==='exclude'?'exclude':'reviewed';$$('input[name=use]',form).forEach(x=>x.checked=x.value===use);if(form.elements.primary&&use!=='listing')form.elements.primary.checked=false;markDirty(form);}
function markDirty(form) {
  if(!form||['transfer-form','delete-choice-form','delete-confirm-form','bulk-delete-choice-form','bulk-delete-confirm-form'].includes(form.id))return;
  const changed=!['image-form','asset-form'].includes(form.id)||imageFormChanged(form);
  if(changed)state.dirty.add(form.id);else state.dirty.delete(form.id);
  const el=$('.save-state',form);if(el)el.textContent=changed?'Unsaved changes':'No unsaved changes';
}
async function saveImageDetails(trigger) {
  state.savingImage=true;const buttons=$$('#image-form button[type=submit],#asset-form button[type=submit]');buttons.forEach(b=>b.disabled=true);
  const forms=[$('#image-form'),$('#asset-form')];forms.forEach(f=>{f.inert=true;f.setAttribute('aria-busy','true');});
  try{
    const form=$('#image-form'),f=form.elements;
    if(!f.decision.disabled&&(trigger==='image-form'||imageFormChanged(form))){
      const values={decision:f.decision.value,uses:$$('input[name=use]:checked',form).map(x=>x.value),primary:f.primary?.checked||false,order:Number(f.order.value),alt:f.alt.value,caption:f.caption.value,edit_notes:f.edit_notes.value,notes:f.notes.value};
      const saved=await save('image',state.pid,state.image.id,values);
      f.decision.value=saved.data.decision||'pending';
      $$('input[name=use]',form).forEach(x=>x.checked=(saved.data.uses||[]).includes(x.value));
      if(f.primary)f.primary.checked=!!saved.data.primary;
      rememberImageForm(form);
      if(values.primary){const updated=await api('/api/products/'+encodeURIComponent(state.pid));absorb(updated.reviews);}
    }
    const tags=$('#asset-form'),a=tags.elements;
    if(trigger==='asset-form'||imageFormChanged(tags)){
      await save('asset','',state.image.id,{tags:[...new Set(a.tags.value.split(',').map(x=>x.trim()).filter(Boolean))],collection:a.collection.value,rights:a.rights.value,notes:a.notes.value,types:$$('input[name=image_type]:checked',tags).map(x=>x.value)});rememberImageForm(tags);
    }
    for(const el of $$('#image-form .save-state,#asset-form .save-state'))el.textContent='All image changes saved';
    renderGrid();renderList();toast('Image choices and tags saved');
  }finally{state.savingImage=false;forms.forEach(f=>{f.inert=false;f.removeAttribute('aria-busy');});buttons.forEach(b=>b.disabled=false);}
}
async function submitForm(form) {
  const button=$('button[type=submit]',form),pid=state.pid,request=state.request;button.disabled=true;
  try {
    if(['image-form','asset-form'].includes(form.id)){await saveImageDetails(form.id);return;}
    if(form.matches('.spec-form')){
      const values=Object.fromEntries(new FormData(form));
      await save('field',pid,form.dataset.field,values);
      if(pid!==state.pid||request!==state.request){toast('Specification saved for the original sculpture');return;}
      if(form.dataset.field==='Name'){const name=values.decision==='edit'?values.value:state.current.original_name;state.current.name=name;state.boot.products.find(p=>p.id===state.pid).name=name;$('.hero h1').textContent=name;}
      const badge=$('[data-field-badge]',form.closest('.spec-card'));badge.textContent=values.decision;badge.className='chip '+(values.decision==='exclude'?'bad':values.decision!=='pending'?'good':'');
      const savedValue=$('[data-listing-value]',form.closest('.spec-card'));
      savedValue.textContent=values.decision==='exclude'?'Omitted from listing':(values.decision==='edit'?values.value:state.current.fields.find(f=>f.key===form.dataset.field).value).replaceAll('\u2014','-');
      savedValue.previousElementSibling.textContent='Saved listing value';
    } else if(form.id==='product-notes') {
      await save('product',pid,'',{...data('product',pid),notes:form.elements.notes.value});
      if(pid!==state.pid||request!==state.request){toast('Notes saved for the original sculpture');return;}
    }
    state.dirty.delete(form.id);const status=$('.save-state',form);if(status)status.textContent='Saved locally · '+new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});toast('Saved locally');renderList();
  } catch(e){toast(e.message,true);}finally{button.disabled=false;}
}
document.addEventListener('submit',e=>{if(e.target.matches('.spec-form,#image-form,#asset-form,#product-notes')){e.preventDefault();submitForm(e.target);}});
document.addEventListener('input',e=>{const form=e.target.closest('form');if(form&&form.id!=='transfer-form')markDirty(form);if(e.target.id==='search')renderList();if(e.target.id==='image-search'){state.imageSearch=e.target.value;state.limit=24;renderGrid();}});
document.addEventListener('change',async e=>{
  const el=e.target;const form=el.closest('form');if(form&&form.id!=='transfer-form')markDirty(form);
  if(['family-filter','review-filter'].includes(el.id))renderList();
  if(['image-source','image-role','image-use','image-scope'].includes(el.id)){state[{'image-source':'source','image-role':'role','image-use':'use','image-scope':'scope'}[el.id]]=el.value;state.limit=24;state.selected.clear();renderGrid();}
  if(el.dataset.selectImage){el.checked?state.selected.add(el.dataset.selectImage):state.selected.delete(el.dataset.selectImage);renderGrid();}
  if(['product-decision','product-status'].includes(el.id)){
    el.disabled=true;
    try{await save('product',state.pid,'',{...data('product',state.pid),decision:$('#product-decision').value,status:$('#product-status').value});renderList();toast('Product choice saved locally');}
    catch(err){toast(err.message,true);el.value=data('product',state.pid)[el.id==='product-decision'?'decision':'status']|| (el.id==='product-decision'?'pending':'unreviewed');}finally{el.disabled=false;}
  }
  if(el.closest('#image-form')&&(el.name==='use'||el.name==='primary')){
    if(el.checked)$('#image-decision').value='reviewed';
    if(el.name==='use'&&el.value==='listing'&&!el.checked&&form.elements.primary)form.elements.primary.checked=false;
    if(el.name==='primary'&&el.checked){const listing=$('input[name=use][value=listing]',$('#image-form'));if(listing)listing.checked=true;}
  }
  if(el.id==='image-decision'&&el.value!=='reviewed'&&form.elements.primary)form.elements.primary.checked=false;
  if(el.id==='image-decision'&&el.value==='exclude')setImagePreset('exclude');
});
document.addEventListener('click',async e=>{
  const target=e.target.closest('button,[data-open-image]');if(!target)return;
  if(e.target.closest('.select-box'))return;
  if(target.dataset.product){navigate(target.dataset.product);return;}
  if(target.id==='library-view'){navigate('__library__');return;}
  if(target.id==='sculptures-view'){navigate(state.current?.id||state.boot.products[0].id);return;}
  if(target.id==='next-product'){const list=state.boot.products,index=list.findIndex(p=>p.id===state.pid);navigate(list[(index+1)%list.length].id);return;}
  if(target.dataset.tab){if(!dirtyOK())return;state.dirty.clear();state.tab=target.dataset.tab;$$('[data-tab]').forEach(x=>x.classList.toggle('active',x===target));renderTab();return;}
  if(target.dataset.openImage){openImage(target.dataset.openImage);return;}
  if(target.dataset.close){target.dataset.close==='image-dialog'?closeImage():$('#'+target.dataset.close).close();return;}
  if(target.dataset.preset){setImagePreset(target.dataset.preset);return;}
  if(target.dataset.imageNav){const list=filteredImages(),index=list.findIndex(x=>x.id===state.image.id);openImage(list[(index+Number(target.dataset.imageNav)+list.length)%list.length].id);return;}
  if(target.id==='load-more'){state.limit+=24;renderGrid();return;}
  if(target.id==='clear-selection'){state.selected.clear();renderGrid();return;}
  if(target.dataset.quick||target.dataset.bulk){
    const pid=state.pid,request=state.request,ids=target.dataset.bulk?[...state.selected]:[target.dataset.id];
    const bulk=!!target.dataset.bulk;let completed=0;target.disabled=true;
    try{
      for(const aid of ids){await quick(aid,target.dataset.bulk||target.dataset.quick,bulk?'add':'toggle',pid);completed++;}
      toast(ids.length+' image choice'+(ids.length===1?'':'s')+' saved locally');
    }catch(err){toast((completed?completed+' saved; remaining choices were not saved. ':'')+err.message,true);}
    finally{
      if(pid===state.pid&&request===state.request){if(bulk)for(const aid of ids.slice(0,completed))state.selected.delete(aid);renderGrid();}
      target.disabled=false;
    }
    return;
  }
  if(target.id==='export-open'){$('#export-dialog').showModal();return;}
  if(target.id==='export-run'){
    if(state.dirty.size){toast('Save or discard your unsaved edits before exporting.',true);return;}
    target.disabled=true;target.textContent='Creating bundle…';$('#export-result').textContent='Saving your decisions and preparing the export.';
    try {const result=await api('/api/export',{include_media:$('#include-media').checked});$('#export-result').innerHTML=`<strong>Export saved.</strong> ${result.review_decisions} decisions · ${result.included} products selected · ${result.listing_ready} listing-ready.<br><a class="button green" href="${esc(result.download_url)}" download>Download review bundle ↓</a><p class="small muted">Saved at ${esc(result.path)}</p>`;}
    catch(err){$('#export-result').textContent=err.message;}finally{target.disabled=false;target.textContent='Create review bundle';}
  }
});
document.addEventListener('error',e=>{if(e.target.tagName==='IMG'){const p=document.createElement('div');p.className='placeholder';p.textContent='Preview unavailable — open the source link';e.target.replaceWith(p);}},true);
$('#image-dialog').addEventListener('cancel',e=>{e.preventDefault();closeImage();});
window.addEventListener('beforeunload',e=>{if(state.dirty.size){e.preventDefault();e.returnValue='';}});
window.addEventListener('hashchange',()=>{
  const filters=routeState(),pid=filters.pid;
  if(!dirtyOK()){history.replaceState(null,'','#'+(state.pid==='__library__'?'library':state.pid));return;}
  state.dirty.clear();if(pid)load(pid,filters);
});
boot();
