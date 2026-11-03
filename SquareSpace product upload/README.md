# Boldstone — social posts, blog articles and platform images

Everything for one product lives together. Each post has its own folder containing the
caption/article **and the photos sized for that platform**.

```
blog/<slug>/            article.md   + 01.jpg … NN.jpg   (max 1600px, no crop)
social/instagram/<slug>/ caption.md  + 01.jpg … 20.jpg   (4:5  1080×1350, all photos)
social/facebook/<slug>/  caption.md  + 01.jpg … 20.jpg   (4:5  1200×1500, all photos)
social/threads/<slug>/   caption.md  + 01.jpg … 20.jpg   (4:5  1080×1350, all photos)
social/x/<slug>/         caption.md  + 01.jpg, 02.jpg    (16:9 1600×900,  MAX 2)
social/linkedin/<slug>/  caption.md  + 01.jpg … 04.jpg   (1:1  1200×1200, MAX 4)
```

## Step 1 — download the images (one command, ~10 minutes)

I can generate text but I'm not able to download image binaries, so this last step runs on your
machine. It reads your live site, pulls each product's photos, and drops correctly-sized JPEGs
into every post folder above.

```bash
cd "SquareSpace product upload/scripts"
./run.sh
```

That's it. `run.sh` builds a self-contained virtualenv in `scripts/.venv` and runs the pipeline
inside it, so it never touches your system Python.

**If you tried `pip install` and got `externally-managed-environment`** — that's Homebrew's Python
refusing to install packages system-wide (PEP 668). It's protecting you, and `run.sh` is the fix.
Don't reach for `--break-system-packages`; you don't need it.

Safe to re-run — it skips anything already downloaded. Pass `./run.sh --refresh` to re-scan the
site if you've added products since.

## Step 2 — post

Open any folder, copy the caption out of `caption.md`, attach the numbered JPEGs in order.
Each file states its photo count, hashtag count and character count against the platform limit.

## What's here

| | Count |
|---|---|
| Products covered | 136 |
| Blog articles (500–1000 words each) | 135 |
| Social posts (5 platforms × 136) | 680 |
| Photos that will be produced | ~2,700 |

## Choices I made, so you can overrule them

- **Photos are letterboxed on white, never cropped.** A centre-crop to 4:5 would guillotine a
  120cm-wide ammonite. White padding keeps the whole piece visible and suits the brand. If you'd
  rather crop, set `"pad": False` in `TARGETS` in `fetch_and_resize.py`.
- **Hashtag counts differ by platform, deliberately.** Instagram gets 20–28 (it rewards them);
  Facebook and LinkedIn get 3–5; X and Threads get 1–3. Thirty hashtags on LinkedIn reads as spam.
- **X leads with a hook, not the product description.** The Shopify descriptions are long,
  unpunctuated run-ons; truncated into 280 characters they read badly. X gets the hook, the piece,
  the dimensions and the price.
- **Frozen Fish has no article.** Its record has no description, no dimensions and a £0.00 price,
  so there was nothing factual to write from and I wasn't willing to invent it. Give me the
  details and I'll write it.

## Known gap

Card and print articles are written from the product descriptions, which are thin on provenance.
They lean on natural history and design history for substance. If you have studio notes on any
piece — why you drew it, where you found it — those would make the articles considerably better.
