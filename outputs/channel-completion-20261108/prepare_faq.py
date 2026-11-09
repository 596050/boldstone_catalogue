"""Replace nine complete answers in the original public FAQ HTML."""
import html
import json
from pathlib import Path
import re
OUT=Path(__file__).parent
block=(OUT/'faq-block-before.html').read_text()
headings=re.findall(r'<h4\b.*?</h4>',block,re.S|re.I)
patches=json.loads((OUT/'faq-answer-changes.json').read_text())
for patch in patches:
    matches=[]
    def change(m):
        plain=html.unescape(re.sub(r'<[^>]+>','',m[2]))
        pattern=patch['old_pattern']
        if pattern.startswith('^Email info@'):
            pattern=r'^Email .* with your order details'
        if re.search(pattern,plain):
            matches.append(plain)
            return m[1]+html.escape(patch['value'])+m[3]
        return m[0]
    block=re.sub(r'(<p\b[^>]*>)(.*?)(</p>)',change,block,flags=re.S|re.I)
    assert len(matches)==1,(patch['old_pattern'],len(matches))
assert headings==re.findall(r'<h4\b.*?</h4>',block,re.S|re.I)
assert len(headings)==15
def decode(encoded):
    raw=bytes.fromhex(encoded)
    return bytes(v^raw[0] for v in raw[1:]).decode()
block=re.sub(r'<span\b[^>]*data-cfemail="([a-f0-9]+)"[^>]*>.*?</span>',lambda m:html.escape(decode(m[1])),block,flags=re.I|re.S)
block=re.sub(r'<a\b[^>]*data-cfemail="([a-f0-9]+)"[^>]*>.*?</a>',lambda m:'<a href="mailto:'+html.escape(decode(m[1]),quote=True)+'">'+html.escape(decode(m[1]))+'</a>',block,flags=re.I|re.S)
block=re.sub(r'<a\b[^>]*href="/cdn-cgi/l/email-protection#([a-f0-9]+)"[^>]*>.*?</a>',lambda m:'<a href="mailto:'+html.escape(decode(m[1]),quote=True)+'">'+html.escape(decode(m[1]))+'</a>',block,flags=re.I|re.S)
assert '[email' not in html.unescape(block)
(OUT/'faq-block-after.html').write_text(block)
print(json.dumps({'answers_changed':len(patches),'questions_preserved':len(headings)}))
