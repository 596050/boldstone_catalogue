"""Select an explicit all-history start date using the native export calendar."""
import json,re,sys
from datetime import date
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path[:0]=[str(ROOT/'social-publisher'),str(OUT)]
from source_chrome import SourceChrome
from chrome import Chrome
from settings import Settings
from common import atomic_json,utc
c=SourceChrome(Settings(),OUT/'instagram-source-reader-state');name='verification'
months='January February March April May June July August September October November December'.split()
scope=[{'selector':'div[data-count="2"]'}]
for count in range(300):
 snap=c.call(name,{'op':'snapshot','scope':scope,'includeHTML':True})
 matches=re.findall(r'\b('+'|'.join(months)+r') (\d{4})\b',snap['text']);assert len(matches)==2
 month,year=matches[0];year=int(year);index=months.index(month)+1
 if (year,index)<=(2004,1):
  atomic_json(OUT/'meta-facebook-all-history-calendar-start.json',snap);print('Start month ready '+month+' '+str(year),flush=True);break
 previous=next(b for b in snap['controls'] if b['name']=='Previous month');assert not previous['disabled'],'Native earliest calendar limit reached'
 Chrome.call(c,name,{'op':'click','locator':[{'selector':'div[data-count="2"] [role=button]','name':'Previous month','in_view':True}]})
 if count%12==0:print(json.dumps({'utc':utc(),'left_month':month,'year':year,'steps':count+1}),flush=True)
else:raise RuntimeError('Calendar scope not reached')
print(Chrome.call(c,name,{'op':'click','locator':[{'selector':'div[data-count="2"] [role=button]','name':'Thursday, 1 January 2004','in_view':True}]}),flush=True)
snap=c.call(name,{'op':'snapshot','fullDocument':True,'includeHTML':True});atomic_json(OUT/'meta-facebook-all-history-start-selected.json',snap);print(snap['text'][-1700:],flush=True)
