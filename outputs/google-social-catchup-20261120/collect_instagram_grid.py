"""Inventory the complete visible owned profile grid, without opening editors."""
import json,re,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'social-publisher'))
from source_chrome import SourceChrome
from settings import Settings
from common import atomic_json,utc
c=SourceChrome(Settings(),OUT/'instagram-reader-state');name='verification'
items={};stable=0
for step in range(250):
 s=c.call(name,{'op':'source_grid'});before=len(items)
 for item in s['items']:items[item['url']]=item
 m=re.search(r'([\d,]+) posts',s['profile_text']);expected=int(m.group(1).replace(',','')) if m else None
 stable=stable+1 if len(items)==before and s['at_bottom'] else 0
 result={'utc':utc(),'profile':'boldstonesculpture','expected_profile_posts':expected,'collected':len(items),'scroll_steps':step,
         'at_bottom':s['at_bottom'],'status':'GRID_COMPLETE' if expected==len(items) else 'GRID_IN_PROGRESS','items':list(items.values())}
 atomic_json(OUT/'instagram-full-grid-inventory.json',result)
 if step%10==0 or len(items)!=before:print(json.dumps({k:v for k,v in result.items() if k!='items'}),flush=True)
 if len(items)==expected or stable>=8:break
 c.call(name,{'op':'scroll_page'});time.sleep(.6)
