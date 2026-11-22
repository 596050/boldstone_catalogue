"""Record the completed native Instagram history review without caption deduplication."""
import json,sys
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,digest,utc

photos=json.loads((OUT/'legacy-photo-review-index.json').read_text())
selected={0,2,3,4,5,14,15,31,32,36,58,60,61,62,63,64,65,67,122,123,125,129,135,136,137,138,140,143,145,154,158,162,166,170,174,178,182,185,195,205,207,209,217,219,226,227,233,236,237,238,240,244,246,250,253,255,256,258,263,265,269,271,273,276,279,283,286,291,296,301,305,308,314,318}
included={photos[i]['shortcode'] for i in selected}
included.update({'DQbP4ROgGhK','DK9gpyKtxOb','DKwYzsytXsz','DKtlo1SN73f','DKhhnxstVTu','CrTxUyFr6JC','CnkQUMtoiNB','CY47NtvombA','B7tVYmrAxGH'})
review={'DQXt7QaiCFe','CVnER00IZ9u','CLMEWsNBrNO','CK9HAftjsHx','CCRUhY9A8MO','CFT8jAgDnbM'}
by_code={r['shortcode']:r for r in photos}
records=[]
for row in json.loads((OUT/'instagram-native-history-posts.json').read_text()):
 source=row['source'];date=min(t['datetime'] for t in source['times'])
 if row['in_2026_export']:continue
 code=row['shortcode'];photo=by_code.get(code)
 decision='INCLUDE_SCULPTURE' if code in included else 'IMAGE_REVIEW_REQUIRED' if code in review else 'EXCLUDE_NON_SCULPTURE'
 reason='Original Boldstone sculpture or sculpture studio work; native cover and caption reviewed' if code in included else 'Caption is ambiguous or absent; retrieve original cover before a scope decision' if code in review else 'Native cover or original caption identifies nature, drawing, painting, furniture, other artist, architecture or unrelated subject'
 if code=='DKmJDySN4bV':decision='COVERED_2026';reason='Exact same original caption represented by the 2026 Facebook source group'
 key=digest('instagram-history:'+code)
 records.append({'source_key':key,'legacy_caption_key':row['source_key'],'shortcode':code,'decision':decision,'reason':reason,
  'caption':source['caption'],'sources':[{'platform':'instagram','post_id':'instagram:'+code,'url':source['url'],'post_type':'IG reel' if source.get('videos') else 'IG image','publish_time':date}],
  'native_record':row,'photo':photo,'visual_review_index':photos.index(photo) if photo else None})
assert len(records)==390 and len({r['source_key'] for r in records})==390
atomic_json(OUT/'history-review-decisions-legacy.json',{'utc':utc(),'scope':'All 390 native Instagram posts before 2026; source identity is shortcode, not caption','decisions':records})
print({d:sum(r['decision']==d for r in records) for d in sorted({r['decision'] for r in records})})
