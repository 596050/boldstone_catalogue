import json,sys
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,digest,utc
file=OUT/'history-review-decisions-legacy.json';data=json.loads(file.read_text())
include={'DQXt7QaiCFe','CVnER00IZ9u'};exclude={'CLMEWsNBrNO','CK9HAftjsHx','CCRUhY9A8MO','CFT8jAgDnbM'}
for row in data['decisions']:
 if row['shortcode'] in include:row.update(decision='INCLUDE_SCULPTURE',reason='Original material/finish study or standalone sculptural cuboid; public embed cover reviewed')
 if row['shortcode'] in exclude:row.update(decision='EXCLUDE_NON_SCULPTURE',reason='Public embed cover reviewed: drawing, print or nature photograph')
data['utc']=utc();data['visual_review_evidence']={'contact_sheet':'legacy-embed-review.jpg','sha256':digest((OUT/'legacy-embed-review.jpg').read_bytes()),'covers_reviewed':15}
atomic_json(file,data)
print({d:sum(r['decision']==d for r in data['decisions']) for d in sorted({r['decision'] for r in data['decisions']})})
