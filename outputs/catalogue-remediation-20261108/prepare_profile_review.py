"""Prepare factual profile recommendations without changing LinkedIn."""
import json
import html
from pathlib import Path

OUT=Path(__file__).parent
review={
 'checked_date':'2026-11-08',
 'personal_profile_url':'https://uk.linkedin.com/in/sally-price-1193858a',
 'personal_profile_access':'Public fetch blocked. Signed-in personal-profile fields have not been audited. No profile edits applied.',
 'company_url':'https://www.linkedin.com/company/boldstone-sculpture/',
 'company_observation':'Public company About text describes sculpture for gardens and interiors, with a broad list of art and homeware specialties. The company page links Sally Price and the Boldstone website.',
 'headline_proposal':'Designer & Sculptor at Boldstone Sculpture | Handmade Wall Reliefs & Garden Art | Bespoke Commissions | Bath, UK',
 'about_proposal':"I’m Sally Price, designer and sculptor behind Boldstone Sculpture, based near Bath. I create handmade wall sculptures and relief panels inspired by natural forms, rippling water, shells and botanical shapes.\n\nThe collection includes individual pieces and coordinating designs for interiors and outdoor settings. Finishes, colours and designs can be customised. Completely new commissions can also be developed in collaboration with me.\n\nI welcome enquiries from private clients, interior designers, garden designers, architects and retailers. View the current collection at boldstonesculpture.com or contact info@boldstone.co.uk to discuss a project.",
 'recommended_featured_items':[
  {'label':'Shop wall sculptures','url':'https://boldstonesculpture.com/?utm_source=linkedin&utm_medium=social&utm_campaign=wall_sculptures_profile'},
  {'label':'Commissions and design process','action':'Feature a genuine completed-project case study, with photographs, scale, finish and the enquiry route.'},
  {'label':'Trade collection','action':'Feature the approved wholesale presentation only after pricing and publication review. Brandboom presentation 681160 is currently private and ordering is disabled.'}
 ],
 'company_specialties_proposal':['Wall sculpture','Relief panels','Garden wall art','Architectural relief','Bespoke sculpture','Custom commissions','Sculptural water features','Interior design collaborations','Garden design collaborations'],
 'channel_discoverability_actions':[
  'Keep the exact Boldstone name, website and public contact details consistent across the personal Experience entry, company page and sales profiles.',
  'Use one website page for verified public Where to buy links, rather than exposing seller dashboards or pending accounts.',
  'Link the personal Experience role to the existing Boldstone Sculpture company page.',
  'Feature Instagram, Facebook Shop and Pinterest only through their verified public profiles. Merchant Center and Commerce Manager are management tools, not customer purchase links.',
  'Use project posts showing the sculpture at scale and link to the exact product. Add alt text and short video of the relief in changing light.',
  'Use tracked website links to distinguish LinkedIn visitors and enquiries. Do not claim a channel is live until its public product route is verified.'
 ],
 'sources':['https://www.linkedin.com/company/boldstone-sculpture/','https://boldstonesculpture.com/about'],
 'changes_applied':False,
}
(OUT/'linkedin-profile-review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
esc=lambda text:html.escape(str(text))
actions=''.join('<li>'+esc(action)+'</li>' for action in review['channel_discoverability_actions'])
links=''.join('<li>'+esc(item['label'])+': '+('<a href="'+esc(item['url'])+'">'+esc(item['url'])+'</a>' if item.get('url') else esc(item['action']))+'</li>' for item in review['recommended_featured_items'])
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sally Price · LinkedIn profile review</title><style>body{max-width:900px;margin:45px auto;padding:0 24px;background:#f7f5ef;color:#25372f;font:17px/1.6 Arial,sans-serif}h1,h2{font-family:Georgia,serif;font-weight:400}h1{font-size:42px}h2{margin-top:35px}.draft{background:white;border:1px solid #d7dece;padding:24px;white-space:pre-wrap}.note{background:#e5e9db;padding:18px}a{color:#335b43}li{margin:12px 0}small{color:#566650}</style><h1>Sally Price<br>LinkedIn discoverability review</h1><p class="note">Prepared 8 November 2026. Draft recommendations only. The public company page was reviewed. The personal profile was blocked from public access and has not received a full signed-in audit. No LinkedIn changes were applied.</p><h2>Proposed headline</h2><div class="draft">'''+esc(review['headline_proposal'])+'''</div><h2>Proposed About section</h2><div class="draft">'''+esc(review['about_proposal'])+'''</div><h2>Featured items</h2><ul>'''+links+'''</ul><h2>Make the buying routes easier to find</h2><ul>'''+actions+'''</ul><h2>Company specialties</h2><p>'''+esc(', '.join(review['company_specialties_proposal']))+'''</p><p><small>Sources: <a href="https://www.linkedin.com/company/boldstone-sculpture/">Existing company page</a> · <a href="https://boldstonesculpture.com/about">Boldstone About</a> · <a href="https://uk.linkedin.com/in/sally-price-1193858a">Personal profile to inspect when signed in</a></small></p></html>'''
(OUT/'linkedin-profile-preview.html').write_text(page)
print(json.dumps(dict(status='DRAFT_RECOMMENDATIONS',personal_profile_live_audit=False,edits_applied=False)))
