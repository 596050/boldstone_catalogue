import datetime
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
url = 'https://boldstonesculpture.com/buy/p/moonshell-lava-1-white'
request = urllib.request.Request(url, headers={
    'User-Agent': 'BoldstoneCatalogueVerification/1.0', 'Cache-Control': 'no-cache'
})
page = urllib.request.urlopen(request, timeout=35).read().decode()
footer = (ROOT / 'footer-after-tracking.html').read_text()
header = (ROOT / 'header-before-tracking.html').read_text()
result = {
    'at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'url': url,
    'footer_exact_present': footer in page, 'header_exact_preserved': header in page,
    'funnel_script_count': page.count('id="boldstone-ga4-shopping-funnel"'),
    'script_sha256': hashlib.sha256(footer.encode()).hexdigest(),
}
(ROOT / 'tracking-public-readback.json').write_text(json.dumps(result, indent=2))
assert result['footer_exact_present'] and result['header_exact_preserved']
assert result['funnel_script_count'] == 1
print(json.dumps(result))
