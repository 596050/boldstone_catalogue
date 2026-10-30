#!/usr/bin/env python3
"""Turn the 135 markdown articles into a WordPress WXR file that Squarespace can import."""
import re, sys, html
from pathlib import Path
from datetime import datetime, timedelta, timezone
import markdown

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://boldstonesculpture.com"
OUT  = ROOT / "_import"
OUT.mkdir(exist_ok=True)

# Which slugs to include (all, or a named subset for a test run)
only = sys.argv[1:] if len(sys.argv) > 1 else None

def parse(p):
    t = p.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", t, re.S)
    if not m:
        return None
    fm_raw, body = m.group(1), m.group(2).strip()
    fm = {}
    for line in fm_raw.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip().strip('"').strip()
        if k.strip() == "tags":
            v = [x.strip().strip('"') for x in v.strip("[]").split(",") if x.strip()]
        fm[k.strip()] = v
    fm["body"] = body
    return fm

arts = sorted((ROOT / "blog").glob("*/article.md"))
posts = []
for p in arts:
    slug = p.parent.name
    if only and slug not in only:
        continue
    fm = parse(p)
    if not fm:
        print("!! bad front matter:", slug); continue
    fm["slug"] = slug
    posts.append(fm)

# Stagger publication dates backwards, 2 days apart, so the blog reads as an
# archive rather than 135 posts dumped on one day (which reads as spam to search).
start = datetime.now(timezone.utc) - timedelta(days=1)
for i, fm in enumerate(posts):
    fm["date"] = start - timedelta(days=2 * i)

md = markdown.Markdown(extensions=["extra"])

def cdata(s):
    return "<![CDATA[" + (s or "").replace("]]>", "]]]]><![CDATA[>") + "]]>"

items = []
for i, fm in enumerate(posts, 1):
    body = fm["body"]
    # Squarespace renders the post title (the product name) itself, so demote the
    # crafted headline to an H2 lead-in rather than discarding it.
    body = re.sub(r"^#\s+(.*?)\n", r"## \1\n", body, count=1).strip()
    md.reset()
    body_html = md.convert(body)
    d = fm["date"]
    def nick(v):
        return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", v.lower())).strip("-") or "art"
    cats = "".join(
        f'<category domain="post_tag" nicename="{html.escape(nick(t), quote=True)}">{cdata(t)}</category>'
        for t in fm.get("tags", [])
    )
    _ty = fm.get("type") or "Art"
    cats += f'<category domain="category" nicename="{html.escape(nick(_ty), quote=True)}">{cdata(_ty)}</category>'
    items.append(f"""<item>
<title>{cdata(fm.get('title',fm['slug']))}</title>
<link>{SITE}/blog/{fm['slug']}</link>
<pubDate>{d.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>
<dc:creator>{cdata('Boldstone')}</dc:creator>
<guid isPermaLink="false">{SITE}/?p={1000+i}</guid>
<description></description>
<content:encoded>{cdata(body_html)}</content:encoded>
<excerpt:encoded>{cdata(fm.get('meta_description',''))}</excerpt:encoded>
<wp:post_id>{1000+i}</wp:post_id>
<wp:post_date>{d.strftime('%Y-%m-%d %H:%M:%S')}</wp:post_date>
<wp:post_date_gmt>{d.strftime('%Y-%m-%d %H:%M:%S')}</wp:post_date_gmt>
<wp:comment_status>closed</wp:comment_status>
<wp:ping_status>closed</wp:ping_status>
<wp:post_name>{fm['slug']}</wp:post_name>
<wp:status>publish</wp:status>
<wp:post_parent>0</wp:post_parent>
<wp:menu_order>0</wp:menu_order>
<wp:post_type>post</wp:post_type>
<wp:is_sticky>0</wp:is_sticky>
{cats}
</item>""")

xml = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0"
 xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/"
 xmlns:content="http://purl.org/rss/1.0/modules/content/"
 xmlns:wfw="http://wellformedweb.org/CommentAPI/"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:wp="http://wordpress.org/export/1.2/">
<channel>
<title>Journal</title>
<link>{SITE}</link>
<description>Journal</description>
<pubDate>{datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>
<language>en-GB</language>
<wp:wxr_version>1.2</wp:wxr_version>
<wp:base_site_url>{SITE}</wp:base_site_url>
<wp:base_blog_url>{SITE}</wp:base_blog_url>
<wp:author><wp:author_id>1</wp:author_id><wp:author_login>{cdata('boldstone')}</wp:author_login><wp:author_email>{cdata('studio@boldstonesculpture.com')}</wp:author_email><wp:author_display_name>{cdata('Boldstone')}</wp:author_display_name></wp:author>
{chr(10).join(items)}
</channel>
</rss>
"""

name = "boldstone_blog_TEST.xml" if only else "boldstone_blog_ALL.xml"
dest = OUT / name
dest.write_text(xml, encoding="utf-8")

# validate it parses as XML
import xml.etree.ElementTree as ET
ET.parse(dest)
print(f"WROTE {dest.name}: {len(posts)} posts, {dest.stat().st_size/1024:.0f} KB — XML valid")
print("date range:", posts[-1]['date'].date(), "→", posts[0]['date'].date())
