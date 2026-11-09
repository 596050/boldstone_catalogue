"""Prepare a narrow header addition and a consent-aware shopping-funnel bridge."""
from pathlib import Path
from urllib.parse import urlparse
import csv
import json
import re
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
master=json.loads((OUT/'master-platform-values.json').read_text())
scope={p['id'] for p in json.loads((OUT.parent/'product-social-approval-20261108/pinterest-public-audit.json').read_text())['products']}
native={r['Variant ID [Non Editable]']:r for r in csv.DictReader((OUT/'squarespace-after.csv').open(encoding='utf-8-sig',newline=''))}
products={}
for pid,m in master.items():
    vid=m.get('pinterest_id')
    if vid not in scope:continue
    row=native[vid];sku=row['SKU'];assert sku==m['SKU']
    products[sku]={'id':vid,'path':urlparse(m['pinterest_link']).path}
assert len(products)==176
config={'tagId':'2612823030261','products':products}
code=(ROOT/'channel-update-playbook/automation/pinterest_tag.js').read_text().replace('__BOLDSTONE_PINTEREST_CONFIG__',json.dumps(config,separators=(',',':')))
(OUT/'pinterest-tag-config.json').write_text(json.dumps(config,indent=2)+'\n')
(OUT/'pinterest-tag-header.html').write_text('\n<!-- Boldstone Pinterest consent bridge, 2026-11-08 -->\n<script>\n'+code+'\n</script>\n')
old=(OUT/'homepage-inline-61.js').read_text();new=old.replace('Does not send Meta events,','Does not send Meta events,').replace('  function consent() {\n    try { return window.getSquarespaceCookies().performance === \'accepted\'; }\n    catch (_) { return false; }\n  }', '''  function performanceConsent() {
    try { return window.getSquarespaceCookies().performance === 'accepted'; }
    catch (_) { return false; }
  }
  function consent() {
    try { var c=window.getSquarespaceCookies(); return c.performance === 'accepted' || c.marketing === 'accepted'; }
    catch (_) { return false; }
  }''')
assert new!=old
new=new.replace("if (!consent() || typeof window.gtag !== 'function' || !items.length) return false;","if (!consent() || !items.length) return false;")
new=new.replace("    window.gtag('event', name, {","    var emitted = false;\n    if (performanceConsent() && typeof window.gtag === 'function') {\n      window.gtag('event', name, {")
needle="      items: items, transport_type: 'beacon'\n    });\n    return true;"
replacement="""      items: items, transport_type: 'beacon'
      });
      emitted = true;
    }
    if (window.BoldstonePinterest && window.BoldstonePinterest.commerce(name,items,currency)) emitted = true;
    return emitted;"""
assert new.count(needle)==1;new=new.replace(needle,replacement)
(OUT/'shopping-funnel-after.js').write_text(new)
print(json.dumps({'tag_id':config['tagId'],'products':len(products),'purchase_events_added':0,'customer_email_added':False}))
