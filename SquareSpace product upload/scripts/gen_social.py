#!/usr/bin/env python3
"""Generate platform-native social posts for every Boldstone product."""
import json, re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from content_paths import product_folders, slugify, write_text_atomically

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://boldstonesculpture.com"

RULES = {
 "instagram": dict(imgs=20, tags=(20, 28), limit=2200, ratio="4:5 (1080x1350)", how="Carousel"),
 "facebook":  dict(imgs=20, tags=(3, 5),   limit=1200, ratio="4:5 (1200x1500)", how="Album"),
 "threads":   dict(imgs=20, tags=(1, 3),   limit=500,  ratio="4:5 (1080x1350)", how="Carousel"),
 "x":         dict(imgs=2,  tags=(1, 3),   limit=280,  ratio="16:9 (1600x900)", how="Max 2 photos"),
 "linkedin":  dict(imgs=4,  tags=(3, 5),   limit=3000, ratio="1:1 (1200x1200)", how="Max 4 photos"),
}

CORE = ["boldstone", "boldstonesculpture", "britishsculpture", "handmadeart"]
BY_TYPE = {
 "wall sculpture": ["wallsculpture","wallart","reliefsculpture","sculpturalart","texturedart","contemporarysculpture","interiorsculpture","basrelief","modernsculpture","artcollector","originalart","neutralinteriors","organicmodern","wabisabi","interiordesign","interiorstyling","designerhome","luxuryinteriors","hotelart","gallerywall","artinstallation","sculpturalwall"],
 "Prints": ["artprint","fineartprint","limitededition","printmaking","botanicalart","naturalhistory","watercolour","inkdrawing","artonpaper","affordableart","artforthehome","botanicalillustration","printcollector","framedart","gallerywall","interiordesign","artlovers","originalartwork"],
 "Photography": ["fineartphotography","photographicprint","botanicalphotography","naturephotography","limitededitionprint","artphotography","printsforsale","wallartdecor","photoart","interiordesign","gallerywall","artcollector","stilllife","naturelovers"],
 "Greeting & Note Cards": ["greetingscards","artcards","stationery","snailmail","papergoods","artistmade","blankcards","notecards","illustratedcards","botanicalcards","naturalhistory","smallbusiness","giftideas","artgifts","letterwriting","independentartist","papergoodslove"],
 "Paintings": ["originalpainting","watercolour","fineart","artforsale","contemporarypainting","artcollector","oneofakind","artistsoninstagram","interiordesign","originalartwork"],
 "Artwork": ["originalartwork","fineart","artforsale","contemporaryart","artcollector","interiordesign","handmade","studioart"],
}
THEME = {
 "ammonite":["ammonite","fossilart","fossil","naturalform"],
 "spiral":["spiral","goldenratio","fibonacci","naturalform"],
 "moon":["moonart","lunar","moonphases","celestialart"],
 "wave":["waveart","oceanart","coastalinteriors","coastaldecor"],
 "shell":["shellart","seashell","coastalart"],
 "dune":["dunes","sandripples","naturalpattern"],
 "palm":["palmart","artdeco","tropicalinteriors"],
 "deco":["artdeco","decoinspired","geometricart"],
 "leaf":["botanical","leafart","natureinspired","foliage"],
 "onion":["botanicalart","stilllife","kitchenart"],
 "fish":["fishart","oceanart","marinelife"],
 "coral":["coralart","reef","oceanart"],
 "fern":["fernart","botanical","greeninteriors"],
 "rose":["roseart","floralart","flowerphotography"],
 "beetle":["entomology","insectart","naturalhistoryart"],
 "iris":["irisflower","floralart","botanicalphotography"],
 "sycamore":["seedart","botanical","naturalform"],
 "pineapple":["pineappleart","stilllife","kitchenart"],
 "mussel":["shellart","coastalart","marine"],
 "sound":["soundwave","abstractart","minimalart"],
 "crater":["moonart","lunar","texturedart"],
 "fold":["foldedform","abstractsculpture","minimalart"],
 "brancusi":["brancusi","modernism","sculpturehistory"],
 "gink":["ginkgo","botanical","autumnart"],
 "hydrangea":["hydrangea","floralart","botanical"],
 "agave":["agave","succulent","botanical"],
 "eucalyptus":["eucalyptus","botanical","foliage"],
 "maple":["japanesemaple","acer","botanical"],
}

