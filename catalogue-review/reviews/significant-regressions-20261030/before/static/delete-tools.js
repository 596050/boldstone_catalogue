'use strict';
let deleteImage=null,deletePlan=null,deletionView=0;
function renderDeleteControl(image){
  $('#image-form').insertAdjacentHTML('beforebegin','<p class="small muted">Either Save button saves image choices and shared tags together.</p>');
  if(image.source==='Dropbox'&&image.id.startsWith('id:')){
    $('.detail-controls').insertAdjacentHTML('beforeend',`<section class="delete-section"><h3>Original file</h3><p class="small muted">Delete an unwanted original from Dropbox and remove it from every sculpture in this app. Cached history is retained. You will review the exact file first.</p><button class="button danger" data-delete-image="${esc(image.id)}">Delete file…</button></section>`);
  }
}
function deletionPicture(image,label){
  return `<figure><figcaption>${esc(label)}</figcaption>${imageURL(image,true)?`<img loading="lazy" decoding="async" src="${esc(imageURL(image,true))}" alt="${esc(image.name)}">`:'<p class="small muted">Preview unavailable. The file can still be reviewed by its Dropbox ID.</p>'}<strong>${esc(image.name)}</strong><p>${esc(originalSize(image))}</p></figure>`;
}
function deleteCandidates(){return currentImages().filter(a=>!imageMemberIDs(a).some(id=>imageMemberIDs(deleteImage).includes(id))&&a.source==='Dropbox'&&a.id.startsWith('id:')&&deletionActivity(a)?.kind!=='delete');}
function renderBusyDeletion(image,items){
  $('#delete-dialog').innerHTML=`<button class="close" data-close="delete-dialog" aria-label="Close deletion review">×</button><h2>${esc(image.name)}</h2>${deletionBusyNotice(items)}<p>No additional deletion has been started for this file.</p>`;
}
async function openDelete(aid){
  const image=currentImages().find(x=>x.id===aid);if(!image)return;
  if($('#image-dialog').open&&!closeImage())return;
  deleteImage=image;deletePlan=null;bulkDeletion=null;
  const view=++deletionView;
  $('#delete-dialog').innerHTML='<button class="close" data-close="delete-dialog" aria-label="Close deletion review">×</button><h2>Check original file</h2><p role="status">Checking existing deletion jobs…</p>';
  $('#delete-dialog').showModal();
  try{await refreshDeletionActivity();}
  catch(error){if(view===deletionView&&$('#delete-dialog').open)$('#delete-dialog').innerHTML=`<button class="close" data-close="delete-dialog" aria-label="Close deletion review">×</button><p>${esc(error.message)}</p><button class="button" data-delete-image="${esc(aid)}">Try again</button>`;return;}
  if(view!==deletionView||!$('#delete-dialog').open)return;
  const busy=deletionActivity(image);if(busy){renderBusyDeletion(image,[busy]);return;}
  $('#delete-dialog').innerHTML=`<button class="close" data-close="delete-dialog" aria-label="Close deletion review">×</button><span class="eyebrow">DELETE AN ORIGINAL FILE</span><h2>Check the copy to delete</h2><p>Choose the image to keep when removing a duplicate. Smaller size or a similar appearance alone does not select a file for deletion.</p><div class="delete-comparison"><div>${deletionPicture(image,'Delete this file')}</div><div id="delete-keeper-preview"></div></div><form id="delete-choice-form"><label>Reason<select name="reason" id="delete-reason"><option value="duplicate">Duplicate or smaller / modified copy</option><option value="unwanted" selected>Unwanted image — no replacement needed</option></select></label><div id="delete-keeper-choice"><label>Image to keep<select name="keeper" id="delete-keeper"><option value="">Choose the original to keep…</option>${deleteCandidates().map(a=>`<option value="${esc(a.id)}">${esc(a.name)} · ${esc(originalSize(a,true))}</option>`).join('')}</select></label><p class="small muted">These are Dropbox images associated with the current view. Open the Image library if your keeper is under another title.</p></div><button class="button dark" type="submit">Review deletion</button></form><p class="small muted">Dropbox’s normal deleted-file recovery rules apply. This does not permanently purge recovery history or delete folders.</p><div id="delete-result" role="status"></div>`;
  updateDeleteKeeper();
}
function updateDeleteKeeper(){
  const duplicate=$('#delete-reason').value==='duplicate';$('#delete-keeper-choice').hidden=!duplicate;
  const keeper=deleteCandidates().find(a=>a.id===$('#delete-keeper').value);
  $('#delete-keeper-preview').innerHTML=duplicate&&keeper?deletionPicture(keeper,'Keep this file'):'';
}
async function prepareDeletion(form){
  const image=deleteImage,reason=form.elements.reason.value,keeper=form.elements.keeper.value;
  bulkDeletion={phase:'choices',entries:[{image,reason,keeper_id:reason==='duplicate'?keeper:'',plan:null,status:'not_started'}],skipped:[],busy:[],error:''};
  deletePlan=null;await prepareBulkDeletion();
}
function renderDeleteReview(){
  if(deletePlan.file.availability==='missing'){renderMissingDeleteReview();return;}
  const p=deletePlan,f=p.file,s=f.sharing,shared=s.links.length||s.explicit_members||s.parent_shared_folder_id;
  const keeper=p.keeper?deleteCandidates().find(a=>a.id===p.keeper.id):null;
  $('#delete-dialog').innerHTML=`<button class="close" data-close="delete-dialog" aria-label="Close deletion review">×</button><span class="eyebrow">EXACT FILE REVIEW</span><h2>Delete ${esc(f.name)}?</h2><div class="delete-comparison"><div>${deletionPicture(deleteImage,'Delete this file')}</div><div>${keeper?deletionPicture(keeper,'Keep this file'):''}</div></div><dl class="delete-facts"><dt>Dropbox path</dt><dd>${esc(f.path)}</dd><dt>Type</dt><dd>One image file</dd><dt>Size</dt><dd>${esc(bytesLabel(f.bytes))}</dd><dt>Last modified</dt><dd>${esc(f.modified||'Unavailable')}</dd><dt>Stable file ID</dt><dd>${esc(f.id)}</dd><dt>Revision</dt><dd>${esc(f.revision)}</dd><dt>Reason</dt><dd>${p.reason==='duplicate'?'User-selected duplicate; keeper verified in Dropbox':'User-selected unwanted image'}</dd><dt>Sharing</dt><dd>${shared?'Shared access or links exist; deleting this file affects those references.':'No shared links or explicit members returned by Dropbox.'}</dd></dl>${s.links.length?`<details><summary>${s.links.length} shared or parent-folder link(s)</summary>${s.links.map(l=>`<p><a href="${safeURL(l.url)}" target="_blank" rel="noopener">${esc(l.name||l.path||'Shared link')} ↗</a> · ${l.direct?'direct file link':'parent / inherited link'}</p>`).join('')}</details>`:''}<details open><summary>${p.context.products.length} sculpture association(s) affected</summary><ul>${p.context.products.map(x=>`<li>${esc(x.name)}${x.choice.data.primary?' — selected primary':x.source_primary?' — source reference':''}${x.choice.data.uses?.length?' · '+esc(x.choice.data.uses.join(', ')):''}</li>`).join('')}</ul></details><p class="small muted">Only this Dropbox file will be deleted. Other exact-byte originals are not deleted; ${p.context.aliases.length-1} retained alias record(s) stay in history. This image’s cached display group is withheld throughout the app. Existing website copies are not deleted by this action.</p><form id="delete-confirm-form"><label class="check-line"><input id="delete-confirm" type="checkbox">I have checked this exact file and its uses${p.keeper?' and will retain '+esc(p.keeper.name):''}.</label><button class="button danger" type="submit" disabled>Delete this file from Dropbox</button></form><p class="small muted">Recoverable through Dropbox’s Deleted files while your account’s recovery period allows. Review remains available for 24 hours; the file is checked again before deletion.</p><div id="delete-result" role="status"></div>`;
}
function renderMissingDeleteReview(){
  const p=deletePlan,f=p.file;
  $('#delete-dialog').innerHTML=`<button class="close" data-close="delete-dialog" aria-label="Close deletion review">×</button><span class="eyebrow">UNAVAILABLE FILE REVIEW</span><h2>Remove this missing entry?</h2>${deletionPicture(deleteImage,'Saved reference')}<p>Dropbox reports this stable file ID is no longer present. Remove its leftover entry from this app; no Dropbox deletion request will be sent.</p><dl class="delete-facts"><dt>File</dt><dd>${esc(f.name)}</dd><dt>Last recorded path</dt><dd>${esc(f.path)}</dd><dt>Stable file ID</dt><dd>${esc(f.id)}</dd><dt>Dropbox status</dt><dd>Already absent - checked ${esc(f.checked_utc)}</dd></dl><p>${p.context.products.length} sculpture association(s) will be withheld. Review history and cached files are retained.</p><form id="delete-confirm-form"><label class="check-line"><input id="delete-confirm" type="checkbox">Remove this unavailable entry from every sculpture in the app.</label><button class="button danger" type="submit" disabled>Remove missing entry</button></form><p class="small muted">Dropbox will be checked again before removal. If the file is present again, a new deletion review is required.</p><div id="delete-result" role="status"></div>`;
}
async function executeDeletion(form){
  if(!$('#delete-confirm').checked)return;
  const plan=deletePlan,dialog=$('#delete-dialog'),view=deletionView;
  $('button[type=submit]',form).disabled=true;
  $('#delete-result').textContent='Queueing this file. You can close this dialog and follow progress in Jobs.';
  try{
    const job=await api('/api/deletions/execute',{operation_id:plan.operation_id,confirm_file_id:plan.file.id,confirmed:true});
    if(view===deletionView&&deletePlan===plan&&dialog.open)dialog.close();
    await trackNativeJob(job);reportDeletionJob(job);
  }catch(e){
    const found=await findNativeJob('delete-'+plan.operation_id);
    if(found){if(view===deletionView&&deletePlan===plan&&dialog.open)dialog.close();reportDeletionJob(found);return;}
    if(view===deletionView&&deletePlan===plan&&dialog.open){
      if(e.details?.busy_files?.some(item=>imageMemberIDs(deleteImage).includes(item.file_id)))renderBusyDeletion(deleteImage,e.details.busy_files);
      else {$('#delete-result').textContent=e.message;$('button[type=submit]',form).disabled=false;}
    }
    else toast(e.message+' Check Jobs before starting another deletion.',true);
  }
}
let deletionHistoryRequest=0,deletionHistoryView=0;
const checkingHistoryDeletions=new Set();
function renderDeletionHistory(){
  $('#history-dialog').innerHTML=`<button class="close" data-close="history-dialog" aria-label="Close history">×</button><span class="eyebrow">ORIGINAL FILE DELETIONS</span><h2>Deletion history</h2><p>Files are removed only after their exact deletion review. <a href="https://www.dropbox.com/deleted_files" target="_blank" rel="noopener">Open Dropbox Deleted files ↗</a> for available recovery.</p><p id="history-status" role="status"></p><button class="button" id="deletion-history-refresh">Refresh history</button>${(state.boot.deletions||[]).map(j=>`<div class="operation-row"><div><strong>${esc(j.file.name)}</strong><p class="small">${esc(j.file.path)}<br>${esc(j.file_id)} · ${esc(j.file.revision)}</p><p>${esc(j.state==='deleted'?'Deleted - absence verified':j.state==='already_absent'?'Already absent - app entry removed':j.state==='present'?'File present - ready for a new review':j.state==='rejected'?'Not deleted - review changed':j.state==='executing'?'Deletion started - check result':'Verification pending')}</p>${j.result.message?`<p>${esc(j.result.message)}</p>`:''}</div>${['uncertain','executing'].includes(j.state)?`<button class="button" data-check-deletion="${esc(j.operation_id)}" ${checkingHistoryDeletions.has(j.operation_id)?'disabled':''}>Check status</button>`:''}</div>`).join('')||'<p>No files have been deleted through this app.</p>'}`;
}
function showDeletionHistory(){
  deletionHistoryView=++historyView;renderDeletionHistory();$('#history-dialog').showModal();
}
async function refreshDeletionHistory(view=historyView){
  if(view!==historyView||!$('#history-dialog').open)return;
  const request=++deletionHistoryRequest;
  $('#history-status').textContent='Refreshing saved deletion results…';
  try{
    const rows=await api('/api/deletions/history');
    if(request!==deletionHistoryRequest||view!==historyView||!$('#history-dialog').open)return;
    // A history read must never replace the catalogue or another saved edit.
    state.boot.deletions=rows;renderDeletionHistory();
    $('#history-status').textContent='Saved deletion results refreshed.';
  }catch(error){
    if(request===deletionHistoryRequest&&view===historyView&&$('#history-dialog').open)
      $('#history-status').textContent='Could not refresh history: '+error.message+' Use Refresh history to try again.';
  }
}
async function openDeletionHistory(){
  showDeletionHistory();await refreshDeletionHistory();
}
async function checkHistoryDeletion(button){
  const id=button.dataset.checkDeletion,view=historyView;
  if(button.disabled||checkingHistoryDeletions.has(id))return;
  checkingHistoryDeletions.add(id);button.disabled=true;
  ++deletionHistoryRequest; // Ignore history reads begun before this check.
  $('#history-status').textContent='Checking this file in Dropbox. You can close this window.';
  try{
    const result=await api('/api/deletions/check',{operation_id:id});
    state.boot.deletions=(state.boot.deletions||[]).map(row=>row.operation_id===id?{...row,state:result.state,result}:row);
    nativeViewNeedsRefresh=true;
    if(historyView===deletionHistoryView&&$('#history-dialog').open){
      renderDeletionHistory();await refreshDeletionHistory();
    }
    else toast('Deletion status checked. The saved result is available in Jobs and Deletion history.');
  }catch(error){
    if(view===historyView&&$('#history-dialog').open)$('#history-status').textContent='Could not check this result: '+error.message;
    toast(error.message,true);
  }finally{
    checkingHistoryDeletions.delete(id);button.disabled=false;
    if(historyView===deletionHistoryView&&$('#history-dialog').open)
      for(const b of $$('[data-check-deletion]',$('#history-dialog')))b.disabled=checkingHistoryDeletions.has(b.dataset.checkDeletion);
  }
}
document.addEventListener('click',async e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.dataset.deleteImage){openDelete(b.dataset.deleteImage);return;}
  if(b.id==='delete-history'){await openDeletionHistory();return;}
  if(b.id==='deletion-history-refresh'){await refreshDeletionHistory();return;}
  if(b.dataset.checkDeletion)await checkHistoryDeletion(b);
});
document.addEventListener('change',e=>{
  if(['delete-reason','delete-keeper'].includes(e.target.id))updateDeleteKeeper();
  if(e.target.id==='delete-confirm')$('#delete-confirm-form button[type=submit]').disabled=!e.target.checked;
});
document.addEventListener('submit',e=>{
  if(e.target.id==='delete-choice-form'){e.preventDefault();prepareDeletion(e.target);}
  if(e.target.id==='delete-confirm-form'){e.preventDefault();executeDeletion(e.target);}
});
