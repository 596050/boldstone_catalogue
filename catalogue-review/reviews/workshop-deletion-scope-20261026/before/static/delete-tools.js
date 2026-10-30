'use strict';
let deleteImage=null,deletePlan=null;
function renderDeleteControl(image){
  $('#image-form').insertAdjacentHTML('beforebegin','<p class="small muted">Either Save button saves image choices and shared tags together.</p>');
  if(image.source==='Dropbox'&&image.original?.dropbox_content_hash&&image.original?.bytes){
    $('.detail-controls').insertAdjacentHTML('beforeend',`<section class="delete-section"><h3>Original file</h3><p class="small muted">Delete an unwanted original from Dropbox and remove it from every sculpture in this app. Cached history is retained. You will review the exact file first.</p><button class="button danger" data-delete-image="${esc(image.id)}">Delete file…</button></section>`);
  }
}
function deletionPicture(image,label){
  return `<figure><figcaption>${esc(label)}</figcaption>${imageURL(image,true)?`<img src="${esc(imageURL(image,true))}" alt="${esc(image.name)}">`:''}<strong>${esc(image.name)}</strong><p>${esc(originalSize(image))}</p></figure>`;
}
function deleteCandidates(){return currentImages().filter(a=>a.id!==deleteImage.id&&a.source==='Dropbox'&&a.original?.dropbox_content_hash&&a.original?.bytes);}
function openDelete(aid){
  const image=currentImages().find(x=>x.id===aid);if(!image)return;
  if($('#image-dialog').open&&!closeImage())return;
  deleteImage=image;deletePlan=null;
  $('#delete-dialog').innerHTML=`<button class="close" data-close="delete-dialog" aria-label="Close deletion review">×</button><span class="eyebrow">DELETE AN ORIGINAL FILE</span><h2>Check the copy to delete</h2><p>Choose the image to keep when removing a duplicate. Smaller size or a similar appearance alone does not select a file for deletion.</p><div class="delete-comparison"><div>${deletionPicture(image,'Delete this file')}</div><div id="delete-keeper-preview"></div></div><form id="delete-choice-form"><label>Reason<select name="reason" id="delete-reason"><option value="duplicate">Duplicate or smaller / modified copy</option><option value="unwanted" selected>Unwanted image — no replacement needed</option></select></label><div id="delete-keeper-choice"><label>Image to keep<select name="keeper" id="delete-keeper"><option value="">Choose the original to keep…</option>${deleteCandidates().map(a=>`<option value="${esc(a.id)}">${esc(a.name)} · ${esc(originalSize(a,true))}</option>`).join('')}</select></label><p class="small muted">These are Dropbox images associated with the current view. Open the Image library if your keeper is under another title.</p></div><button class="button dark" type="submit">Review deletion</button></form><p class="small muted">Dropbox’s normal deleted-file recovery rules apply. This does not permanently purge recovery history or delete folders.</p><div id="delete-result" role="status"></div>`;
  updateDeleteKeeper();$('#delete-dialog').showModal();
}
function updateDeleteKeeper(){
  const duplicate=$('#delete-reason').value==='duplicate';$('#delete-keeper-choice').hidden=!duplicate;
  const keeper=deleteCandidates().find(a=>a.id===$('#delete-keeper').value);
  $('#delete-keeper-preview').innerHTML=duplicate&&keeper?deletionPicture(keeper,'Keep this file'):'';
}
async function prepareDeletion(form){
  const button=$('button[type=submit]',form);button.disabled=true;$('#delete-result').textContent='Checking the current file, revision and shared links in Dropbox…';
  try{
    const plan=await api('/api/deletions/prepare',{asset_id:deleteImage.id,reason:form.elements.reason.value,keeper_id:form.elements.reason.value==='duplicate'?form.elements.keeper.value:''});
    deletePlan=plan;renderDeleteReview();
  }catch(e){$('#delete-result').textContent=e.message;}finally{button.disabled=false;}
}
function renderDeleteReview(){
  const p=deletePlan,f=p.file,s=f.sharing,shared=s.links.length||s.explicit_members||s.parent_shared_folder_id;
  const keeper=p.keeper?deleteCandidates().find(a=>a.id===p.keeper.id):null;
  $('#delete-dialog').innerHTML=`<button class="close" data-close="delete-dialog" aria-label="Close deletion review">×</button><span class="eyebrow">EXACT FILE REVIEW</span><h2>Delete ${esc(f.name)}?</h2><div class="delete-comparison"><div>${deletionPicture(deleteImage,'Delete this file')}</div><div>${keeper?deletionPicture(keeper,'Keep this file'):''}</div></div><dl class="delete-facts"><dt>Dropbox path</dt><dd>${esc(f.path)}</dd><dt>Type</dt><dd>One image file</dd><dt>Size</dt><dd>${esc(bytesLabel(f.bytes))}</dd><dt>Last modified</dt><dd>${esc(f.modified||'Unavailable')}</dd><dt>Stable file ID</dt><dd>${esc(f.id)}</dd><dt>Revision</dt><dd>${esc(f.revision)}</dd><dt>Reason</dt><dd>${p.reason==='duplicate'?'User-selected duplicate; keeper verified in Dropbox':'User-selected unwanted image'}</dd><dt>Sharing</dt><dd>${shared?'Shared access or links exist; deleting this file affects those references.':'No shared links or explicit members returned by Dropbox.'}</dd></dl>${s.links.length?`<details><summary>${s.links.length} shared or parent-folder link(s)</summary>${s.links.map(l=>`<p><a href="${safeURL(l.url)}" target="_blank" rel="noopener">${esc(l.name||l.path||'Shared link')} ↗</a> · ${l.direct?'direct file link':'parent / inherited link'}</p>`).join('')}</details>`:''}<details open><summary>${p.context.products.length} sculpture association(s) affected</summary><ul>${p.context.products.map(x=>`<li>${esc(x.name)}${x.choice.data.primary?' — selected primary':x.source_primary?' — source reference':''}${x.choice.data.uses?.length?' · '+esc(x.choice.data.uses.join(', ')):''}</li>`).join('')}</ul></details><p class="small muted">Only this Dropbox file will be deleted. Other exact-byte originals are not deleted; ${p.context.aliases.length-1} retained alias record(s) stay in history. This image’s cached display group is withheld throughout the app. Existing website copies are not deleted by this action.</p><form id="delete-confirm-form"><label class="check-line"><input id="delete-confirm" type="checkbox">I have checked this exact file and its uses${p.keeper?' and will retain '+esc(p.keeper.name):''}.</label><button class="button danger" type="submit" disabled>Delete this file from Dropbox</button></form><p class="small muted">Recoverable through Dropbox’s Deleted files while your account’s recovery period allows. Review expires after 10 minutes.</p><div id="delete-result" role="status"></div>`;
}
async function executeDeletion(form){
  if(!$('#delete-confirm').checked)return;
  const button=$('button[type=submit]',form);button.disabled=true;$('#delete-result').textContent='Deleting the reviewed original and checking Dropbox…';
  try{
    const result=await api('/api/deletions/execute',{operation_id:deletePlan.operation_id,confirm_file_id:deletePlan.file.id,confirmed:true});
    await refreshAfterTransfer();$('#delete-dialog').close();
    if(result.state==='deleted')toast('Original deleted from Dropbox and verified. Review history retained.');
    else if(result.state==='rejected')toast(result.message||'The file changed; nothing was deleted.',true);
    else {toast('Deletion needs verification. It will not be retried automatically.',true);showDeletionHistory();}
  }catch(e){$('#delete-result').textContent=e.message;button.disabled=false;}
}
function showDeletionHistory(){
  $('#history-dialog').innerHTML=`<button class="close" data-close="history-dialog" aria-label="Close history">×</button><span class="eyebrow">ORIGINAL FILE DELETIONS</span><h2>Deletion history</h2><p>Files are removed only after their exact deletion review. <a href="https://www.dropbox.com/deleted_files" target="_blank" rel="noopener">Open Dropbox Deleted files ↗</a> for available recovery.</p>${(state.boot.deletions||[]).map(j=>`<div class="operation-row"><div><strong>${esc(j.file.name)}</strong><p class="small">${esc(j.file.path)}<br>${esc(j.file_id)} · ${esc(j.file.revision)}</p><p>${esc(j.state==='deleted'?'Deleted — absence verified':j.state==='rejected'?'Not deleted — review changed':j.state==='executing'?'Deletion started — check result':'Verification pending')}</p>${j.result.message?`<p>${esc(j.result.message)}</p>`:''}</div>${['uncertain','executing'].includes(j.state)?`<button class="button" data-check-deletion="${esc(j.operation_id)}">Check status</button>`:''}</div>`).join('')||'<p>No files have been deleted through this app.</p>'}`;
  $('#history-dialog').showModal();
}
document.addEventListener('click',async e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.dataset.deleteImage){openDelete(b.dataset.deleteImage);return;}
  if(b.id==='delete-history'){state.boot=await api('/api/bootstrap');showDeletionHistory();return;}
  if(b.dataset.checkDeletion){b.disabled=true;try{await api('/api/deletions/check',{operation_id:b.dataset.checkDeletion});await refreshAfterTransfer();showDeletionHistory();}catch(err){toast(err.message,true);}finally{b.disabled=false;}}
});
document.addEventListener('change',e=>{
  if(['delete-reason','delete-keeper'].includes(e.target.id))updateDeleteKeeper();
  if(e.target.id==='delete-confirm')$('#delete-confirm-form button[type=submit]').disabled=!e.target.checked;
});
document.addEventListener('submit',e=>{
  if(e.target.id==='delete-choice-form'){e.preventDefault();prepareDeletion(e.target);}
  if(e.target.id==='delete-confirm-form'){e.preventDefault();executeDeletion(e.target);}
});
