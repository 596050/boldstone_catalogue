"""Finish the explicit Facebook lifetime export range, through the current day."""
import re,sys
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path[:0]=[str(ROOT/'social-publisher'),str(OUT)]
from source_chrome import SourceChrome
from chrome import Chrome
from settings import Settings
from common import atomic_json,utc
c=SourceChrome(Settings(),OUT/'instagram-source-reader-state');name='verification'
months='January February March April May June July August September October November December'.split()
for count in range(300):
 snap=c.call(name,{'op':'snapshot','scope':[{'selector':'div[data-count="2"]'}],'includeHTML':True})
 matches=re.findall(r'\b('+'|'.join(months)+r') (\d{4})\b',snap['text']);assert len(matches)==2
 month,year=matches[0];year=int(year);index=months.index(month)+1
 if (year,index)==(2026,10):break
 assert (year,index)<(2026,10)
 Chrome.call(c,name,{'op':'click','locator':[{'selector':'div[data-count="2"] [role=button]','name':'Next month','in_view':True}]})
 if count%24==0:print(utc(),month,year,'steps',count+1,flush=True)
else:raise RuntimeError('Current export month not reached')
snap=c.call(name,{'op':'snapshot','scope':[{'selector':'div[data-count="2"]'}],'includeHTML':True});atomic_json(OUT/'meta-facebook-all-history-end-calendar.json',snap)
print(Chrome.call(c,name,{'op':'click','locator':[{'selector':'div[data-count="2"] [role=button]','name':'Friday, 20 November 2026','in_view':True}]}),flush=True)
snap=c.call(name,{'op':'snapshot','fullDocument':True,'includeHTML':True});atomic_json(OUT/'meta-facebook-all-history-range-selected.json',snap);assert '1 Jan 2004 - 20 Nov 2026' in snap['text'];print(snap['text'][-900:],flush=True)
print(Chrome.call(c,name,{'op':'click','locator':[{'selector':'[role=button]','name':'Update','in_view':True}]}),flush=True)
snap=c.call(name,{'op':'snapshot','scope':[{'selector':'[role=dialog]','contains':'Export metric data'}],'includeHTML':True});atomic_json(OUT/'meta-facebook-all-history-export-ready.json',snap);assert '1 Jan 2004 - 20 Nov 2026' in snap['text'];print(snap['text'],flush=True)
