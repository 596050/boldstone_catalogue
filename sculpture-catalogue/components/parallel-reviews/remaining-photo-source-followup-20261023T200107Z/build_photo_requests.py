import datetime
import hashlib
import html
import json
from pathlib import Path
from html.parser import HTMLParser

J = Path(__file__).parent
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
targets = read(J / 'active-context-targets.json')
prior_path = J.parent / 'remaining-insitu-review-20261023T190856Z/remaining-insitu-review-outcomes.json'
prior = {x['option_id']: x for x in read(prior_path)}
specifics = {
    'BSI-9B2B466B38BE': 'Show the complete Two Leaves panel with its pale blue and white marbled finish and the surrounding display setting.',
    'BSI-B42C439049D7': 'Show the complete long Leaf Growth relief with the white and gold leaf finish and its surrounding setting. A different gold botanical panel does not identify this piece.',
    'BSI-46F6DB226213': 'Show the complete Phase 4 panel in its Verdigris and Rust finish in a display setting. A photograph of the matching full phase series may also help its separate series request.',
    'BSI-0696BC44A7BC': 'Show the complete wide-lip crater in its Drip Rust finish on its intended support or in its display setting, with the outer rim visible.',
    'BSI-75ACAD5A9841': 'Show the complete White Lava Corner Curve sculpture and the surrounding display setting, keeping every panel edge visible.',
    'BSI-3EC38D9CD913': 'Show the complete third Moonspiral design in White and its surrounding setting. Keep the design distinct from Moonspiral One and Two.',
    'BSI-E5A179105EA8': 'Show the complete Beige Panel Curves sculpture and enough surrounding space to establish its display setting.',
    'BSI-2418C8B43415': 'Show the complete textured Gold Leaf Panel Curves sculpture in its setting. Keep foliage and other objects clear of its outer edges.',
    'BSI-21DCD11AD8C6': 'Show the complete White Soundwave sculpture in its room, garden or display setting, with the full relief visible.',
    'BSI-718DFFB7EC5D': 'Show the complete first Bronze Spiralfish Wave and Tide panel in its setting. One photograph of both Bronze panels may cover both requests if both are fully visible.',
    'BSI-54F871DCF4CA': 'Show the complete second Bronze Spiralfish Wave and Tide panel in its setting. One photograph of both Bronze panels may cover both requests if both are fully visible.',
    'BSI-8EA49F5DDB1C': 'Show the complete White Quarter Moon sculpture and its surrounding display setting.',
    'BSI-207102CFD25C': 'Show the complete Blue, Brown and Rust textured panel in a display setting. The existing overhead fabric/worktable view does not establish that setting.',
    'BSI-449C4421ABD0': 'Show the complete Two Leaves panel in Pewter in its setting. The One Leaf Left Pewter panel is a different sculpture.',
    'BSI-1774B82C6518': 'Show the complete Egyptian Palm One Pewter panel in its setting. If photographed with Deco Palm Right, keep both complete and retain the established identities.',
}
assert len(targets) == 15 and set(specifics) == {x['option_id'] for x in targets}
requests = []
for t in targets:
    oid = t['option_id']
    assert prior[oid]['review_state'] == 'CURRENT_CONTEXT_SOURCE_STILL_REQUIRED'
    ref = t['individual']['reference']
    assert 'BOLDSTONE%20MASTER' in ref['image_url'] and 'BOLDSTONE%20MASTER' in ref['folder_url']
    requests.append({
        'option_id': oid, 'name': t['name'], 'requested_role': 'In situ / display',
        'status': 'CURRENT_SOURCE_REQUIRED_AFTER_BOUNDED_RECHECK',
        'photograph_to_supply': specifics[oid],
        'accepted_individual_reference': ref,
        'why_existing_sources_do_not_fill_role': prior[oid]['finding'],
        'next_action': 'Locate an existing suitable original in BOLDSTONE MASTER, or photograph the piece when available and save the original in its corresponding Master folder.',
        'source_scope': 'Fresh complete family metadata listings and reused prior visual findings; supplementary current Master searches. No universal visual absence claim.',
        'new_reference_selected': None, 'owner_image_approval_added': False,
        'primary_changed': False, 'physical_specification_verified': False,
    })
