'use strict';
let bulkDeletion=null;
const deletableOriginal=image=>image.source==='Dropbox'&&image.id.startsWith('id:')&&image.original?.dropbox_content_hash&&image.original?.bytes;
const imageMemberIDs=image=>[image.id,...(image.duplicates||[]).map(a=>a.id)];
function bulkDeleteKeepers(batch){
  const selected=new Set(batch.entries.flatMap(e=>imageMemberIDs(e.image)));
  return currentImages().filter(image=>deletableOriginal(image)&&!imageMemberIDs(image).some(id=>selected.has(id)));
}
function openBulkDelete(){
  if(state.dirty.size){toast('Save your edits before reviewing files for deletion.',true);return;}
  const images=currentImages().filter(image=>state.selected.has(image.id));
  if(!images.length)return;
  bulkDeletion={phase:'choices',entries:images.filter(deletableOriginal).map(image=>({image,reason:'duplicate',keeper_id:'',plan:null,status:'not_started'})),skipped:images.filter(image=>!deletableOriginal(image)),error:''};
  renderBulkDelete();$('#delete-dialog').showModal();
}
function closeBulkDelete(){
  if(bulkDeletion?.phase==='executing')return;
  bulkDeletion=null;$('#delete-dialog').close();
}
function bulkDeleteLinks(image){
  return `<p class="small">${image.url?`<a href="${safeURL(image.url)}" target="_blank" rel="noopener">Image ↗</a>`:''}${image.folder_url?` · <a href="${safeURL(image.folder_url)}" target="_blank" rel="noopener">Folder ↗</a>`:''}</p>`;
}
function bulkDeleteFacts(entry){
  const p=entry.plan,f=p.file,s=f.sharing,shared=s.links.length||s.explicit_members||s.parent_shared_folder_id;
  return `<dl class="delete-facts"><dt>Dropbox path</dt><dd>${esc(f.path)}</dd><dt>Type / size</dt><dd>Image file · ${esc(bytesLabel(f.bytes))}</dd><dt>Last modified</dt><dd>${esc(f.modified||'Unavailable')}</dd><dt>Stable file ID</dt><dd>${esc(f.id)}</dd><dt>Revision</dt><dd>${esc(f.revision)}</dd><dt>Reason</dt><dd>${p.reason==='duplicate'?'Duplicate — keep '+esc(p.keeper.name):'Unwanted image — no replacement needed'}</dd><dt>Sharing</dt><dd>${shared?'Shared access or links exist; deleting this file affects those references.':'No shared links or explicit members returned by Dropbox.'}</dd></dl>${s.links.length?`<details><summary>${s.links.length} shared or parent-folder link(s)</summary>${s.links.map(l=>`<p><a href="${safeURL(l.url)}" target="_blank" rel="noopener">${esc(l.name||l.path||'Shared link')} ↗</a> · ${l.direct?'direct file link':'parent / inherited link'}</p>`).join('')}</details>`:''}<details><summary>${p.context.products.length} sculpture association(s) affected</summary><ul>${p.context.products.map(x=>`<li>${esc(x.name)}${x.choice.data.primary?' — selected primary':x.source_primary?' — source reference':''}${x.choice.data.uses?.length?' · '+esc(x.choice.data.uses.join(', ')):''}</li>`).join('')}</ul></details>`;
}
function bulkDeleteStatus(entry){
  return ({not_started:'Not attempted',executing:'Deleting and verifying…',deleted:'Deleted — absence verified',rejected:'Not deleted — review changed',uncertain:'Result unconfirmed — check Deletion history'})[entry.status]||entry.status;
}
function renderBulkDelete(){
  const batch=bulkDeletion;if(!batch)return;
  const count=batch.entries.length,choosing=['choices','preparing'].includes(batch.phase),busy=batch.phase==='executing',done=batch.phase==='done',keepers=bulkDeleteKeepers(batch);
  const skipped=batch.skipped.length?`<aside class="bulk-delete-skipped"><strong>${batch.skipped.length} selected image(s) will not be deleted</strong><p>These have no verified Dropbox original available. Use Exclude to keep them out of listings.</p><ul>${batch.skipped.map(a=>`<li>${esc(a.name)} · ${esc(a.source)}</li>`).join('')}</ul></aside>`:'';
  const rows=batch.entries.map((entry,index)=>{
    const keeper=keepers.find(a=>a.id===entry.keeper_id);
    return `<section class="bulk-delete-item" data-delete-entry="${index}"><h3>${index+1}. ${esc(entry.image.name)}</h3><div class="delete-comparison"><div>${deletionPicture(entry.image,'Delete this file')}${bulkDeleteLinks(entry.image)}</div><div>${choosing?`<label>Reason<select data-bulk-delete-reason="${index}"><option value="duplicate" ${entry.reason==='duplicate'?'selected':''}>Duplicate or smaller / modified copy</option><option value="unwanted" ${entry.reason==='unwanted'?'selected':''}>Unwanted image — no replacement needed</option></select></label><div data-bulk-keeper-choice="${index}" ${entry.reason==='duplicate'?'':'hidden'}><label>Image to keep<select data-bulk-delete-keeper="${index}" ${entry.reason==='duplicate'?'required':''}><option value="">Choose the image to keep…</option>${keepers.map(a=>`<option value="${esc(a.id)}" ${entry.keeper_id===a.id?'selected':''}>${esc(a.name)} · ${esc(originalSize(a,true))}</option>`).join('')}</select></label></div>`:''}<div data-bulk-keeper-preview="${index}">${entry.reason==='duplicate'&&keeper?deletionPicture(keeper,'Keep this file')+bulkDeleteLinks(keeper):''}</div></div></div>${!choosing?bulkDeleteFacts(entry):''}${busy||done?`<p class="bulk-delete-status" role="status">${esc(bulkDeleteStatus(entry))}${entry.message?' · '+esc(entry.message):''}</p>`:''}</section>`;
  }).join('');
  $('#delete-dialog').innerHTML=`<button class="close" id="bulk-delete-close" aria-label="Close selected-file deletion review" ${busy?'disabled':''}>×</button><span class="eyebrow">DELETE SELECTED ORIGINALS</span><h2>${done?'Deletion results':choosing?`Review ${count} selected Dropbox file${count===1?'':'s'}`:`Delete ${count} reviewed file${count===1?'':'s'}?`}</h2><p class="bulk-delete-intro">${done?'Each result is shown below. Unattempted files remain selected in the gallery.':choosing?'Choose a keeper for each duplicate, or mark the file as unwanted. Selected files cannot be keepers.':'Check every file below. Deletion removes each original from Dropbox and withholds its display group throughout the app.'}</p>${skipped}${choosing?`<form id="bulk-delete-choice-form" ${batch.phase==='preparing'?'inert':''}>${rows}${count?'<button class="button dark" type="submit">Review selected files</button>':''}</form>`:rows}${batch.phase==='review'?`<p class="small muted">Only these ${count} exact Dropbox files will be deleted. Other native copies and website copies remain. Cached history is retained; each deleted file’s display group is withheld. Reviews expire after 10 minutes.</p><form id="bulk-delete-confirm-form"><label class="check-line"><input id="bulk-delete-confirm" type="checkbox">I have checked all ${count} files and their uses, and will retain any chosen keepers.</label><div class="bulk-delete-actions"><button class="button danger" type="submit" disabled>Delete ${count} file${count===1?'':'s'} from Dropbox</button><button class="button" type="button" id="bulk-delete-back">Back</button></div></form>`:''}${done?'<div class="bulk-delete-actions"><button class="button" id="bulk-delete-history">Deletion history</button><button class="button dark" id="bulk-delete-done">Done</button></div>':''}<p class="small muted">Dropbox’s normal deleted-file recovery rules apply. This does not permanently purge recovery history or delete folders.</p><div id="bulk-delete-result" role="status">${esc(batch.error||'')}</div>`;
}
async function prepareBulkDeletion(){
  const batch=bulkDeletion;if(!batch||batch.phase!=='choices'||!batch.entries.length)return;
  const keepers=new Set(bulkDeleteKeepers(batch).map(a=>a.id));
  if(batch.entries.some(e=>e.reason==='duplicate'&&!keepers.has(e.keeper_id))){batch.error='Choose an unselected Dropbox image to keep for each duplicate.';renderBulkDelete();return;}
  batch.phase='preparing';batch.error='';renderBulkDelete();
  for(let i=0;i<batch.entries.length;i++){
    const entry=batch.entries[i];
    $('#bulk-delete-result').textContent=`Checking file ${i+1} of ${batch.entries.length}, including its current revision and shared links…`;
    try{
      const plan=await api('/api/deletions/prepare',{asset_id:entry.image.id,reason:entry.reason,keeper_id:entry.reason==='duplicate'?entry.keeper_id:''});
      if(bulkDeletion!==batch||!$('#delete-dialog').open)return;
      entry.plan=plan;
    }catch(error){
      if(bulkDeletion!==batch||!$('#delete-dialog').open)return;
      batch.phase='choices';batch.error=`Could not review ${entry.image.name}: ${error.message} Nothing has been deleted.`;renderBulkDelete();return;
    }
  }
  try{
    const plan=await api('/api/deletions/prepare-batch',{operation_ids:batch.entries.map(e=>e.plan.operation_id)});
    if(bulkDeletion!==batch||!$('#delete-dialog').open)return;
    batch.plan=plan;
  }catch(error){
    if(bulkDeletion!==batch||!$('#delete-dialog').open)return;
    batch.phase='choices';batch.error=error.message+' Nothing has been deleted.';renderBulkDelete();return;
  }
  batch.phase='review';renderBulkDelete();
}
async function executeBulkDeletion(){
  const batch=bulkDeletion;if(!batch||batch.phase!=='review'||!$('#bulk-delete-confirm').checked)return;
  batch.phase='executing';batch.error='';renderBulkDelete();
  $('#bulk-delete-result').textContent='Deleting the confirmed files in order and verifying each result…';
  let result;
  try{
    result=await api('/api/deletions/execute-batch',{batch_id:batch.plan.batch_id,confirm_files:batch.plan.files,confirmed:true});
  }catch(error){
    batch.error=error.message+' The batch will not be retried. Check Deletion history for current status.';
    try{result=await api('/api/deletions/batch-status',{batch_id:batch.plan.batch_id});}catch(statusError){batch.error+=' '+statusError.message;}
  }
  for(const entry of batch.entries){
    const item=result?.results?.find(r=>r.operation_id===entry.plan.operation_id);
    entry.status=item?.state||(result?.state==='prepared'?'not_started':'uncertain');entry.message=item?.message||'';
  }
  if(result?.state==='executing')batch.error='The server is still processing this confirmed batch. Check Deletion history for its latest results; do not submit the files again.';
  try{
    await refreshAfterTransfer();
    const retained=new Set([...batch.entries.filter(e=>e.status!=='deleted').map(e=>e.image.id),...batch.skipped.map(a=>a.id)]);
    state.selected=new Set(currentImages().filter(a=>retained.has(a.id)).map(a=>a.id));renderGrid();
  }catch(error){batch.error='Could not refresh the gallery. Reload it to see current file status. '+error.message;}
  batch.phase='done';renderBulkDelete();
}
document.addEventListener('click',async event=>{
  const button=event.target.closest('button');if(!button)return;
  if(button.id==='bulk-delete'){openBulkDelete();return;}
  if(['bulk-delete-close','bulk-delete-done'].includes(button.id)){closeBulkDelete();return;}
  if(button.id==='bulk-delete-back'&&bulkDeletion?.phase==='review'){bulkDeletion.phase='choices';bulkDeletion.entries.forEach(e=>e.plan=null);renderBulkDelete();return;}
  if(button.id==='bulk-delete-history'){
    button.disabled=true;
    try{state.boot=await api('/api/bootstrap');closeBulkDelete();showDeletionHistory();}
    catch(error){toast(error.message,true);}finally{button.disabled=false;}
  }
});
document.addEventListener('change',event=>{
  const element=event.target;
  if(element.id==='bulk-delete-confirm')$('#bulk-delete-confirm-form button[type=submit]').disabled=!element.checked;
  if(!bulkDeletion||bulkDeletion.phase!=='choices')return;
  if(element.hasAttribute('data-bulk-delete-reason')){
    const index=Number(element.dataset.bulkDeleteReason),entry=bulkDeletion.entries[index];entry.reason=element.value;
    const choice=$(`[data-bulk-keeper-choice="${index}"]`);choice.hidden=entry.reason!=='duplicate';$('select',choice).required=entry.reason==='duplicate';
    const keeper=bulkDeleteKeepers(bulkDeletion).find(a=>a.id===entry.keeper_id);
    $(`[data-bulk-keeper-preview="${index}"]`).innerHTML=entry.reason==='duplicate'&&keeper?deletionPicture(keeper,'Keep this file')+bulkDeleteLinks(keeper):'';
  }
  if(element.hasAttribute('data-bulk-delete-keeper')){
    const index=Number(element.dataset.bulkDeleteKeeper),entry=bulkDeletion.entries[index];entry.keeper_id=element.value;
    const keeper=bulkDeleteKeepers(bulkDeletion).find(a=>a.id===entry.keeper_id);
    $(`[data-bulk-keeper-preview="${index}"]`).innerHTML=keeper?deletionPicture(keeper,'Keep this file')+bulkDeleteLinks(keeper):'';
  }
});
document.addEventListener('submit',event=>{
  if(event.target.id==='bulk-delete-choice-form'){event.preventDefault();prepareBulkDeletion();}
  if(event.target.id==='bulk-delete-confirm-form'){event.preventDefault();executeBulkDeletion();}
});
document.querySelector('#delete-dialog').addEventListener('cancel',event=>{if(bulkDeletion){event.preventDefault();closeBulkDelete();}});
window.addEventListener('beforeunload',event=>{if(bulkDeletion?.phase==='executing'){event.preventDefault();event.returnValue='';}});
