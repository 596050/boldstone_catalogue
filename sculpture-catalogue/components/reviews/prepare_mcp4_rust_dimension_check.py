"""Stage the next scoped specification question without recording an answer."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'components/reviews/concave-to-mcp4-consolidation-2026-10-19/verdigris-rust-review'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(path, value):
    temp = path.with_name(path.name + '.tmp'); temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n'); temp.replace(path)
paths = {'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
docs = {k: read(v) for k, v in paths.items()}; before = copy.deepcopy(docs)
p, cp, c = (docs[k] for k in ['progress', 'walkthrough', 'component'])
qid = 'MCP4-VERDIGRIS-RUST-DIMENSIONS-01'
if cp['current_question_id'] == qid:
    assert not cp['current_answer_recorded']; print(json.dumps({'status': 'ALREADY_PREPARED_NO_WRITE'})); raise SystemExit
assert docs['root']['current_component_review'] == c and cp['current_answer_recorded']
node = p['reviews']['BC-MCP-4']['size_finish_variants']['MCP4-VERDIGRIS-RUST']
assert node['identity_confirmed'] and not node['proposals_approved']
user = ROOT / 'components/reviews/user_classifications.json'; guard = sha(user); now = datetime.now(timezone.utc).isoformat()
card = {'schema': 'boldstone.scoped-dimension-review.v1', 'prepared_utc': now, 'question_id': qid, 'component_id': 'BC-MCP-4', 'size_finish_variant_id': 'MCP4-VERDIGRIS-RUST', 'canonical_name': node['canonical_name'], 'identity_already_kept': True, 'identity_approval': node['identity_approval'], 'owner_question': 'For this panel, are the proposed dimensions of 25 × 25 cm and approximately 6 cm depth correct?', 'proposal': node['specification_proposals'][0], 'all_six_proposals': node['specification_proposals'], 'current_dropbox_reference': node['current_dropbox_reference'], 'owner_answer_recorded': False, 'scope': 'Dimension check only. The name Keep did not approve dimensions. Other five specification groups remain pending.'}
path = HERE / 'dimension-check.json'; rel = str(path.relative_to(ROOT))
cp.update({'current_question_id': qid, 'current_review_record': rel, 'current_answer_recorded': False, 'current_dimension_answer_recorded': False, 'review_decision_mode': 'DIMENSIONS_AND_DEPTH_ONLY', 'question_scope': card['scope'], 'state': 'MCP4_FINISH_NAMES_COMPLETE;AWAITING_RUST_DIMENSION_CHECK', 'answer_state': card['scope'], 'proposed_name': node['canonical_name'], 'primary_image': node['current_dropbox_reference']['image_url'], 'containing_folder': node['current_dropbox_reference']['folder_url']})
c['interactive_review_state'].update({'current_question_id': qid, 'current_dimension_answer_recorded': False, 'review_decision_mode': 'DIMENSIONS_AND_DEPTH_ONLY', 'state': cp['state']})
p.setdefault('pending_specification_checks', {})[qid] = {'review_record': rel, 'identity_already_kept': True, 'owner_answer_recorded': False}
for doc in docs.values(): doc['updated_utc'] = now
docs['root']['current_component_review'] = copy.deepcopy(c)
assert p['reviews'] == before['progress']['reviews'] and p['source_design_reviews'] == before['progress']['source_design_reviews']
write(path, card)
for k, file in paths.items(): write(file, docs[k])
assert read(paths['root'])['current_component_review'] == read(paths['component']) and sha(user) == guard and not read(paths['walkthrough'])['current_answer_recorded']
write(HERE / 'dimension-preparation-receipt.json', {'status': 'PREPARED_AND_READ_BACK', 'question_id': qid, 'card_sha256': sha(path), 'owner_decisions': 0, 'specification_approvals': 0, 'user_ledger_unchanged': True, 'all_component_and_source_reviews_unchanged': True})
print(json.dumps({'status': 'PREPARED_AND_READ_BACK', 'question_id': qid, 'specification_approvals': 0}))
