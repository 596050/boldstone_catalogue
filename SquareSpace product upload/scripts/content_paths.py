"""Keep generated product folders distinct and inside their platform folder."""
import re
import tempfile
from pathlib import Path


def slugify(title):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", title.lower())).strip("-")


def product_folders(products, slug_for):
    folders, seen = [], set()
    for product in products:
        slug = slug_for(product)
        if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise ValueError(f"Invalid product folder slug: {slug!r}")
        if slug in seen:
            raise ValueError(f"Duplicate product folder slug: {slug!r}; no files were written.")
        seen.add(slug)
        folders.append((product, slug))
    return folders


def write_text_atomically(destination, text):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.' + destination.name, suffix='.tmp', delete=False) as handle:
        temporary = Path(handle.name)
    try:
        temporary.write_text(text, encoding='utf-8')
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
