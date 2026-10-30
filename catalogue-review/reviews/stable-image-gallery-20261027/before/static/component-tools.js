'use strict';
let componentReview=null,componentOpening=false,componentView=0;
const componentChoiceKeys=['shown','listing','advertising'];
const componentCount=(image,use)=>(image.component_ids||[]).filter(pid=>data('image',pid,image.id).decision==='reviewed'&&data('image',pid,image.id).uses?.includes(use)).length;
function componentCard(image){
  const ids=image.component_ids||[],names=ids.map(pid=>state.boot.products.find(p=>p.id===pid)?.name).filter(Boolean);
  const library=data('image','__library__',image.id),libraryUses=library.decision==='reviewed'?library.uses||[]:[];
  return `<div class="component-card"><span>${names.length?'Shown with: '+esc(names.join(' · ')):'No component chosen yet'}</span><button class="text-button" data-components="${esc(image.id)}">Components (${names.length}) / uses</button><button class="text-button" data-overview-image="${esc(image.id)}">Photos & specs</button>${image.default_component_ids?.length?'<small>Group-folder defaults; choose the pieces visible in this photo.</small>':''}${state.pid==='__library__'&&libraryUses.length?`<small>Library-only use: ${esc(libraryUses.join(', '))}</small>`:''}</div>`;
}
function imageActions(image){
  const aid=esc(image.id),removed=image.association?.tier==='removed',library=state.pid==='__library__';
  const uses=activeImageUses(data('image',state.pid,image.id)),situ=imageTypes(image).includes('in_situ');
  const total=(image.component_ids||[]).length;
  const componentButton=(use,label)=>{const count=componentCount(image,use);return `<button data-components="${aid}" data-component-purpose="${use}" class="${count?'selected':''}" aria-pressed="${count&&count<total?'mixed':Boolean(count)}" title="Choose components and ${label.toLowerCase()} use">${label}${total?' '+count+'/'+total:''}</button>`;};
  return `<div class="quick-actions">${removed?`<button data-transfer-image="${aid}" data-transfer-mode="restore">Restore</button>`:library?componentButton('listing','Listing')+componentButton('advertising','Ads'):`<button data-quick="listing" data-id="${aid}" class="${uses.includes('listing')?'selected':''}" aria-pressed="${uses.includes('listing')}" title="Toggle listing use for this sculpture">Listing</button><button data-quick="advertising" data-id="${aid}" class="${uses.includes('advertising')?'selected':''}" aria-pressed="${uses.includes('advertising')}" title="Toggle advertising use for this sculpture">Ads</button>`}<button data-in-situ="${aid}" class="${situ?'selected':''}" aria-pressed="${situ}" title="Toggle the shared In situ image type; listing and ads choices stay separate">In situ</button>${removed?'':`<button data-quick="exclude" data-id="${aid}" title="${library?'Exclude library uses; component choices are managed with Components':'Clear uses for this sculpture; keep the original file'}">${library?'Library exclude':'Exclude'}</button>`}<button data-transfer-image="${aid}" title="Move or copy to another sculpture">Move</button><button data-open-image="${aid}">Review ↗</button></div>`;
}
const componentChanges=()=>componentReview?componentReview.rows.filter(row=>componentChoiceKeys.some(k=>row[k]!==componentReview.original.get(row.product_id)[k])):[];
function updateComponentDirty(){
  const changes=componentChanges();changes.length?state.dirty.add('component-review'):state.dirty.delete('component-review');
  const button=$('#component-save');if(button)button.disabled=!changes.length||componentReview?.saving;
}
async function openComponents(aid,purpose){
  if(componentOpening||componentReview?.saving)return;
  if(state.dirty.size){toast('Save your current edits before choosing components.',true);return;}
  if($('#image-dialog').open&&!closeImage())return;
  componentOpening=true;componentReview=null;
  const request=state.request,view=++componentView,dialog=$('#component-dialog');
  const isCurrent=()=>view===componentView&&dialog.open;
  dialog.innerHTML='<button class="close" id="component-close" aria-label="Close component choices">×</button><span class="eyebrow">ONE PHOTO, SEVERAL SCULPTURES</span><h2>Components and image uses</h2><p class="loading" role="status">Loading component choices…</p><button class="button" id="component-cancel">Cancel</button>';
  dialog.setAttribute('aria-busy','true');dialog.showModal();
  try{
    const result=await api('/api/image-components?id='+encodeURIComponent(aid));
    if(!isCurrent())return;
    if(request!==state.request){closeComponents(true);return;}
    componentReview={...result,original:new Map(result.rows.map(row=>[row.product_id,{...row}])),search:'',saving:false};
    if(purpose){
      const targets=componentReview.rows.filter(r=>r.shown&&!r.excluded),remove=targets.length&&targets.every(r=>r[purpose]);
      for(const row of targets)row[purpose]=!remove;
    }
    const image=componentReview.image;
    $('#component-dialog').innerHTML=`<button class="close" id="component-close" aria-label="Close component choices">×</button><span class="eyebrow">ONE PHOTO, SEVERAL SCULPTURES</span><h2>Components and image uses</h2><div class="component-layout"><div class="component-photo">${picture(image,'',false)}<strong>${esc(image.name)}</strong><p class="small">${image.url?`<a href="${safeURL(image.url)}" target="_blank" rel="noopener">Image ↗</a>`:''}${image.folder_url?` · <a href="${safeURL(image.folder_url)}" target="_blank" rel="noopener">Folder ↗</a>`:''}</p><p class="small muted">${imageTypes(image).map(t=>esc(typeLabels()[t]||t)).join(' · ')||'Image type not assigned'}</p></div><div class="component-options"><p><strong>Show</strong> places this photo under the selected sculpture. <strong>Listing</strong> and <strong>Ads</strong> choose its uses for that sculpture; both can be selected.</p><p class="small muted">Group-folder defaults include only explicitly named components. Check which pieces are visible, especially in detail shots. In situ is a shared image type. Saving component choices queues one Dropbox move into their combined folder; no extra original is copied.</p><label class="component-search">Find another component<input id="component-search" type="search" placeholder="Search all sculptures or finishes…"></label><div class="component-table-wrap"><table class="component-table"><thead><tr><th>Component</th><th>Show</th><th>Listing</th><th>Ads</th></tr></thead><tbody id="component-rows"></tbody></table></div><p class="small muted">Unchecking Show also clears Listing and Ads for that component. The original stays a single file. Its Dropbox folder and filename follow the selected components and image types; track progress in Jobs.</p><div id="component-result" role="status"></div><div class="component-save-actions"><button class="button dark" id="component-save">Save component choices</button><button class="button" id="component-cancel">Cancel</button></div></div></div>`;
    renderComponentRows();updateComponentDirty();
  }catch(error){
    if(!isCurrent())return;
    if(request!==state.request){closeComponents(true);return;}
    dialog.innerHTML=`<button class="close" id="component-close" aria-label="Close component choices">×</button><span class="eyebrow">ONE PHOTO, SEVERAL SCULPTURES</span><h2>Components and image uses</h2><p role="alert">${esc(error.message)}</p><button class="button dark" data-components="${esc(aid)}" ${purpose?`data-component-purpose="${esc(purpose)}"`:''}>Retry</button><button class="button" id="component-cancel">Cancel</button>`;
  }finally{if(view===componentView){componentOpening=false;dialog.removeAttribute('aria-busy');}}
}
function renderComponentRows(){
  const c=componentReview,q=c.search.toLowerCase(),family=c.image.family;
  const rows=c.rows.filter(r=>q?[r.name,r.family].join(' ').toLowerCase().includes(q):r.family===family||r.shown||r.default||r.removed)
    .sort((a,b)=>a.family.localeCompare(b.family)||a.name.localeCompare(b.name,undefined,{numeric:true}));
  $('#component-rows').innerHTML=rows.map(row=>`<tr><td><strong>${esc(row.name)}</strong><small>${esc(row.family)} · ${row.default?'Named in group folder':row.shown?'Shown under this component':row.removed?'Removed by you':'Not shown under this component'}${row.excluded?' · Existing exclusion':''}</small></td>${componentChoiceKeys.map(key=>`<td><input type="checkbox" data-component-pid="${esc(row.product_id)}" data-component-choice="${key}" aria-label="${key==='shown'?'Show':key==='listing'?'Listing':'Ads'} for ${esc(row.name)}" ${row[key]?'checked':''}></td>`).join('')}</tr>`).join('')||'<tr><td colspan="4">No matching components. Search by another name or finish.</td></tr>';
}
function closeComponents(discard=false){
  if(componentReview?.saving)return;
  if(!discard&&componentChanges().length&&!window.confirm('Discard the unsaved component choices?'))return;
  ++componentView;componentOpening=false;
  state.dirty.delete('component-review');componentReview=null;$('#component-dialog').removeAttribute('aria-busy');$('#component-dialog').close();
}
async function saveComponents(){
  if(!componentReview||componentReview.saving)return;
  const changes=componentChanges();if(!changes.length)return;
  componentReview.saving=true;updateComponentDirty();
  const controls=$$('input,button',$('#component-dialog'));controls.forEach(el=>el.disabled=true);
  $('#component-result').textContent='Saving choices for '+changes.length+' component(s)…';
  let committed=false;
  try{
    await api('/api/image-components',{asset_id:componentReview.image.id,content_hash:componentReview.content_hash,rows:changes});
    committed=true;
    state.dirty.delete('component-review');componentReview.saving=false;closeComponents(true);
    await refreshAfterTransfer();toast('Component choices saved. Dropbox organisation is queued in Jobs.');
  }catch(error){
    if(committed){toast('Component choices were saved. Reload the gallery to see them.',true);return;}
    $('#component-result').textContent=error.message;componentReview.saving=false;
    controls.forEach(el=>el.disabled=false);updateComponentDirty();
  }
}
async function toggleInSitu(button){
  const image=currentImages().find(a=>a.id===button.dataset.inSitu);if(!image)return;
  button.disabled=true;
  const types=imageTypes(image),add=!types.includes('in_situ');
  try{
    await save('asset','',image.id,{...data('asset','',image.id),types:add?[...types,'in_situ']:types.filter(t=>t!=='in_situ')});
    renderGrid();toast(add?'In situ added. Dropbox organisation is queued in Jobs':'In situ removed. Dropbox organisation is queued; listing and ads retained');
  }catch(error){toast(error.message,true);}finally{button.disabled=false;}
}
document.addEventListener('click',e=>{
  const button=e.target.closest('button');if(!button)return;
  if(button.dataset.components)openComponents(button.dataset.components,button.dataset.componentPurpose);
  if(button.dataset.inSitu)toggleInSitu(button);
  if(button.id==='component-save')saveComponents();
  if(button.id==='component-close')closeComponents();
  if(button.id==='component-cancel')closeComponents(true);
});
document.addEventListener('input',e=>{if(e.target.id==='component-search'){componentReview.search=e.target.value;renderComponentRows();}});
document.addEventListener('change',e=>{
  const el=e.target;if(!el.dataset.componentChoice)return;
  const row=componentReview.rows.find(r=>r.product_id===el.dataset.componentPid),key=el.dataset.componentChoice;
  row[key]=el.checked;
  if(key==='shown'&&!el.checked){row.listing=false;row.advertising=false;}
  if(key!=='shown'&&el.checked)row.shown=true;
  renderComponentRows();updateComponentDirty();
});
document.addEventListener('cancel',e=>{if(e.target.id==='component-dialog'){e.preventDefault();closeComponents();}},true);
