"""Close a superseded root handoff and expose the current incremental work."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

H = Path(__file__).resolve().parent
ROOT = H.parents[1]
B = ROOT / 'sculpture-catalogue'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
dump = lambda p,x: Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
now = datetime.now(timezone.utc).isoformat()
pfile = B / 'current-master.json'
p = read(pfile)
assert sha(pfile) == '9083266b288bfef81f806c3975a18a8dc1bb5268a984152de64852bbd5bf3c1c'
g = read(B / p['register'])
assert sha(B / p['register']) == p['register_sha256']
options = {o['product_id']:o for o in g['options']}
index_binding = p['current_source_photo_review_index']
index_file = B / index_binding['path']
assert sha(index_file) == index_binding['sha256']
index = read(index_file)
queue = ROOT / 'reports/catalogue-terminal-walkthrough-20261024/next-source-review-handoff.json'
q = read(queue)
assert q['status'] == 'NEXT_LOCAL_SOURCE_REVIEW_OUTSIDE_CURRENT_NINE_PACKET_INDEX'
entry = next(r for r in index['review_packets'] if r['review_json'] == q['review_json'])
assert sha(entry['review_json']) == entry['review_sha256'] == q['review_json_sha256']
assert entry['seal_sha256'] == q['seal_sha256'] == sha(entry['seal'])
assert sorted(entry['offer_refs']) == sorted(q['source_offer_refs'])
assert set(q['source_offer_refs']).issubset(index['retained_source_offer_refs'])
(H/'source-index-handoff.before.json').write_bytes(queue.read_bytes())
q.update(status='COMPLETED_ALREADY_INCLUDED_IN_CURRENT_PUBLISHED_SOURCE_REVIEW_INDEX',
    queued_for_import=False, superseded_utc=now,
    current_index={'path':str(index_file),'sha256':index_binding['sha256']},
    current_register_sha256=p['register_sha256'],
    supersession_scope='Existing source review already indexed. Its photograph qualifications and original frozen scope remain unchanged; do not repeat its import.')
tmp = queue.with_name(queue.name+'.tmp-root')
dump(tmp,q);os.replace(tmp,queue)
assert read(queue) == q
def reference(oid):
    o=options[oid]
    return {k:o[k] for k in ['product_id','name','file_id','folder_id','image_url','folder_url']}
items = [
    {'number':1,'title':'Decowaves 1 old pending question',
     'status':'Closed: existing owner answer already published',
     'detail':'Same relief design in two separate finish options. No dimensions, price, SKU, stock or physical fields transferred.',
     'references':[reference(x) for x in ['BSI-612EF4DBB555','BSI-8CC6C8AABCB7']]},
    {'number':2,'title':'Four-source old queued handoff',
     'status':'Closed: all four sources already in the current 14-packet review index',
     'detail':'O005, O052, O068 and O073. This closes an outdated queue note; it adds no new exact platform matches.',
     'references':[reference(x) for x in entry['option_ids']],
     'review':entry['review']},
    {'number':3,'title':'Moon Crater Phase 1 native candidate',
     'status':'One design identity question presented; owner answer pending',
     'detail':'Eight retained Squarespace frames and four Dropbox comparisons rechecked. Exact photograph/finish/native variant remains unbound.',
     'references':[reference('BSI-EBD43DF0704F')],
     'source_image':read(H/'owner-question.json')['source_image_url'],
     'review':str(H/'index.html'),
     'question':read(H/'owner-question.json')['question']},
    {'number':4,'title':'Acanthus One Leaf Left — Pewter physical details',
     'status':'Existing optional physical question remains unanswered; no repeat prompt',
     'detail':'Retain accepted estimates. Measured dimensions/depth, bare-panel weight, maker material and fitted hardware need evidence.',
     'references':[reference('BSI-3635E3DC3434')],
     'working_details':{k:v['display'] for k,v in options['BSI-3635E3DC3434']['master_fields'].items()},
     'review':str(B/p['current_specification_verification']['review'])},
]
progress={'status':'CURRENT_INCREMENTAL_REVIEW_ONE_DESIGN_QUESTION_PENDING',
    'recorded_utc':now,'current_pointer_sha256':sha(pfile),
    'register_sha256':p['register_sha256'],'active_options':188,
    'items':items,'next_item':3,
    'other_active_session':{'thread_id':'01a13fe6-495b-7253-b923-31823b4cbca8',
        'scope':'Review app purpose toggles, modal save behaviour, prepared source sync and selected-file deletion UI; root does not edit this lane.'},
    'current_context_holds':22,'current_series_holds':1,
    'source_root':'BOLDSTONE MASTER only',
    'canonical_changes':0,'review_app_choices_changed':0,'native_or_platform_writes':0,
    'question_delivery':{'tool':'request_user_input_async','accepted':True,'answer_received':False,
        'question_file':str(H/'owner-question.json')}}
dump(H/'progress.json',progress)
previous=read(H/'verification.json')
assert all(sha(path)==expected for path,expected in previous['protected_files_unchanged'].items())
verification={'status':'PASS_TWO_ROOT_QUEUE_CORRECTIONS_AND_CURRENT_WALKTHROUGH',
    'recorded_utc':now,'outdated_pending_notes_closed':2,
    'current_source_index_packets':len(index['review_packets']),
    'current_source_index_offers':len(index['retained_source_offer_refs']),
    'preserved_canonical_register_sha256':p['register_sha256'],
    'preserved_pointer_sha256':sha(pfile),
    'protected_files_unchanged':True,'canonical_or_app_changes':0,'native_or_platform_writes':0,
    'physical_verifications_added':0,'new_exact_variant_matches':0,
    'progress_sha256':sha(H/'progress.json'),'queue_sha256':sha(queue)}
dump(H/'queue-verification.json',verification)
print(json.dumps(verification,ensure_ascii=False,indent=2))