def hashtags(p, lo, hi):
    t = list(CORE) + list(BY_TYPE.get(p["type"], BY_TYPE["Artwork"]))
    title = p["title"].lower()
    for k, v in THEME.items():
        if k in title:
            t += v
    for tag in p["tags"]:
        s = re.sub(r"[^a-z0-9]", "", tag.lower())
        if 3 <= len(s) <= 24:
            t.append(s)
    seen, out = set(), []
    for x in t:
        if x not in seen:
            seen.add(x); out.append(x)
    return ["#" + x for x in out[:hi]]

def dims(p):
    for pat in [r"(\d+\s*(?:\.\d+)?\s*cm\s*(?:x|by)\s*\d+\s*(?:\.\d+)?\s*cm(?:\s*(?:x|by)\s*\d+\s*(?:\.\d+)?\s*cm)?)",
                r"(\d+\s*(?:x|by)\s*\d+\s*(?:inches|inch|cm|mm))",
                r"(\d+\s*(?:\.\d+)?\s*cm\s*(?:high|wide|diameter|square))"]:
        m = re.search(pat, p["desc"], re.I)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    for v in p["variants"]:
        if v["option"] and re.search(r"\d", v["option"]):
            return v["option"]
    return ""

def edition(p):
    m = re.search(r"(edition of \d+(?: of \d+)?|limited edition|one of a kind)", p["desc"], re.I)
    return m.group(1).strip() if m else ""

def sentence(p, n=1, cap=260):
    """Shopify descriptions are unpunctuated run-ons, so clip to `cap` on a
    word boundary and close cleanly rather than dumping the whole blob."""
    d = re.sub(r"\s+", " ", p["desc"]).strip()
    if not d:
        return ""
    parts = [x for x in re.split(r"(?<=[.!?])\s+", d) if x.strip()]
    out = " ".join(parts[:n]).strip() if parts else d
    if len(out) < 45 and len(parts) > n:
        out = " ".join(parts[: n + 1]).strip()
    # strip trailing sales boilerplate
    out = re.split(r"\s+(?:Available in different sizes|Contact us for further)", out)[0].strip()
    if len(out) > cap:
        out = out[:cap].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"
    elif not out.endswith((".", "!", "?", "…")):
        out += "."
    return out

HOOK = {
 "wall sculpture": ["Carved shadow, held still.", "A form borrowed from deep time.",
                    "Light does half the work here.", "Relief is a slow medium. It rewards a slow look.",
                    "Where the surface breaks, the shadow gathers."],
 "Prints": ["Drawn from life, printed with care.", "Natural history, closely observed.",
            "Paper, pigment, patience.", "A study in looking properly."],
 "Photography": ["Found, not arranged.", "The photograph waits for the light.",
                 "Close enough to see the structure."],
 "Greeting & Note Cards": ["A small thing, well made.", "Worth the stamp.",
                           "Post something someone keeps."],
 "Paintings": ["One of one.", "Brush, water, time."],
 "Artwork": ["An original, from the studio."],
}

def hook(p):
    hs = HOOK.get(p["type"], HOOK["Artwork"])
    return hs[sum(map(ord, p["handle"])) % len(hs)]

def price(p):
    try:
        amount = Decimal(str(p['price']))
        if not amount.is_finite():
            return ""
        value = f"{amount:,.2f}"
        return "£" + (value[:-3] if value.endswith('.00') else value)
    except (InvalidOperation, KeyError, ValueError, TypeError):
        return ""

