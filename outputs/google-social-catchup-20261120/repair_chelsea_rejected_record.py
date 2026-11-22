"""One recorded caption-only edit of the same rejected Google post, never a new post."""
import copy,json,re,sys
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from common import Hold,atomic_json,digest,read_json,utc
from settings import Settings
from google_fast import GoogleFastChrome
from google_business import saved_details,norm
from workflow import Workflow,render
from journal import Store
from engine import Engine
job_id='0b6b60470e10f3743aba398755f1823a';settings=Settings();state=ROOT/'social-publisher/state'
path=state/'evidence'/(job_id+'-google-rejected-revision.json')
assert not path.exists(),'A revision proof already exists; reconcile its original intent only'
main=GoogleFastChrome(settings,state);editor=GoogleFastChrome(settings,OUT/'google-rejection-reader-state')
revised='Chelsea Moonwave — wall relief sculpture\n\nDetail of an original Boldstone wall sculpture by Sally Price. The photograph shows the work’s curved relief, central spiral and textured surface.\n\nFrom the Boldstone sculpture archive. Use Learn more for information about wall sculptures and commissions.'
with Store(state) as store:
 job=store.get(job_id);p=job['payload'];c={**p['profile_snapshot'],**p,'id':job_id}
 assert store.has_intent(job_id) and job['state']=='OUTCOME_UNKNOWN'
 assert settings.fingerprint(p['profile_id'])==p['profile_hash']
 assert not any(e['kind']=='GOOGLE_REJECTED_REVISION_INTENT' and e['job_id']==job_id for e in store.ledger)
 main.navigate('verification',c['inventory_url'],job_id,recovery=True)
 row=[{'selector':'div.J7elmb','contains':c['caption']}]
 snap=main.call('verification',{'op':'snapshot','scope':row,'includeHTML':True})
 caption=main.call('verification',{'op':'snapshot','scope':[{'selector':'div.XNfYrb','text':c['caption']}]})
 status=main.call('verification',{'op':'snapshot','scope':[{'selector':'div.WeJbRc','within':row[0]}]})
 assert norm(status['text'])=='Rejected' and norm(caption['text'])==norm(c['caption'])
 ids=set(re.findall(r'data-post-name="accounts/-/locations/(\d+)/localPosts/(\d+)"',snap['html']));assert ids=={(c['location_id'],'6367692611203319285')}
 native=c['inventory_url']+'/6367692611203319285/edit';assert editor.bindings['verification']['url']==native
 recipe=settings.workflow(settings.profile(p['profile_id']));photo=editor.confirm_upload_preview('verification',recipe['google_photo'],c)
 saved=editor.call('verification',{'op':'snapshot','fullDocument':True,'includeHTML':True});saved_details(saved,photo,c)
 # Release only the exact, independently proven rejected local composer.
 writer=c['profile_id'];binding=main.bindings[writer];assert binding['job_id']==job_id and binding['url']==c['compose_url']
 main.confirm_upload_preview(writer,recipe['google_photo'],c)
 main.call(writer,{'op':'assert','checks':[{'locator':[{'selector':'textarea[maxlength="1500"]'}],'text':c['caption']},{'locator':[{'selector':'input[type=url]'}],'text':c['purchase_url']}]})
 before=main.call(writer,{'op':'snapshot','fullDocument':True});atomic_json(OUT/'chelsea-rejected-local-composer-before-release.json',before)
 main.call(writer,{'op':'click','locator':[{'selector':'main div[data-file-id] button','name':'Delete photo'}]})
 for selector in ['textarea[maxlength="1500"]','input[type=url]']:main.call(writer,{'op':'set_text','locator':[{'selector':selector}],'value':''})
 clean=main.call(writer,{'op':'clean_state',**recipe['clean_state']});assert clean['clean']
 atomic_json(OUT/'chelsea-rejected-local-composer-after-release.json',{'utc':utc(),'clean':clean,'independent_rejected_record':{'snapshot':snap,'caption':caption,'status':status}})
 main.checkpoint(writer,0,dirty=False);main.navigate(writer,c['inventory_url'],job_id,recovery=True)
 # This editor belongs to the existing post id; only its description changes.
 editor.call('verification',{'op':'set_text','locator':[{'selector':'textarea[maxlength="1500"]'}],'value':revised,'focus':True})
 updated={**c,'caption':revised};guards=Workflow(settings,editor,editor.directory).guards(recipe,updated)
 for guard in guards:
  if guard.get('purpose')=='account':guard['locator']=[{'selector':'h1','text':'Edit update'}];guard['text']='Edit update'
 editor.confirm_upload_preview('verification',recipe['google_photo'],updated)
 ready=editor.call('verification',{'op':'assert','checks':guards,'job':job_id,'mediaSha256':c['media_sha256']})
 changed=editor.call('verification',{'op':'snapshot','fullDocument':True,'includeHTML':True})
 proof={'utc':utc(),'job_id':job_id,'profile_hash':p['profile_hash'],'location_id':c['location_id'],'post_id':'6367692611203319285','native_url':native,'original_caption':c['caption'],'revised_caption':revised,'media_sha256':c['media_sha256'],'verification_attempts_before_revision':job['verify_attempts'],'rejected_record':{'snapshot':snap,'caption':caption,'status':status},'original_saved_editor':saved,'original_photo':photo,'revised_editor':changed,'ready':ready,'same_existing_native_record':True,'caption_only':True,'new_post_created':False,'max_revision_attempts':1}
 atomic_json(path,proof)
 store.event('GOOGLE_REJECTED_REVISION_INTENT',job_id=job_id,evidence_path=str(path.resolve()),evidence_sha256=digest(path.read_bytes()),native_url=native)
 result=editor.call('verification',{'op':'submit_google_rejected_revision','job':job_id,'mediaSha256':c['media_sha256'],'nativeURL':native,'originalCaption':c['caption'],'revisedCaption':revised,'rejectionEvidenceSha256':digest(path.read_bytes()),'checks':guards})
 atomic_json(OUT/'chelsea-rejected-existing-record-edit-result.json',{'utc':utc(),'result':result,'proof_path':str(path.resolve()),'proof_sha256':digest(path.read_bytes())})
 try:Engine(store,Workflow(settings,main,state),settings.policy).reconcile(job_id,native_url=native)
 except Exception as error:print('READ_ONLY_RECONCILIATION_PENDING',str(error),flush=True)
 store.export();store.backup();print(json.dumps({'state':store.get(job_id)['state'],'native_url':native,'same_existing_post':True}),flush=True)
