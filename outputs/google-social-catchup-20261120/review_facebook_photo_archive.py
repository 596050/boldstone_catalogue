"""Record the visual scope decisions for all otherwise-unmatched Facebook photos."""
import json,sys
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,digest,utc
rows=json.loads((OUT/'facebook-unmatched-final-index.json').read_text());excluded=set()
for a,b in [(45,83),(118,140),(232,238),(249,251),(253,269),(274,284),(286,288),(299,306),(308,308)]:excluded.update(range(a,b+1))
paired={r['photo_id']:r for r in json.loads((OUT/'facebook-paired-photo-visual-confirmation.json').read_text())['confirmations']}
new={'968769045393133':'FACEBOOK-ARCHIVE-968769045393133','406915868245123':'FACEBOOK-ARCHIVE-406915868245123','103781881870689':'FACEBOOK-ARCHIVE-406915868245123'}
records=[]
for i,r in enumerate(rows):
 proof=OUT/('facebook-unmatched-final-%02d.jpg'%(i//48+1))
 decision='EXCLUDE_NON_SCULPTURE' if i in excluded else 'COVERED_SAME_SOURCE_PHOTOGRAPH' if r['photo_id'] in paired else 'INCLUDE_FACEBOOK_ONLY' if r['photo_id'] in new else 'SCULPTURE_ALBUM_ATTACHMENT'
 reason='Reviewed photograph depicts functional furniture, lighting, mirrors, bowls, drawing, nature, architecture, unrelated subject or brand/avatar graphic' if i in excluded else 'Original Boldstone sculpture or sculpture surface study; album parent and same-photograph coverage reconciled separately'
 records.append({**r,'review_index':i,'decision':decision,'reason':reason,'google_post_keys':paired.get(r['photo_id'],{}).get('google_post_keys',[]) or ([new[r['photo_id']]] if r['photo_id'] in new else []),'visual_review_path':str(proof.resolve()),'visual_review_sha256':digest(proof.read_bytes())})
atomic_json(OUT/'facebook-photo-review-decisions.json',{'utc':utc(),'scope':'All 309 native Facebook photos not directly matched to the 2026 export; all seven contact sheets reviewed','decisions':records})
print({d:sum(r['decision']==d for r in records) for d in sorted({r['decision'] for r in records})})