observations = {
    'id:cnqzTNngPVsAAAAAAAsehg': 'Gold astronaut figure in an Omega shop-window display. It is not one of the requested Boldstone reliefs.',
    'id:cnqzTNngPVsAAAAAAAsc8A': 'Another view of the gold astronaut shop-window display. It does not show the requested Boldstone reliefs.',
    'id:cnqzTNngPVsAAAAAAAsdSg': 'Another view of the gold astronaut shop-window display. It does not show the requested Boldstone reliefs.',
    'id:cnqzTNngPVsAAAAAAAtBjQ': 'Close photograph of blue flower buds. It is botanical imagery, not an Acanthus sculpture.',
    'id:cnqzTNngPVsAAAAAAAs_8g': 'Landscape gold botanical artwork in a room composition. The central single bud/leaf and side arcs differ from the accepted long two-leaf White and Gold Leaf Growth reference; no exact-option context match.',
    'id:cnqzTNngPVsAAAAAAAurhA': 'Monochrome printed card/detail composition of a spiral relief. It does not show either complete Bronze Spiralfish panel in a setting.',
}
sources = read(J / 'supplementary-original-receipts.json')['sources']
assert {x['file_id'] for x in sources} == set(observations)
visual = {'recorded_utc': now, 'status': 'SIX_CURRENT_WHOLE_ORIGINALS_REVIEWED_NO_TARGET_MATCH', 'sources': [{**x, 'finding': observations[x['file_id']], 'new_gap_closed': False} for x in sources], 'comparison_reference': 'Leaf Growth White and Gold Leaf current primary id:cnqzTNngPVsAAAAAAA6VkQ visually compared against Golden leaf bud 2; different composition.', 'new_physical_claims': 0, 'new_personal_owner_approvals': 0}
(J / 'supplementary-visual-review.json').write_text(json.dumps(visual, ensure_ascii=False, indent=2) + '\n')
packet = {'recorded_utc': now, 'status': 'FIFTEEN_CONTEXT_REQUESTS_RECHECKED_SOURCE_STILL_REQUIRED', 'request_count': len(requests), 'new_qualified_matches': 0, 'requests': requests, 'excluded_lanes': {'Pewter_context_and_all_series': 'A review session', 'bordered_Moonphase_context': 'A reviewed; main session imports', 'held_cases': 'Unchanged'}, 'evidence': [{'path': str(p), 'sha256': sha(p)} for p in [prior_path, J / 'metadata-delta-review.json', J / 'supplementary-targeted-searches.json', J / 'supplementary-visual-review.json']], 'boundaries': 'The 2,295 generic direct camera files in supplementary directories were inventoried, not all visually screened. Their nested folders were not exhaustively scanned. No unknown scene is promoted to an exact option.'}
(J / 'context-photograph-requests.json').write_text(json.dumps(packet, ensure_ascii=False, indent=2) + '\n')
esc = html.escape
cards = []
for r in requests:
    ref = r['accepted_individual_reference']
    cards.append(f'<article><h2>{esc(r["name"])}</h2><p>{esc(r["photograph_to_supply"])}</p><p><a href="{esc(ref["image_url"], quote=True)}">Accepted individual image</a> · <a href="{esc(ref["folder_url"], quote=True)}">Containing folder</a></p><details><summary>Why another reference is needed</summary><p>{esc(r["why_existing_sources_do_not_fill_role"])}</p></details></article>')
page = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Remaining display photograph requests</title><style>body{font:17px/1.55 system-ui;max-width:980px;margin:40px auto;padding:0 24px;background:#f6f4ef;color:#21302c}article{padding:20px;margin:18px 0;background:white;border:1px solid #d9dfd8;border-radius:8px}h1{font-size:30px}h2{font-size:21px}a{color:#17604b}summary{cursor:pointer}details{font-size:15px}</style><h1>15 display references still needed</h1><p>Locate an existing suitable original in BOLDSTONE MASTER, or photograph the piece when available. Show the whole sculpture, its exact finish and its surrounding display setting. One group photograph can cover several requests when each sculpture is complete and clearly identifiable.</p><p>These requests cover this review session. Pewter, bordered Moonphase and series requests are coordinated separately. Held cases are excluded. Existing primary images and accepted specifications remain in place.</p>' + ''.join(cards) + '</html>'
(J / 'context-photograph-requests.html').write_text(page)
class Check(HTMLParser):
    def __init__(self): super().__init__(); self.links = []; self.articles = 0
    def handle_starttag(self, tag, attrs):
        if tag == 'article': self.articles += 1
        if tag == 'a': self.links.append(dict(attrs)['href'])
c = Check(); c.feed(page)
assert c.articles == 15 and len(c.links) == 30 and all('dropbox.com/' in x and 'BOLDSTONE%20MASTER' in x for x in c.links)
(J / 'request-verification.json').write_text(json.dumps({'recorded_utc': now, 'status': 'PASS_FIFTEEN_SCOPED_REQUESTS_AND_THIRTY_MASTER_LINKS', 'option_ids': sorted(specifics), 'requests': 15, 'links': 30, 'new_image_roles': 0, 'new_native_or_platform_writes': 0, 'packet_sha256': sha(J / 'context-photograph-requests.json')}, indent=2) + '\n')
print(json.dumps({'status': packet['status'], 'requests': len(requests), 'new_matches': 0, 'packet': str(J / 'context-photograph-requests.json'), 'packet_sha256': sha(J / 'context-photograph-requests.json')}))
