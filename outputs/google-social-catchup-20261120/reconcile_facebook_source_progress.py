"""Match native Facebook photo stories to frozen Meta and Instagram sources."""
import collections,json,re,sys,unicodedata
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,utc
def norm(s):
 s=re.sub(r'https?://\S+','',s);s=re.sub(r'#\w+','',s);s=re.sub(r'(?i)\bsee (?:less|more)\s*$','',s)
 return ' '.join(unicodedata.normalize('NFKC',s).casefold().replace('\u200b','').replace('\ufeff','').split()).rstrip(' .…')
meta=collections.defaultdict(list);legacy=collections.defaultdict(list)
for r in json.loads((OUT/'history-audit.json').read_text())['groups']:
 if norm(r['caption']):meta[norm(r['caption'])].append(r['source_key'])
for r in json.loads((OUT/'history-review-decisions-legacy.json').read_text())['decisions']:
 if norm(r['caption']):legacy[norm(r['caption'])].append({'source_key':r['source_key'],'shortcode':r['shortcode'],'decision':r['decision']})
rows=json.loads((OUT/'facebook-native-photo-history.json').read_text());matched=[];unmatched=[]
associations={r['photo_id']:r['meta_source_key'] for r in json.loads((OUT/'facebook-album-photo-associations.json').read_text())['associations']} if (OUT/'facebook-album-photo-associations.json').exists() else {}
for r in rows:
 text=norm(r['caption']);m=meta[text] if text else [];l=legacy[text] if text else []
 if r['photo_id'] in associations:m=list(set(m+[associations[r['photo_id']]]))
 result={'photo_id':r['photo_id'],'native_parent':r['canonical_parent'],'date':r['date']['text'],'caption':r['caption'],'meta_source_keys':m,'legacy_candidates':l,'in_2026_export_by_permalink':r['in_2026_export'],'native_evidence_path':r['evidence_path'],'native_evidence_sha256':r['evidence_sha256']}
 if r['in_2026_export'] or m:matched.append(result)
 else:unmatched.append(result)
progress=json.loads((OUT/'facebook-native-photo-history-progress.json').read_text())
atomic_json(OUT/'facebook-photo-source-reconciliation-progress.json',{'utc':utc(),'native_collection_status':progress['status'],'native_photos_read':len(rows),'matched_2026_posts':len(matched),'unmatched_native_photos':len(unmatched),'matched':matched,'unmatched':unmatched})
print(json.dumps({'photos_read':len(rows),'matched_2026':len(matched),'review_needed':len(unmatched),'native_status':progress['status']}))
