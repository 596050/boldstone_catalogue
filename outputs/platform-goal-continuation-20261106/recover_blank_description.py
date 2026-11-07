"""Permit a same-ID field retry only after a fresh server form proves blank."""
import json
import hashlib
import re
import sys
import time
from pathlib import Path

OUT = Path(__file__).parent

def validate_blank_proof(proof, intent):
    native_id = str(intent['native_artwork_id'])
    visible = proof.split('Selected text:')[0]
    address = next(line for line in visible.splitlines() if 'Address and search bar' in line)
    actual = re.search(r'Value: (.*?)(?:, Placeholder:|$)', address).group(1)
    actual = re.sub(r'^https?://(?:www\.)?', '', actual)
    assert actual == f'saatchiart.com/en-gb/studio/art/{native_id}/description', 'Wrong active native artwork route'
    assert intent['title'] in visible and 'text DRAFT' in visible, 'Bound title/draft is not active'
    assert re.search(r'^\s*\d+ text field \(settable\) Search or select a category$', visible, re.M), 'Category is already populated'
    assert re.search(r'^\s*\d+ text entry area \(settable\) Write Here\.\.\.$', visible, re.M), 'Description is already populated'


def main():
    path = Path(sys.argv[1]).resolve()
    intent = json.loads(path.read_text())
    assert intent['status'] in {'DESCRIPTION_SAVE_SUBMITTED_EXISTING_ID', 'REVIEW_REQUIRED_DESCRIPTION_NOT_SAVED'}
    strategy = sys.argv[3] if len(sys.argv) > 3 else 'same-id-after-verified-blank-reload'
    if intent['status'] == 'REVIEW_REQUIRED_DESCRIPTION_NOT_SAVED':
        assert strategy == 'native-keyboard-paste-and-blur', 'A stopped retry requires the specific new input strategy'
    native_id = intent['native_artwork_id']
    proof_path = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else OUT / f'evidence/saatchi-{native_id}-description-after-normal-reload.txt'
    proof = proof_path.read_text()
    assert 0 <= time.time() - proof_path.stat().st_mtime < 300, 'Capture a fresh server-backed form before retrying'
    validate_blank_proof(proof, intent)
    if intent.get('description_recovery'):
        intent.setdefault('description_recovery_history', []).append(intent['description_recovery'])
    intent['description_recovery'] = dict(reason='Fresh server-backed edit form shows blank description fields. Retry only the exact existing artwork with the recorded input strategy.', evidence=str(proof_path.relative_to(OUT)), evidence_sha256=hashlib.sha256(proof.encode()).hexdigest(), previous_status=intent['status'], strategy=strategy)
    intent['status'] = 'SAVED_PRIMARY_DRAFT_NATIVE_ID_VERIFIED'
    path.write_text(json.dumps(intent, indent=2) + '\n')
    print(json.dumps(dict(status='PASS_SAME_ID_DESCRIPTION_RECOVERY_PREPARED', native_id=native_id, strategy=strategy)))


if __name__ == '__main__':
    main()