def link(p):
    return f"{SITE}/buy/p/{slugify(p['title'])}"

def spec_line(p):
    bits = [b for b in [dims(p), edition(p), price(p)] if b]
    return " · ".join(bits)

def clip(s, n):
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"

# ---------------- per-platform copy ----------------
def build(p, plat):
    r = RULES[plat]
    ht = hashtags(p, *r["tags"])
    t, sp, u = p["title"], spec_line(p), link(p)
    s = sentence(p, 2, cap={"instagram":300,"facebook":300,"threads":200,"x":120,"linkedin":420}[plat])

    if plat == "instagram":
        body = f"{hook(p)}\n\n{t}\n{s}"
        if sp: body += f"\n\n{sp}"
        body += f"\n\nShop via the link in bio → {u}\n\n" + " ".join(ht)

    elif plat == "facebook":
        body = f"{t} — {hook(p)}\n\n{s}"
        if sp: body += f"\n\n{sp}"
        body += f"\n\nAvailable now: {u}\n\n" + " ".join(ht)

    elif plat == "threads":
        core = f"{t}. {s}"
        if sp: core += f"\n{sp}"
        tags = " ".join(ht)
        body = clip(core, r["limit"] - len(u) - len(tags) - 2) + f"\n{u}\n{tags}"

    elif plat == "x":
        # X rewards brevity. A truncated run-on description reads badly, so lead
        # with the hook and let the specs do the selling. URLs count as 23 chars.
        tags = " ".join(ht)
        spec = " · ".join([b for b in [dims(p), price(p)] if b])
        line2 = f"{t}" + (f" · {spec}" if spec else "")
        body = f"{hook(p)}\n\n{line2}\n{u}\n{tags}"
        eff = len(body) - (len(u) - 23)
        if eff > r["limit"]:                       # fall back: drop the hook
            body = f"{clip(line2, r['limit'] - 23 - len(tags) - 2)}\n{u}\n{tags}"

    else:  # linkedin
        s3 = sentence(p, 3, cap=420)
        body = (f"{t}\n\n{hook(p)}\n\n{s3}\n\n"
                f"Every Boldstone piece is made by hand in the studio, so no two are identical.")
        if sp: body += f"\n\nSpecification: {sp}"
        body += f"\n\nView the piece: {u}\n\n" + " ".join(ht)

    return body.strip(), ht

def write(products=None):
    if products is None:
        products = json.loads((ROOT / "_data" / "products_master.json").read_text())
    counts = {k: 0 for k in RULES}
    for p, slug in product_folders(products, lambda p: slugify(p["title"])):
        for plat, r in RULES.items():
            body, ht = build(p, plat)
            eff = len(body) - (len(link(p)) - 23 if plat == "x" else 0)
            if eff > r["limit"]:
                raise ValueError(f"{slug}/{plat} over limit: {eff}; caption was not written.")
            n_img = min(p["n_img"], r["imgs"])
            imgs = "\n".join(f"  {i:02d}. {i:02d}.jpg" for i in range(1, n_img + 1)) or "  (none)"
            md = (
                f"# {p['title']}\n"
                f"**Platform:** {plat.title()}  \n"
                f"**Photos:** {n_img} ({r['how']}, {r['ratio']})  \n"
                f"**Hashtags:** {len(ht)}  \n"
                f"**Characters:** {len(body) - (len(link(p)) - 23 if plat == 'x' else 0)} / {r['limit']}  \n"
                f"**Product:** {link(p)}\n\n"
                f"---\n\n## Caption\n\n```\n{body}\n```\n\n## Images to attach\n\n{imgs}\n"
            )
            out = ROOT / "social" / plat / slug / "caption.md"
            write_text_atomically(out, md)
            counts[plat] += 1
    return counts

if __name__ == "__main__":
    c = write()
    print("WRITTEN:", json.dumps(c, indent=1))
