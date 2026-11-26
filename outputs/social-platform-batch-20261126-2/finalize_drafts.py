"""Read back retained drafts; keep original tall photos flagged for framing review."""
from pathlib import Path
import copy,json,sys
OUT=Path(__file__).resolve().parent;sys.path.insert(0,str(OUT.parents[1]/'social-publisher'))
from settings import Settings
from preparation import PreparationOnlyChrome
from workflow import Workflow,render
from common import atomic_json,read_json,utc,Hold

settings=Settings(OUT/'draft-config/profiles.json');jobs=settings.jobs(OUT/'combined-draft-manifest.json',require_authorized=False)
completed_only='--completed-only' in sys.argv
report=OUT/('native-draft-final-progress.json' if completed_only else 'native-draft-results.json')
results=[]
for job in jobs:
 directory=OUT/'native-drafts'/job['id']
 if completed_only and not (directory/'preparation-result.json').exists():continue
 result=read_json(directory/'preparation-result.json');name=job['payload']['profile_id']
 if result.get('final_readback_complete'):
  results.append(result);continue
 c=PreparationOnlyChrome(settings,directory);w=Workflow(settings,c,directory);context=w.context(job);recipe=settings.workflow(settings.profile(name))
 try:
  assert c.bindings[name]['job_id']==job['id']
  s=c.call(name,{'op':'snapshot','fullDocument':True})
  if name=='boldstone_facebook':
   alt_step=render(next(step for step in recipe['prepare'] if step['op']=='photo_alt'),context)
   if c.call(name,{'op':'exists','locator':alt_step['panel']})['exists']:
    # Close only our prior read-only crop inspection, preserving the photograph.
    c.call(name,{'op':'click','locator':alt_step['cancel']});w.wait_absent(name,alt_step['panel'])
   step=render(next(step for step in recipe['prepare'] if step['op']=='product_tag'),context)
   c.call(name,{'op':'click','locator':step['open']});w.wait(name,step['heading'])
   proof=c.call(name,{'op':'attest_product_tag','tag':context['product_tag'],'job':job['id'],'mediaSha256':context['media_sha256'],'panel':step['panel'],'heading':step['heading'],'markers':step['markers']})
   atomic_json(directory/'evidence'/(job['id']+'-product-tag-final.json'),{'utc':utc(),'job_id':job['id'],**proof})
   c.call(name,{'op':'click','locator':step['cancel']});w.wait_absent(name,step['panel'])
   s=c.call(name,{'op':'snapshot','fullDocument':True})
   crop_warning="Instagram will automatically crop this original tall photograph. Review the framing before publishing; the full original photograph is retained." if 'Photo will be auto-cropped' in s['text'] or 'Photo(s) will be auto-cropped' in s['text'] else None
   guards=w.guards(recipe,context);badge=c.call(name,{'op':'exists','locator':step['badge']})['exists']
   if not badge:
    # Some combined composers omit the thumbnail count. Retain the stricter
    # publish recipe unchanged. This prepare-only readback uses the exact saved
    # name, price and single marker in the reopened native tagging editor above,
    # correlated with the committed photo and the document's tag receipt.
    guards=copy.deepcopy(guards)
    for guard in guards:
     if guard.get('purpose')=='tag':
      guard['locator']=next(g['locator'] for g in guards if g.get('purpose')=='photo')
      guard.pop('text',None);guard['image']=True
   ready=c.call(name,{'op':'ready','job':job['id'],'mediaSha256':context['media_sha256'],'checks':guards,'submit':render(recipe['submit'],context)})
   result.update(product_tag_verified=True,product_tag=proof['product_tag'],thumbnail_tag_count_visible=badge,crop_warning=crop_warning,ready=ready)
   if crop_warning:
    result.update(state='PREPARED_REQUIRES_CROP_REVIEW',code='INSTAGRAM_AUTO_CROP',detail=crop_warning)
   elif not badge:
    result.update(state='PREPARED_REQUIRES_TAG_REVIEW',code='THUMBNAIL_TAG_COUNT_ABSENT',detail='Exact persisted product tag was verified in its editor; inspect the final preview before publishing.')
   else:
    result.update(state='PREPARED_NOT_PUBLISHED');result.pop('code',None);result.pop('detail',None)
  else:
   result['ready']=c.call(name,{'op':'ready','job':job['id'],'mediaSha256':context['media_sha256'],'checks':w.guards(recipe,context),'submit':render(recipe['submit'],context)})
  upload=c.call(name,{'op':'upload_status','job':job['id'],'mediaSha256':context['media_sha256']})
  assert upload.get('committed') and upload.get('sha256')==context['media_sha256']
  label=('FB + IG' if name=='boldstone_facebook' else 'Threads')+' · '+context['title']+' · Draft'
  c.call(name,{'op':'label_draft','title':label})
  snap=c.call(name,{'op':'snapshot','fullDocument':True,'includeHTML':True});assert snap['title']==label
  atomic_json(directory/'prepared-native-final.json',snap)
  result.update(verified_utc=utc(),caption=context['caption'],media_sha256=context['media_sha256'],upload=upload,native_snapshot_path=str(directory/'prepared-native-final.json'),final_readback_complete=True)
 except Exception as error:
  result.update(state='HELD',code=getattr(error,'code',type(error).__name__),detail=str(error))
 finally:c.close()
 atomic_json(directory/'preparation-result.json',result);results.append(result)
 atomic_json(report,{'utc':utc(),'mode':'prepare_only','drafts':results,'prepared_composers':sum(r['state'].startswith('PREPARED_') for r in results),'ready_composers':sum(r['state']=='PREPARED_NOT_PUBLISHED' for r in results),'publish_clicks':0,'publish_intents_written_by_this_worker':0,'outbox_jobs_added_by_this_worker':0})
 print(json.dumps({'title':result['title'],'platforms':result['platforms'],'state':result['state'],'detail':result.get('detail')},ensure_ascii=False),flush=True)
atomic_json(report,{'utc':utc(),'mode':'prepare_only','drafts':results,'prepared_composers':sum(r['state'].startswith('PREPARED_') for r in results),'ready_composers':sum(r['state']=='PREPARED_NOT_PUBLISHED' for r in results),'publish_clicks':0,'publish_intents_written_by_this_worker':0,'outbox_jobs_added_by_this_worker':0})
