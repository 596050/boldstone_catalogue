"""Prepare the current Pinterest bridge and canonical shopping funnel; no live writes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
PRODUCT_COUNT = 176


def validate(config):
    if not isinstance(config, dict) or not re.fullmatch(r'[0-9]{13}', str(config.get('tagId', ''))):
        raise ValueError('A 13-digit public Pinterest tag ID is required.')
    products = config.get('products')
    if not isinstance(products, dict) or len(products) != PRODUCT_COUNT:
        raise ValueError(f'Expected exactly {PRODUCT_COUNT} reviewed product mappings.')
    ids = set()
    for sku, product in products.items():
        if not isinstance(sku, str) or not sku.strip() or not isinstance(product, dict):
            raise ValueError('Product mappings require nonempty SKU names and objects.')
        identity = product.get('id')
        if not isinstance(identity, str) or not identity.strip() or identity in ids:
            raise ValueError('Every product needs a distinct nonempty product ID.')
        ids.add(identity)
        path = product.get('path')
        if not isinstance(path, str):
            raise ValueError('Product paths must be local /buy/p/ URLs.')
        parsed = urlsplit(path)
        decoded = unquote(path)
        if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment
                or not path.startswith('/buy/p/') or not path[7:].strip('/')
                or '\\' in decoded or any(c.isspace() for c in decoded)
                or any(part in ('.', '..') for part in decoded.split('/'))):
            raise ValueError('Product paths must be exact local /buy/p/ paths without queries or traversal.')
    return config


def prepare(config, output, sources=HERE):
    validate(config)
    # JSON is embedded in an HTML script, where a literal </script> terminates
    # even a JavaScript string. Escape HTML delimiters before interpolation.
    payload = json.dumps(config, separators=(',', ':'), ensure_ascii=True)
    for character, escaped in (('<', '\\u003c'), ('>', '\\u003e'), ('&', '\\u0026')):
        payload = payload.replace(character, escaped)
    template = (sources / 'pinterest_tag.js').read_text()
    if template.count('__BOLDSTONE_PINTEREST_CONFIG__') != 1:
        raise ValueError('Pinterest template must contain exactly one configuration marker.')
    tag = template.replace('__BOLDSTONE_PINTEREST_CONFIG__', 'JSON.parse(' + json.dumps(payload) + ')')
    funnel = (sources / 'shopping_funnel.js').read_text()
    if 'lastViews.ga4' not in funnel or 'lastViews.pinterest' not in funnel:
        raise ValueError('The shopping funnel must retain separate platform view state.')
    files = {'pinterest-tag-header.html': '<script>\n' + tag + '\n</script>\n',
             'shopping-funnel-footer.html': '<script id="boldstone-ga4-shopping-funnel">\n' + funnel.rstrip() + '\n</script>'}
    receipt = {'status': 'PREPARED_ONLY', 'products': PRODUCT_COUNT, 'live_writes': 0,
               'sha256': {name: hashlib.sha256(body.encode()).hexdigest() for name, body in files.items()}}
    files['tracking-build.json'] = json.dumps(receipt, indent=2) + '\n'
    output = Path(output)
    for name in files:
        path = output / name
        if path.exists() or path.is_symlink():
            raise FileExistsError(f'Reconcile existing prepared artifact before overwriting: {path}')
    output.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        for name, body in files.items():
            path = output / name
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created.append(path)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path, help='Public tagId and exact SKU-to-product-ID/path mapping JSON')
    parser.add_argument('output', type=Path)
    args = parser.parse_args(argv)
    try:
        prepare(json.loads(args.config.read_text()), args.output)
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, str(error) + '\n')
    print(f'Prepared {PRODUCT_COUNT}-product tracking configuration; no website settings changed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
