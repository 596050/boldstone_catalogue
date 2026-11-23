"""Leave native FB/IG composers ready for human review; never submit."""
from browser_drafts import browser,OUT,ROOT
from workflow import Workflow,render
from common import atomic_json
from upload_bridge import UploadClient
import json,sys

def prepare(index,phase='all'):
 key='meta'+str(index);c=browser(key);name='boldstone_facebook';p=json.loads((OUT/'posts.json').read_text())['posts'][index-1];profile=c.settings.profile(name)
 jobid='draft-'+p['catalogue_id'];ctx={**profile,**p,'profile_id':name,'id':jobid,'job':jobid,'mediaSha256':p['sha256'],'caption':p['captions']['facebook'],'product_tag':{'name':p['title'],'price_text':'£'+format(p['price_gbp'],'.2f')}}
 w=Workflow(c.settings,c,c.directory);recipe=c.settings.workflow(profile)
 if phase in ('all','base'):
  c.begin(name,jobid,profile['compose_url'])
  combo=[{'selector':'[role=combobox][aria-haspopup=listbox]'}]
  if not c.call(name,{'op':'exists','locator':[{'selector':'[role=combobox][aria-haspopup=listbox][aria-expanded=true]'}]})['exists']:c.call(name,{'op':'click','locator':combo})
  for account in ['Boldstone Sculpture','boldstonesculpture']:w.set_checked(name,[{'selector':'[role=option]','name':account}],True)
  c.call(name,{'op':'click','locator':combo})
  for s in recipe['prepare']:
   if s['op']=='set_checked' and s['locator'][0].get('name') in ['Set date and time','Boost','Share to Facebook story']:
    if s.get('if_exists') and not c.call(name,{'op':'exists','locator':s['locator']})['exists']:continue
    w.set_checked(name,s['locator'],False,confirmation=s.get('confirmation'))
  c.call(name,{'op':'set_text','locator':[{'selector':'[contenteditable=true][role=combobox]','name':'Write in the dialogue box to include text with your post.'}],'value':ctx['caption'],'method':'paste'})
  c.checkpoint(name,1,dirty=True)
 if phase in ('all','base','upload'):
  combo=[{'selector':'[role=combobox][aria-haspopup=listbox]'}]
  guard=[{'purpose':'account','locator':combo,'contains':'Boldstone Sculpture and boldstonesculpture'},{'purpose':'schedule','locator':[{'selector':'input[type=checkbox]','name':'Set date and time'}],'checked':False}]
  c.upload_client=UploadClient(ROOT/'social-publisher/state')
  try:result=c.upload(name,ctx,[{'selector':'[role=button]','name':'Add photo/video'}],method='helper',preview=[{'selector':"img[data-imgperflogname='feedImage']"}],guards=guard);print(json.dumps({'phase':'uploaded','title':p['title'],'result':result}),flush=True)
  finally:c.upload_client.close()
 if phase in ('all','tag'):
  alt=next(s for s in recipe['prepare'] if s['op']=='photo_alt');w.photo_alt(name,render(alt,ctx))
  step=next(s for s in recipe['prepare'] if s['op']=='product_tag');r=w.product_tag(name,ctx,render(step,ctx));print(json.dumps({'phase':'tagged','title':p['title'],'result':r}),flush=True)
  checks=[render(g,ctx) for g in recipe['ready'] if g.get('purpose')!='account']
  checks.insert(0,{'purpose':'account','locator':[{'selector':'[role=combobox][aria-haspopup=listbox]'}],'contains':'Boldstone Sculpture and boldstonesculpture'})
  c.call(name,{'op':'assert','checks':checks,'job':jobid,'mediaSha256':p['sha256']})
  r=c.call(name,{'op':'snapshot'});atomic_json(c.directory/'prepared-native.json',r);print(json.dumps({'prepared':p['title'],'window_id':c.bindings[name]['window_id'],'tab_id':c.bindings[name]['tab_id']}),flush=True)
if __name__=='__main__':prepare(int(sys.argv[1]),sys.argv[2] if len(sys.argv)>2 else 'all')
