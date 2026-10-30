'use strict';
let bulkDeletion=null;
const deletableOriginal=image=>image.source==='Dropbox'&&image.id.startsWith('id:');
const imageMemberIDs=image=>[image.id,...(image.duplicates||[]).map(a=>a.id)];
function bulkDeleteKeepers(batch){
  const selected=new Set(batch.entries.flatMap(e=>imageMemberIDs(e.image)));
  return currentImages().filter(image=>deletableOriginal(image)&&deletionActivity(image)?.kind!=='delete'&&!imageMemberIDs(image).some(id=>selected.has(id)));
}
function partitionBusyDeletions(batch){
  batch.busy=batch.busy||[];
  batch.entries=batch.entries.filter(entry=>{
    const item=deletionActivity(entry.image);if(!item)return true;
    if(!batch.busy.some(x=>x.file_id===item.file_id))batch.busy.push(item);
    return false;
  });
}
async function openBulkDelete(){
  if(state.dirty.size){toast('Save your edits before reviewing files for deletion.',true);return;}
  const images=currentImages().filter(image=>state.selected.has(image.id));
  if(!images.length)return;
  deletionView++;
  const batch=bulkDeletion={phase:'checking',entries:images.filter(deletableOriginal).map(image=>({image,reason:'unwanted',keeper_id:'',plan:null,status:'not_started'})),skipped:images.filter(image=>!deletableOriginal(image)),busy:[],error:''};
  renderBulkDelete();$('#delete-dialog').showModal();
  try{
    await refreshDeletionActivity();
    if(bulkDeletion!==batch||!$('#delete-dialog').open)return;
    partitionBusyDeletions(batch);batch.phase='choices';renderBulkDelete();
  }catch(error){if(bulkDeletion===batch&&$('#delete-dialog').open){batch.phase='check_failed';batch.error=error.message;renderBulkDelete();}}
}
function closeBulkDelete(){
  bulkDeletion=null;$('#delete-dialog').close();
}
function bulkDeleteLinks(image){
  return `<p class="small">${image.url?`<a href="${safeURL(image.url)}" target="_blank" rel="noopener">Image ↗</a>`:''}${image.folder_url?` · <a href="${safeURL(image.folder_url)}" target="_blank" rel="noopener">Folder ↗</a>`:''}</p>`;
}
function bulkDeleteFacts(entry){
  const p=entry.plan,f=p.file,s=f.sharing,shared=s.links.length||s.explicit_members||s.parent_shared_folder_id;
  if(f.availability==='missing')return `<aside class="bulk-delete-skipped"><strong>Already absent from Dropbox</strong><p>Remove the leftover entry from this app. No Dropbox deletion request will be sent. The stable file ID will be checked again before removal.</p></aside><dl class="delete-facts"><dt>Last recorded path</dt><dd>${esc(f.path)}</dd><dt>Stable file ID</dt><dd>${esc(f.id)}</dd><dt>Checked</dt><dd>${esc(f.checked_utc)}</dd><dt>App associations</dt><dd>${p.context.products.length} sculpture association(s) will be withheld; review history is retained.</dd></dl>`;
  return `<dl class="delete-facts"><dt>Dropbox path</dt><dd>${esc(f.path)}</dd><dt>Type / size</dt><dd>Image file · ${esc(bytesLabel(f.bytes))}</dd><dt>Last modified</dt><dd>${esc(f.modified||'Unavailable')}</dd><dt>Stable file ID</dt><dd>${esc(f.id)}</dd><dt>Revision</dt><dd>${esc(f.revision)}</dd><dt>Reason</dt><dd>${p.reason==='duplicate'?'Duplicate — keep '+esc(p.keeper.name):'Unwanted image — no replacement needed'}</dd><dt>Sharing</dt><dd>${shared?'Shared access or links exist; deleting this file affects those references.':'No shared links or explicit members returned by Dropbox.'}</dd></dl>${s.links.length?`<details><summary>${s.links.length} shared or parent-folder link(s)</summary>${s.links.map(l=>`<p><a href="${safeURL(l.url)}" target="_blank" rel="noopener">${esc(l.name||l.path||'Shared link')} ↗</a> · ${l.direct?'direct file link':'parent / inherited link'}</p>`).join('')}</details>`:''}<details><summary>${p.context.products.length} sculpture association(s) affected</summary><ul>${p.context.products.map(x=>`<li>${esc(x.name)}${x.choice.data.primary?' — selected primary':x.source_primary?' — source reference':''}${x.choice.data.uses?.length?' · '+esc(x.choice.data.uses.join(', ')):''}</li>`).join('')}</ul></details>`;
}
function bulkDeleteStatus(entry){
  return ({not_started:'Not attempted',executing:'Checking and removing…',deleted:'Deleted - absence verified',already_absent:'Already absent - app entry removed; no deletion request sent',rejected:'Not deleted - review changed',uncertain:'Result unconfirmed - check Deletion history'})[entry.status]||entry.status;
}
function renderBulkDelete(){
  const batch=bulkDeletion;if(!batch)return;
  if(['checking','check_failed'].includes(batch.phase)){
    $('#delete-dialog').innerHTML=`<button class="close" id="bulk-delete-close" aria-label="Close selected-file deletion review">×</button><h2>Check selected files</h2><p role="status">${esc(batch.error||'Checking which files already have a background job…')}</p>${batch.phase==='check_failed'?'<button class="button" id="bulk-delete-retry">Try again</button>':''}`;
    return;
  }
  const count=batch.entries.length,choosing=['choices','preparing'].includes(batch.phase),busy=batch.phase==='executing',done=batch.phase==='done',keepers=bulkDeleteKeepers(batch);
  const absent=batch.entries.filter(e=>e.plan?.file.availability==='missing').length,present=count-absent;
  const action=absent?(present?`Delete ${present} file${present===1?'':'s'} and remove ${absent} missing entr${absent===1?'y':'ies'}`:`Remove ${absent} missing entr${absent===1?'y':'ies'}`):`Delete ${count} file${count===1?'':'s'} from Dropbox`;
  const skipped=(batch.skipped.length?`<aside class="bulk-delete-skipped"><strong>${batch.skipped.length} selected image(s) will not be deleted</strong><p>These are not known Dropbox file IDs. Use Exclude to keep them out of listings.</p><ul>${batch.skipped.map(a=>`<li>${esc(a.name)} · ${esc(a.source)}</li>`).join('')}</ul></aside>`:'')+deletionBusyNotice(batch.busy);
  const rows=batch.entries.map((entry,index)=>{
    const keeper=keepers.find(a=>a.id===entry.keeper_id);
    return `<section class="bulk-delete-item" data-delete-entry="${index}"><h3>${index+1}. ${esc(entry.image.name)}</h3><div class="delete-comparison"><div>${deletionPicture(entry.image,entry.plan?.file.availability==='missing'?'Saved reference':'Delete this file')}${bulkDeleteLinks(entry.image)}</div><div>${choosing?`<label>Reason<select data-bulk-delete-reason="${index}"><option value="duplicate" ${entry.reason==='duplicate'?'selected':''}>Duplicate or smaller / modified copy</option><option value="unwanted" ${entry.reason==='unwanted'?'selected':''}>Unwanted image — no replacement needed</option></select></label><div data-bulk-keeper-choice="${index}" ${entry.reason==='duplicate'?'':'hidden'}><label>Image to keep<select data-bulk-delete-keeper="${index}" ${entry.reason==='duplicate'?'required':''}><option value="">Choose the image to keep…</option>${keepers.map(a=>`<option value="${esc(a.id)}" ${entry.keeper_id===a.id?'selected':''}>${esc(a.name)} · ${esc(originalSize(a,true))}</option>`).join('')}</select></label></div>`:''}<div data-bulk-keeper-preview="${index}">${entry.reason==='duplicate'&&keeper?deletionPicture(keeper,'Keep this file')+bulkDeleteLinks(keeper):''}</div></div></div>${!choosing?bulkDeleteFacts(entry):''}${busy||done?`<p class="bulk-delete-status" role="status">${esc(bulkDeleteStatus(entry))}${entry.message?' · '+esc(entry.message):''}</p>`:''}</section>`;
  }).join('');
  $('#delete-dialog').innerHTML=`<button class="close" id="bulk-delete-close" aria-label="Close selected-file deletion review" >×</button><span class="eyebrow">DELETE SELECTED ORIGINALS</span><h2>${done?'Deletion results':choosing?(count?`Review ${count} selected Dropbox file${count===1?'':'s'}`:'No additional files to delete'):`${action}?`}</h2><p class="bulk-delete-intro">${done?'Each result is shown below. Unattempted files remain selected in the gallery.':choosing?'Unwanted image is selected by default. For a duplicate, choose that reason and an image to keep. Selected files cannot be keepers.':'Check every item below. Present files will be deleted from Dropbox; already-absent files will only have their leftover app entries removed.'}</p>${skipped}${choosing?`<form id="bulk-delete-choice-form" ${batch.phase==='preparing'?'inert':''}>${rows}${count?'<button class="button dark" type="submit">Review selected files</button>':''}</form>`:rows}${batch.phase==='review'?`<p class="small muted">${present} file${present===1?'':'s'} will be deleted from Dropbox; ${absent} missing entr${absent===1?'y':'ies'} will be removed from the app without a deletion request. Other originals and website copies remain. Reviews expire after 10 minutes.</p><form id="bulk-delete-confirm-form"><label class="check-line"><input id="bulk-delete-confirm" type="checkbox">I have checked all ${count} items and their uses, and will retain any chosen keepers.</label><div class="bulk-delete-actions"><button class="button danger" type="submit" disabled>${action}</button><button class="button" type="button" id="bulk-delete-back">Back</button></div></form>`:''}${done?'<div class="bulk-delete-actions"><button class="button" id="bulk-delete-history">Deletion history</button><button class="button dark" id="bulk-delete-done">Done</button></div>':''}<p class="small muted">Dropbox’s normal deleted-file recovery rules apply. This does not permanently purge recovery history or delete folders.</p><div id="bulk-delete-result" role="status">${esc(batch.error||'')}</div>`;
}
async function prepareBulkDeletion(){
  const batch=bulkDeletion;if(!batch||batch.phase!=='choices'||!batch.entries.length)return;
  const keepers=new Set(bulkDeleteKeepers(batch).map(a=>a.id));
  if(batch.entries.some(e=>e.reason==='duplicate'&&!keepers.has(e.keeper_id))){batch.error='Choose an unselected Dropbox image to keep for each duplicate.';renderBulkDelete();return;}
  batch.phase='preparing';batch.error='';renderBulkDelete();
  try{await refreshDeletionActivity();}catch(error){if(bulkDeletion===batch){batch.phase='choices';batch.error=error.message;renderBulkDelete();}return;}
  if(bulkDeletion!==batch||!$('#delete-dialog').open)return;
  partitionBusyDeletions(batch);
  if(!batch.entries.length){batch.phase='choices';renderBulkDelete();return;}
  for(let i=0;i<batch.entries.length;i++){
    const entry=batch.entries[i];
    $('#bulk-delete-result').textContent=`Checking file ${i+1} of ${batch.entries.length}, including its current revision and shared links…`;
    try{
      const plan=await api('/api/deletions/prepare',{asset_id:entry.image.id,reason:entry.reason,keeper_id:entry.reason==='duplicate'?entry.keeper_id:''});
      if(bulkDeletion!==batch||!$('#delete-dialog').open)return;
      entry.plan=plan;
    }catch(error){
      if(bulkDeletion!==batch||!$('#delete-dialog').open)return;
      const busy=error.details?.busy_files?.find(item=>imageMemberIDs(entry.image).includes(item.file_id));
      if(busy){batch.busy.push(busy);batch.entries.splice(i--,1);continue;}
      batch.phase='choices';batch.error=`Could not review ${entry.image.name}: ${error.message} Nothing has been deleted.`;renderBulkDelete();return;
    }
  }
  if(!batch.entries.length){batch.phase='choices';renderBulkDelete();return;}
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
  $('#bulk-delete-result').textContent='Queueing the confirmed files. You may close this dialog; Jobs shows progress.';
  try{
    const job=await api('/api/deletions/execute-batch',{batch_id:batch.plan.batch_id,confirm_files:batch.plan.files,confirmed:true});
    // A closed dialog or navigation must never be reopened by a late response.
    if(bulkDeletion===batch)closeBulkDelete();
    await trackNativeJob(job);
    toast(job.skipped?.length?`Deletion queued for ${job.files.length} file(s); ${job.skipped.length} already handled or reserved. See Jobs.`:'Deletion queued. Keep reviewing; follow progress in Jobs.');
  }catch(error){
    // An HTTP response can be lost after the server commits the queue entry.
    // Discover that durable job; never submit a second deletion automatically.
    const found=await findNativeJob('delete-batch-'+batch.plan.batch_id);
    if(found){if(bulkDeletion===batch)closeBulkDelete();toast('Deletion is queued. See Jobs for progress.');return;}
    if(bulkDeletion===batch){
      batch.phase=error.details?.busy_files?'choices':'review';batch.error=error.message;
      if(error.details?.busy_files){for(const item of error.details.busy_files)nativeJobStatus.deletion_activity[item.file_id]=item;partitionBusyDeletions(batch);batch.entries.forEach(e=>e.plan=null);}
      renderBulkDelete();
    }
    else toast(error.message+' Check Jobs before starting another deletion.',true);
  }
}
document.addEventListener('click',async event=>{
  const button=event.target.closest('button');if(!button)return;
  if(button.id==='bulk-delete'){openBulkDelete();return;}
  if(button.id==='bulk-delete-retry'){closeBulkDelete();openBulkDelete();return;}
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
