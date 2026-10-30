from pathlib import Path
import collections,json,time,urllib.request
here=Path(__file__).resolve().parent
base='http://127.0.0.1:8767'
def get(path):
    with urllib.request.urlopen(base+path,timeout=30) as response:return json.load(response)
start=time.monotonic();specs=get('/api/specifications');coverage=get('/api/coverage');checks=0;records=[]
for p in specs['products']:
    pid=p['id'];overview=get('/api/component-overview/'+pid);photos=p['photos'];cover=coverage['products'][pid]
    selected={a['id'] for a in overview['images'] if 'listing' in a['selected_uses'] and not a['excluded']}
    assert selected==set(overview['listing_ids']),pid;checks+=1
    assert photos['listing']['count']==len(selected),pid;checks+=1
    assert [a['id'] for a in photos['listing']['images']]==overview['listing_ids'][:6],pid;checks+=1
    assert photos['in_situ']['count']==cover['in_situ']['count'],pid;checks+=1
    assert [a['id'] for a in photos['in_situ']['images']]==cover['in_situ']['image_ids'][:6],pid;checks+=1
    assert photos['primary_listing']==cover['primary_listing']==overview['primary_listing'],pid;checks+=1
    assert overview['primary_id'] is None or overview['primary_id'] in selected,pid;checks+=1
    assert len(overview['product']['fields'])==len(p['fields']),pid;checks+=1
    assert len(photos['listing']['images'])<=6 and len(photos['in_situ']['images'])<=6,pid;checks+=1
    records.append({'id':pid,'listing':len(selected),'situ':photos['in_situ']['count'],
                    'primary':photos['primary_listing']['status'],'fields':len(p['fields'])})
result={'health':get('/api/health'),'components':len(records),'checks_passed':checks,
        'primary_statuses':dict(collections.Counter(p['primary'] for p in records)),
        'seconds':round(time.monotonic()-start,3),'records':records}
(here/'live-audit.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='records'}))
