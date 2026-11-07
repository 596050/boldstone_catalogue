"""Read the complete visible native portfolio before creating missing artwork."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).parent
ROOT = OUT.parents[2]
records = []
for page, count in [(1, 100), (2, 26)]:
    path = OUT / f'saatchi-current-portfolio-page{page}.txt'
    state = path.read_text()
    selected = re.search(r'Selected text: ```\n([\s\S]*?)\n```', state).group(1)
    matches = list(re.finditer(r'\ufffc+([^\ufffc]+?)Sculpture([\d.]+ W x [\d.]+ H x [\d.]+ D centimeters)(Published|Draft)([A-Za-z]{3} \d{1,2}, \d{4})\$([\d,]+)\ufffc+For Sale', selected))
    assert len(matches) == count, (page, len(matches), count)
    for match in matches:
        title, dimensions, status, date, price = match.groups()
        records.append(dict(title=title.strip(), dimensions=dimensions, status=status,
                            date=date, price_usd=float(price.replace(',', '')),
                            source=str(path.relative_to(ROOT)), page=page,
                            source_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
normal = lambda s: re.sub(r'[^a-z0-9]+', '', s.casefold())
assert len(records) == len({normal(r['title']) for r in records}) == 126
assert all(r['status'] == 'Published' for r in records)
queue = json.loads((OUT.parent / 'resume-0600/remaining-native-ready-queue.json').read_text())
assert len(queue) == 13
assert not any(normal(x['packet']['title']) in {normal(r['title']) for r in records} for x in queue)
result = dict(status='PASS_FRESH_WHOLE_PORTFOLIO_126_PUBLISHED', checked_utc=datetime.now(timezone.utc).isoformat(),
              total_native_artworks=126, published=126, duplicates_by_normalized_title=0,
              qualified_queue_not_present=13,
              scope='Native full-page selected text:100 and26 records; exact missing queue titles absent before creation.',
              records=records)
(OUT / 'saatchi-fresh-whole-portfolio.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k:v for k,v in result.items() if k != 'records'}))
