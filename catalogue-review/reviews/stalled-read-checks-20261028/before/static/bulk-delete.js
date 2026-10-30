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
  return ({not_started:'Not attempted',executing:'Checking and removing…',deleted:'Deleted - absence verified',already_absent:'Already absent - app entry removed; no deletion request sent',present:'File present - ready for a new review',rejected:'Not deleted - review changed',uncertain:'Result unconfirmed - check Deletion history'})[entry.status]||entry.status;
}
function renderBulkDelete(){
  const batch=bulkDeletion;if(!batch)return;
  if(['checking','check_failed'].includes(batch.phase)){
    $('#delete-dialog').innerHTML=`<button class="close" id="bulk-delete-close" aria-label="Close selected-file deletion review">×</button><h2>Check selected files</h2><p role="status">${esc(batch.error||'Checking which files already have a background job…')}</p>${batch.phase==='check_failed'?'<button class="button" id="bulk-delete-retry">Try again</button>':''}`;
    return;
  }
  if(batch.phase==='checking_files'){
    $('#delete-dialog').innerHTML=`<button class="close" id="bulk-delete-close" aria-label="Close selected-file deletion review">×</button><span class="eyebrow">READ-ONLY CHECKS</span><h2>Checking selected Dropbox files</h2>${deletionReviewProgress(batch.review)}<p>${esc((batch.review?.entries||[]).filter(e=>e.state==='checking').map(e=>'Checking '+e.name).join(' · '))}</p><button class="button" type="button" data-open-native-jobs>View background jobs</button><div id="bulk-delete-result" role="status">${esc(batch.error||'')}</div>`;return;
  }
  if(batch.phase==='stopped'){
    $('#delete-dialog').innerHTML=`<button class="close" id="bulk-delete-close" aria-label="Close selected-file deletion review">×</button><span class="eyebrow">READ-ONLY CHECKS</span><h2>Checks stopped</h2>${deletionReviewProgress(batch.review)}<p>Completed checks are saved. Resume to finish the remaining checks and prepare your confirmation.</p><button class="button dark" type="button" id="bulk-review-retry">Resume checks</button><button class="button" type="button" data-open-native-jobs>View background jobs</button><div id="bulk-delete-result" role="status">${esc(batch.error||'')}</div>`;return;
  }
  const count=batch.entries.length,choosing=['choices','preparing'].includes(batch.phase),busy=batch.phase==='executing',done=batch.phase==='done',keepers=bulkDeleteKeepers(batch);
  const absent=batch.entries.filter(e=>e.plan?.file.availability==='missing').length,present=count-absent;
  const action=absent?(present?`Delete ${present} file${present===1?'':'s'} and remove ${absent} missing entr${absent===1?'y':'ies'}`:`Remove ${absent} missing entr${absent===1?'y':'ies'}`):`Delete ${count} file${count===1?'':'s'} from Dropbox`;
  const skipped=(batch.skipped.length?`<aside class="bulk-delete-skipped"><strong>${batch.skipped.length} selected image(s) will not be deleted</strong><p>These are not known Dropbox file IDs. Use Exclude to keep them out of listings.</p><ul>${batch.skipped.map(a=>`<li>${esc(a.name)} · ${esc(a.source)}</li>`).join('')}</ul></aside>`:'')+deletionBusyNotice(batch.busy);
  const rows=batch.entries.map((entry,index)=>{
    const keeper=keepers.find(a=>a.id===entry.keeper_id);
    return `<section class="bulk-delete-item" data-delete-entry="${index}"><h3>${index+1}. ${esc(entry.image.name)}</h3><div class="delete-comparison"><div>${deletionPicture(entry.image,entry.plan?.file.availability==='missing'?'Saved reference':'Delete this file')}${bulkDeleteLinks(entry.image)}</div><div>${choosing?`<label>Reason<select data-bulk-delete-reason="${index}"><option value="duplicate" ${entry.reason==='duplicate'?'selected':''}>Duplicate or smaller / modified copy</option><option value="unwanted" ${entry.reason==='unwanted'?'selected':''}>Unwanted image — no replacement needed</option></select></label><div data-bulk-keeper-choice="${index}" ${entry.reason==='duplicate'?'':'hidden'}><label>Image to keep<select data-bulk-delete-keeper="${index}" ${entry.reason==='duplicate'?'required':''}><option value="">Choose the image to keep…</option>${(entry.reason==='duplicate'?keepers:[]).map(a=>`<option value="${esc(a.id)}" ${entry.keeper_id===a.id?'selected':''}>${esc(a.name)} · ${esc(originalSize(a,true))}</option>`).join('')}</select></label></div>`:''}<div data-bulk-keeper-preview="${index}">${entry.reason==='duplicate'&&keeper?deletionPicture(keeper,'Keep this file')+bulkDeleteLinks(keeper):''}</div></div></div>${!choosing?bulkDeleteFacts(entry):''}${busy||done?`<p class="bulk-delete-status" role="status">${esc(bulkDeleteStatus(entry))}${entry.message?' · '+esc(entry.message):''}</p>`:''}</section>`;
  }).join('');
  $('#delete-dialog').innerHTML=`<button class="close" id="bulk-delete-close" aria-label="Close selected-file deletion review" >×</button><span class="eyebrow">DELETE SELECTED ORIGINALS</span><h2>${done?'Deletion results':batch.phase==='checked'?`${count} files ready for confirmation`:batch.phase==='finalizing'?'Preparing confirmation…':choosing?(count?`Review ${count} selected Dropbox file${count===1?'':'s'}`:'No additional files to delete'):`${action}?`}</h2><p class="bulk-delete-intro">${done?'Each result is shown below. Unattempted files remain selected in the gallery.':choosing?'Unwanted image is selected by default. For a duplicate, choose that reason and an image to keep. Selected files cannot be keepers.':'Check every item below. Present files will be deleted from Dropbox; already-absent files will only have their leftover app entries removed.'}</p>${skipped}${deletionReviewFailures(batch)}${batch.phase==='checked'?`<div class="bulk-review-ready">${deletionReviewProgress(batch.review)}${count?`<button class="button dark" id="bulk-review-finalize">Continue with ${count} checked files</button>`:''}</div>`:''}${batch.phase==='finalizing'?'<p role="status">Checking the saved review before confirmation…</p>':''}${choosing?`<form id="bulk-delete-choice-form" ${batch.phase==='preparing'?'inert':''}>${rows}${count?'<button class="button dark" type="submit">Review selected files</button>':''}</form>`:batch.phase==='review'?`<details class="bulk-delete-files"><summary>${count} checked files - expand photographs, sharing and sculpture uses</summary>${rows}</details>`:rows}${batch.phase==='review'?`<p class="small muted">${present} file${present===1?'':'s'} will be deleted from Dropbox; ${absent} missing entr${absent===1?'y':'ies'} will be removed from the app without a deletion request. Other originals and website copies remain. Reviews remain available for 24 hours. Identity, revision, sharing and catalogue use are checked again before deletion.</p><form id="bulk-delete-confirm-form"><label class="check-line"><input id="bulk-delete-confirm" type="checkbox">I have checked all ${count} items and their uses, and will retain any chosen keepers.</label><div class="bulk-delete-actions"><button class="button danger" type="submit" disabled>${action}</button><button class="button" type="button" id="bulk-delete-back">Back</button></div></form>`:''}${done?'<div class="bulk-delete-actions"><button class="button" id="bulk-delete-history">Deletion history</button><button class="button dark" id="bulk-delete-done">Done</button></div>':''}<p class="small muted">Dropbox’s normal deleted-file recovery rules apply. This does not permanently purge recovery history or delete folders.</p><div id="bulk-delete-result" role="status">${esc(batch.error||'')}</div>`;
}
function deletionReviewProgress(job){
  const c=job?.counts||{},done=job?.checked||0,total=job?.total||0;
  const waiting=job?.retry_at&&['queued','running'].includes(job.state);
  const wait=waiting?`<p role="status"><strong>${job.wait_reason==='dropbox_cooldown'?'Waiting for Dropbox':'Waiting to retry a temporary read failure'}</strong>. Remaining checks resume automatically at ${esc(new Date(job.retry_at*1000).toLocaleTimeString())}. Completed checks are saved.</p>`:'';
  return `<p><strong>${done} of ${total} files checked</strong> · ${c.ready||0} ready · ${c.failed||0} need attention · ${c.skipped||0} already handled</p><progress aria-label="Deletion review progress" max="${total||1}" value="${done}"></progress>${wait}<p class="small muted">Checks are read-only and saved as they finish. You can close this window; reopen the review from Jobs. Nothing is deleted until you confirm the checked files.</p>`;
}
function deletionReviewFailures(batch){
  const failures=batch.failures||[];
  if(!failures.length)return '';
  return `<aside class="bulk-delete-skipped"><strong>${failures.length} file(s) could not be checked - excluded from this deletion</strong><p>The checked files can continue. Retry only these failed checks when ready.</p><details><summary>Files needing attention</summary><ul>${failures.map(e=>`<li>${esc(e.name)}<br>${esc(e.error||'Check did not finish')}</li>`).join('')}</ul></details><button class="button" type="button" id="bulk-review-retry">Retry failed checks</button></aside>`;
}
async function prepareBulkDeletion(){
  const batch=bulkDeletion;if(!batch||batch.phase!=='choices'||!batch.entries.length)return;
  const keepers=new Set(bulkDeleteKeepers(batch).map(a=>a.id));
  if(batch.entries.some(e=>e.reason==='duplicate'&&!keepers.has(e.keeper_id))){batch.error='Choose an unselected Dropbox image to keep for each duplicate.';renderBulkDelete();return;}
  batch.phase='preparing';batch.error='';renderBulkDelete();
  // The request ID makes even a lost queue response safe to recover.
  const id=batch.review_id||('review-'+crypto.randomUUID());batch.review_id=id;
  const body={request_id:id,entries:batch.entries.map(e=>({asset_id:e.image.id,reason:e.reason,keeper_id:e.reason==='duplicate'?e.keeper_id:''}))};
  try{
    const job=await api('/api/deletion-reviews',body);
    if(bulkDeletion===batch&&$('#delete-dialog').open){batch.phase='checking_files';batch.review=job;renderBulkDelete();}
    await trackNativeJob(job);
    if(bulkDeletion===batch&&$('#delete-dialog').open)await refreshBulkReview();
  }catch(error){
    let found;try{found=await api('/api/deletion-reviews/'+encodeURIComponent(id));}catch(_){}
    if(bulkDeletion!==batch||!$('#delete-dialog').open)return;
    if(found){batch.phase='checking_files';batch.review=found;renderBulkDelete();await refreshBulkReview();return;}
    batch.phase='choices';batch.error=error.message+' Your selection is retained. Retry to reconnect to the same review.';renderBulkDelete();
  }
}
function absorbDeletionReview(batch,job){
  batch.review=job;batch.failures=job.entries.filter(e=>e.state==='failed'||job.state==='cancelled'&&['pending','checking'].includes(e.state));
  batch.busy=job.entries.filter(e=>e.state==='skipped').flatMap(e=>e.busy_files||[]);
  if(['queued','running'].includes(job.state)){batch.phase='checking_files';return;}
  const images=new Map(batch.entries.map(e=>[e.image.id,e.image]));
  batch.entries=job.entries.filter(e=>e.state==='ready'&&e.plan).map(e=>({image:images.get(e.asset_id)||e.image,reason:e.reason,keeper_id:e.keeper_id,plan:e.plan,status:'not_started'}));
  batch.phase=job.state==='cancelled'?'stopped':'checked';
}
let bulkReviewRefreshBusy=false;
async function refreshBulkReview(){
  const batch=bulkDeletion;
  if(!batch?.review_id||!['checking_files','checked','stopped'].includes(batch.phase)||!$('#delete-dialog').open||bulkReviewRefreshBusy)return;
  bulkReviewRefreshBusy=true;
  try{
    const summary=nativeJobStatus.jobs.find(j=>j.id===batch.review_id);
    const job=summary&&['queued','running'].includes(summary.state)?summary:await api('/api/deletion-reviews/'+encodeURIComponent(batch.review_id));
    if(bulkDeletion!==batch||!$('#delete-dialog').open||!['checking_files','checked','stopped'].includes(batch.phase))return;
    const changed=JSON.stringify(batch.review)!==JSON.stringify(job);
    absorbDeletionReview(batch,job);if(changed)renderBulkDelete();
  }catch(error){if(bulkDeletion===batch&&$('#bulk-delete-result'))$('#bulk-delete-result').textContent='Could not refresh progress. Checks remain saved; reconnect or reopen from Jobs.';}
  finally{bulkReviewRefreshBusy=false;}
}
async function openSavedDeletionReview(id){
  if(state.dirty.size){toast('Save your edits before opening the deletion review.',true);return;}
  ++deletionView;deletePlan=null;
  bulkDeletion={phase:'checking_files',review_id:id,entries:[],skipped:[],busy:[],failures:[],error:''};
  renderBulkDelete();if(!$('#delete-dialog').open)$('#delete-dialog').showModal();await refreshBulkReview();
}
async function finalizeDeletionReview(){
  const batch=bulkDeletion;if(!batch||batch.phase!=='checked'||!batch.entries.length)return;
  batch.phase='finalizing';renderBulkDelete();
  try{
    const plan=await api('/api/deletion-reviews/plan',{review_id:batch.review_id});
    const latest=await api('/api/deletion-reviews/'+encodeURIComponent(batch.review_id));
    if(bulkDeletion!==batch||!$('#delete-dialog').open)return;
    absorbDeletionReview(batch,latest);
    const ids=new Set(plan.files.map(f=>f.id));batch.entries=batch.entries.filter(e=>ids.has(e.image.id));
    batch.plan=plan;batch.phase='review';batch.error='';renderBulkDelete();
  }catch(error){if(bulkDeletion===batch&&$('#delete-dialog').open){batch.phase='checked';batch.error=error.message;await refreshBulkReview();renderBulkDelete();}}
}
async function retryDeletionReview(){
  const batch=bulkDeletion;if(!batch?.review_id||!['checked','stopped'].includes(batch.phase))return;
  batch.phase='checking_files';batch.error='';renderBulkDelete();
  try{const job=await api('/api/deletion-reviews/retry',{review_id:batch.review_id});if(bulkDeletion===batch&&$('#delete-dialog').open){batch.review=job;renderBulkDelete();await refreshBulkReview();}await trackNativeJob(job);}
  catch(error){if(bulkDeletion===batch){batch.phase=batch.review?.state==='cancelled'?'stopped':'checked';batch.error=error.message;renderBulkDelete();}}
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
    reportDeletionJob(job);
  }catch(error){
    // An HTTP response can be lost after the server commits the queue entry.
    // Discover that durable job; never submit a second deletion automatically.
    const found=await findNativeJob('delete-batch-'+batch.plan.batch_id);
    if(found){if(bulkDeletion===batch)closeBulkDelete();reportDeletionJob(found);return;}
    if(bulkDeletion===batch){
      batch.phase=batch.review_id?'checked':error.details?.busy_files?'choices':'review';batch.error=error.message;
      if(error.details?.busy_files){for(const item of error.details.busy_files)nativeJobStatus.deletion_activity[item.file_id]=item;if(!batch.review_id){partitionBusyDeletions(batch);batch.entries.forEach(e=>e.plan=null);}}
      renderBulkDelete();
    }
    else toast(error.message+' Check Jobs before starting another deletion.',true);
  }
}
document.addEventListener('click',async event=>{
  const button=event.target.closest('button');if(!button)return;
  if(button.id==='bulk-delete'){openBulkDelete();return;}
  if(button.id==='bulk-review-finalize'){finalizeDeletionReview();return;}
  if(button.id==='bulk-review-retry'){retryDeletionReview();return;}
  if(button.id==='bulk-delete-retry'){closeBulkDelete();openBulkDelete();return;}
  if(['bulk-delete-close','bulk-delete-done'].includes(button.id)){closeBulkDelete();return;}
  if(button.id==='bulk-delete-back'&&bulkDeletion?.phase==='review'){bulkDeletion.phase=bulkDeletion.review_id?'checked':'choices';renderBulkDelete();return;}
  if(button.id==='bulk-delete-history'){
    closeBulkDelete();await openDeletionHistory();
  }
});
document.addEventListener('change',event=>{
  const element=event.target;
  if(element.id==='bulk-delete-confirm')$('#bulk-delete-confirm-form button[type=submit]').disabled=!element.checked;
  if(!bulkDeletion||bulkDeletion.phase!=='choices')return;
  if(element.hasAttribute('data-bulk-delete-reason')){
    const index=Number(element.dataset.bulkDeleteReason),entry=bulkDeletion.entries[index];entry.reason=element.value;bulkDeletion.review_id=null;
    const choice=$(`[data-bulk-keeper-choice="${index}"]`);choice.hidden=entry.reason!=='duplicate';const select=$('select',choice);select.required=entry.reason==='duplicate';if(entry.reason==='duplicate'&&select.options.length===1)select.insertAdjacentHTML('beforeend',bulkDeleteKeepers(bulkDeletion).map(a=>`<option value="${esc(a.id)}">${esc(a.name)} · ${esc(originalSize(a,true))}</option>`).join(''));
    const keeper=bulkDeleteKeepers(bulkDeletion).find(a=>a.id===entry.keeper_id);
    $(`[data-bulk-keeper-preview="${index}"]`).innerHTML=entry.reason==='duplicate'&&keeper?deletionPicture(keeper,'Keep this file')+bulkDeleteLinks(keeper):'';
  }
  if(element.hasAttribute('data-bulk-delete-keeper')){
    const index=Number(element.dataset.bulkDeleteKeeper),entry=bulkDeletion.entries[index];entry.keeper_id=element.value;bulkDeletion.review_id=null;
    const keeper=bulkDeleteKeepers(bulkDeletion).find(a=>a.id===entry.keeper_id);
    $(`[data-bulk-keeper-preview="${index}"]`).innerHTML=keeper?deletionPicture(keeper,'Keep this file')+bulkDeleteLinks(keeper):'';
  }
});
document.addEventListener('submit',event=>{
  if(event.target.id==='bulk-delete-choice-form'){event.preventDefault();prepareBulkDeletion();}
  if(event.target.id==='bulk-delete-confirm-form'){event.preventDefault();executeBulkDeletion();}
});
document.querySelector('#delete-dialog').addEventListener('cancel',event=>{if(bulkDeletion){event.preventDefault();closeBulkDelete();}});
