"""Make a bounded, reviewable duplicate/orientation diagnosis; never write to Brandboom."""
from compare_gallery import OUT, PACKET, load, fetch, distance, source_thumb
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageChops, ImageStat
import json

plan=load(PACKET/'brandboom-restore-plan.json')['records']
public=load(PACKET/'current-public-images-verified.json')
diagnoses=[];rotation_rows=[];pictures=[]
for record in plan:
    comparison=load(OUT/(record['sku']+'-comparison.json'))
    if comparison['native_count']==comparison['expected_count']:continue
    native_rows=comparison['comparisons']
    inputs=[{'kind':'native','key':r['native_media_id'],'url':r['native_rendition_url']} for r in native_rows]
    inputs += [{'kind':'expected','key':photo,'url':source_thumb(public[photo]['url'])} for photo in record['image_ids']]
    with ThreadPoolExecutor(max_workers=3) as pool:images=list(pool.map(fetch,inputs))
    natives={i['key']:i for i in images if i['kind']=='native'}
    sources={i['key']:i for i in images if i['kind']=='expected'}
    source_by_native={r['native_media_id']:r['assigned_source_id'] for r in native_rows}
    for row in native_rows:
        if row['assigned_source_id'] is not None:continue
        extra=natives[row['native_media_id']]
        candidates=sorted((distance(extra,other),key) for key,other in natives.items() if key!=extra['key'])
        difference,closest=candidates[0]
        source_id=source_by_native[closest]
        diagnosis={'sku':record['sku'],'catalogue_id':record['catalogue_id'],'title':record['title'],
            'extra_native_media_id':extra['key'],'closest_retained_native_media_id':closest,
            'closest_retained_assigned_source_id':source_id,
            'native_pair_mean_absolute_pixel_difference':round(difference,6),
            'identical_native_response_bytes':extra['response_sha256']==natives[closest]['response_sha256'],
            'extra_is_primary':extra['key']==native_rows[0]['native_media_id']}
        diagnoses.append(diagnosis)
        pictures.append((diagnosis,extra['thumb'],natives[closest]['thumb'],sources[row['best_source_id']]['thumb']))
    for row in native_rows:
        source_id=row['assigned_source_id']
        if not source_id or row['mean_absolute_pixel_difference']<10:continue
        native=natives[row['native_media_id']];expected=sources[source_id]
        scores={angle:sum(ImageStat.Stat(ImageChops.difference(native['normalized'].rotate(angle),expected['normalized'])).mean)/3 for angle in [0,90,180,270]}
        angle=min(scores,key=scores.get)
        rotation_rows.append({'sku':record['sku'],'catalogue_id':record['catalogue_id'],'title':record['title'],
            'native_media_id':native['key'],'selected_source_id':source_id,
            'best_counterclockwise_rotation_degrees':angle,
            'mean_pixel_differences':{str(k):round(v,6) for k,v in scores.items()},
            'native_is_primary':row['native_media_id']==native_rows[0]['native_media_id']})

canvas=Image.new('RGB',(900,190*len(pictures)),'white');draw=ImageDraw.Draw(canvas)
for index,(diagnosis,extra,retained,source) in enumerate(pictures):
    y=index*190
    draw.text((10,y+3),diagnosis['sku']+' | extra '+diagnosis['extra_native_media_id']+' | pair delta '+str(diagnosis['native_pair_mean_absolute_pixel_difference']),fill='black')
    for x,photo,label in [(10,extra,'Extra'),(235,retained,'Closest retained'),(460,source,'Catalogue reference')]:
        draw.text((x,y+20),label,fill='black');canvas.paste(photo,(x,y+40))
canvas.save(OUT/'extra-photo-pairs-review.jpg',quality=88)
report={'checked_at':datetime.now(timezone.utc).isoformat(),'status':'REVIEW_ONLY_NO_NATIVE_CHANGES',
    'count_discrepancies':diagnoses,'orientation_candidates':rotation_rows,
    'qualification':'Comparison of rendered public renditions with exact saved native IDs. Inspect pictures before any association change. No Dropbox files or app choices changed.'}
(OUT/'extra-photo-diagnosis.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2),flush=True)
