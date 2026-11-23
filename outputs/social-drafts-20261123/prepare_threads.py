"""Fill Threads composers for review without posting."""
from browser_drafts import browser,OUT
from common import atomic_json
import sys,json

def prepare(index):
 c=browser('threads'+str(index));name='boldstone_threads';p=json.loads((OUT/'posts.json').read_text())['posts'][index-1];jid='threads-draft-'+p['catalogue_id']
 c.call(name,{'op':'claim'})
 if not c.call(name,{'op':'exists','locator':[{'selector':'[role=dialog] [contenteditable=true][role=textbox]'}]})['exists']:
  c.call(name,{'op':'click','locator':[{'selector':'[role=button]','name':'New thread'}]})
 checks=[{'purpose':'account','locator':[{'selector':'[role=dialog]'}],'contains':'boldstonesculpture'}]
 c.call(name,{'op':'assert','checks':checks})
 c.call(name,{'op':'begin_job','job':jid})
 c.call(name,{'op':'set_text','locator':[{'selector':'[role=dialog] [contenteditable=true][role=textbox]'}],'value':p['captions']['threads'],'method':'paste'})
 c.checkpoint(name,1,dirty=True)
 ctx={**p,'id':jid,'media_sha256':p['sha256']}
 r=c.upload(name,ctx,[{'selector':'input[type=file]','hidden':True}],method='input',guards=checks)
 print(json.dumps({'title':p['title'],'upload':r}),flush=True)
 r=c.call(name,{'op':'snapshot','scope':[{'selector':'[role=dialog]'}]});atomic_json(c.directory/'prepared-native.json',r)
 print(json.dumps({'text':r['text'],'controls':r['controls'],'fileInputs':r.get('fileInputs'),'images':[{'src':i['src'],'alt':i['alt'],'width':i['width'],'height':i['height']} for i in r['images']]},ensure_ascii=False),flush=True)
if __name__=='__main__':prepare(int(sys.argv[1]))
