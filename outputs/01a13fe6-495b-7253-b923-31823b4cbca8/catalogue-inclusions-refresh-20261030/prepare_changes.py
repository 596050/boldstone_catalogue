"""Prepare a bounded workbook refresh from the complete current app snapshot."""
from pathlib import Path
from collections import Counter
import copy, json

OUT=Path(__file__).resolve().parent
BASE=OUT.parent/'final-upload-preparation-20261030'
read=lambda p:json.loads(Path(p).read_text())
old=read(BASE/'catalogue-snapshot.json'); current=read(OUT/'catalogue-snapshot.json')
expected=read(BASE/'expected-workbook.json'); plan=read(BASE/'upload-plan.json')
assert current['summary']==old['summary']
for key in ('cost_settings','cost_settings_version','image_types'):
    assert current[key]==old[key],key
for a,b in zip(old['images'],current['images']):
    a=copy.deepcopy(a);b=copy.deepcopy(b)
    a['image'].get('provenance',{}).pop('live_inventory_generation',None)
    b['image'].get('provenance',{}).pop('live_inventory_generation',None)
    assert a==b,'Image contents changed; extend refresh before authoring'

main=next(s for s in expected['sheets'] if s['name']=='Wall Sculptures')
upload=next(s for s in expected['sheets'] if s['name']=='Upload Plan')
by_id={p['product_id']:p for p in plan['products']}
patches=[]
def update(sheet,row,column,value):
    former=sheet['rows'][row-8][column]
    if former!=value:
        letters=''; n=column+1
        while n:n,rem=divmod(n-1,26);letters=chr(65+rem)+letters
        patches.append({'sheet':sheet['name'],'cell':letters+str(row),'before':former,'after':value})
        sheet['rows'][row-8][column]=value

for i,(a,p) in enumerate(zip(old['products'],current['products']),8):
    assert a['id']==p['id']==main['rows'][i-8][26]==upload['rows'][i-8][2]
    other={k for k in set(a)|set(p) if a.get(k)!=p.get(k)}-{'listing_decision','review_status'}
    assert not other,(p['id'],other)
    q=by_id[p['id']]
    q['listing_decision']=p['listing_decision'];q['review_status']=p['review_status']
    reminders=[r for r in q['publication_review'] if not r.startswith('Owner listing decision: ') and r!='Component review is not complete']
    if p['listing_decision']!='include':reminders.insert(0,'Owner listing decision: '+p['listing_decision'])
    if p['review_status']!='reviewed':reminders.insert(0,'Component review is not complete')
    q['publication_review']=reminders
    update(main,i,24,p['listing_decision']);update(main,i,25,p['review_status'])
    update(main,i,46,'; '.join(reminders))
    update(upload,i,4,p['listing_decision']);update(upload,i,21,'; '.join(reminders))

decisions=Counter(p['listing_decision'] for p in current['products'])
plan['created_utc']=current['created_utc']
plan['counts']['listing_decisions']=dict(decisions)
plan['counts']['components_with_publication_review']=sum(bool(p['publication_review']) for p in plan['products'])
expected['created_utc']=current['created_utc'];expected['summary']=current['summary']
(OUT/'expected-workbook.json').write_text(json.dumps(expected,ensure_ascii=False))
(OUT/'upload-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2))
(OUT/'workbook-changes.json').write_text(json.dumps({'patches':patches,'decisions':dict(decisions),'created_utc':current['created_utc'],'event_cutoff':current['event_cutoff']},ensure_ascii=False,indent=2))
print(json.dumps({'changed_cells':len(patches),'decisions':dict(decisions),'products':len(current['products']),'event_cutoff':current['event_cutoff']}))
