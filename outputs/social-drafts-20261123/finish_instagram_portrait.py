"""Native Instagram crop and tag readback for this retained draft batch only."""
import sys,json,time,urllib.request
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT/'social-publisher'))
from settings import Settings
from preparation import PreparationOnlyChrome
from workflow import Workflow,render
from common import atomic_json,utc
index=int(sys.argv[1]);posts=json.loads((OUT/'posts.json').read_text())['posts'];post=posts[index-1]
settings=Settings();job=next(j for j in settings.jobs(OUT/'remaining-manifest.json',require_authorized=False) if j['post_key']==post['post_key'] and j['payload']['platform']=='instagram')
state=ROOT/'social-publisher/state/drafts/component-sculptures-drafts-20261123-remaining-d10b634f'/job['id'];c=PreparationOnlyChrome(settings,state);n='boldstone_instagram';w=Workflow(settings,c,state);ctx=w.context(job);recipe=settings.workflow(settings.profile(n))
c.call(n,{'op':'assert','checks':[g for g in w.guards(recipe,ctx) if g.get('purpose') in ['account','caption','schedule','boost']]})
c.bind('verification',962002858,962002881)
panel=[{'selector':'[role=dialog]','contains':'Creative tools','painted':True}]
c.call(n,{'op':'click','locator':[{'selector':'[role=button]','name':'Edit photo'}]});w.wait(n,panel)
c.call(n,{'op':'click','locator':[{'selector':'[role=dialog] [role=button]','name':'Vertical 4:5','within':{'selector':'[role=dialog]','contains':'Creative tools'}}]})
c.call(n,{'op':'click','locator':[{'selector':'[role=dialog] [role=button]','name':'Apply','within':{'selector':'[role=dialog]','contains':'Creative tools'}}]});w.wait_absent(n,panel)
deadline=time.monotonic()+30
while True:
 snapshot=c.call(n,{'op':'snapshot'});images=[i for i in snapshot['images'] if 'xjnjwiz' in i['html']]
 if len(images)==1 and abs(images[0]['width']/images[0]['height']-.8)<.003:break
 if time.monotonic()>deadline:raise RuntimeError('Native 4:5 photograph did not finish loading')
 time.sleep(.3)
im=images[0];(OUT/(post['catalogue_id']+'-instagram-native-crop.jpg')).write_bytes(urllib.request.urlopen(im['src'],timeout=20).read())
atomic_json(state/'native-crop-readback.json',snapshot)
w.photo_alt(n,render(next(s for s in recipe['prepare'] if s['op']=='photo_alt'),ctx))
ready=w.prepare(job);binding=c.bindings[n]
result={'id':job['id'],'post_key':job['post_key'],'title':post['title'],'profile_id':n,'window_id':binding['window_id'],'tab_id':binding['tab_id'],'state':'PREPARED_NOT_PUBLISHED','ready':ready,'crop':'Native 4:5 crop, original source retained','publish_clicks':0,'verified_utc':utc()}
atomic_json(state/'preparation-result.json',result);print(json.dumps(result,ensure_ascii=False))
