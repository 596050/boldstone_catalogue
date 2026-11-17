#!/usr/bin/env python3
"""Convert a newly prepared Boldstone posts.json into a frozen outbox manifest.

Already published rows are refused. Building a manifest does not open Chrome or
enqueue anything. The output defaults to publish_authorized=false.
"""
import argparse
import json
import sys
from pathlib import Path

from common import Hold, atomic_json, digest, read_json
from settings import Settings


def build(source, output, batch_id, authorized=False):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise Hold('OUTPUT_EXISTS', 'Choose a new manifest path to preserve the prepared record')
    records = read_json(source)
    if not isinstance(records, list) or not records:
        raise Hold('SOURCE_SCHEMA', 'Expected a nonempty list of prepared catalogue posts')
    settings = Settings()
    by_platform = {v['platform']: k for k, v in settings.profiles.items()}
    result = []
    for p in records:
        if p.get('publications') or str(p.get('status', '')).startswith(('PUBLISHED', 'COMPLETE')):
            raise Hold('ALREADY_PUBLISHED_MANIFEST', p.get('title', 'Published row'))
        media = Path(p['media_path']).expanduser()
        if not media.is_absolute():
            media = source.parent / media
        media = media.resolve()
        if not media.is_file() or digest(media.read_bytes()) != p['sha256']:
            raise Hold('MEDIA_HASH_CHANGED', p['title'])
        targets = {}
        for platform, caption in p['captions'].items():
            if platform not in by_platform:
                raise Hold('UNKNOWN_PLATFORM', platform)
            target = {'caption': caption}
            wants_tag = platform in {'facebook', 'instagram'} and (
                settings.policy.get('require_meta_product_tags') or 'product tag' in caption.lower() or
                p.get('native_commerce_title') or p.get('native_commerce_price_text'))
            if wants_tag:
                if not p.get('native_commerce_title') or not p.get('native_commerce_price_text'):
                    raise Hold('NATIVE_TAG_DETAILS_REQUIRED', 'Provide native_commerce_title and native_commerce_price_text from the actual Commerce picker')
                target['product_tag'] = {'name': p['native_commerce_title'], 'price_text': p['native_commerce_price_text']}
            if platform != 'instagram' and p.get('tracked_urls', {}).get(platform):
                target['purchase_url'] = p['tracked_urls'][platform]
            targets[by_platform[platform]] = target
        result.append({'post_key': p['catalogue_id'], 'catalogue_id': p['catalogue_id'], 'sku': p.get('sku'),
                       'title': p['title'], 'media_path': str(media), 'sha256': p['sha256'], 'alt_text': p['alt_text'], 'targets': targets})
    manifest = {'schema_version': 1, 'batch_id': batch_id, 'publish_authorized': authorized, 'posts': result}
    atomic_json(output, manifest)
    return {'manifest': str(output), 'sculptures': len(result), 'deliveries': sum(len(p['targets']) for p in result),
            'publish_authorized': authorized, 'browser_actions': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--batch-id', required=True)
    parser.add_argument('--authorize', action='store_true', help='Use only when publication of this exact prepared batch is already authorized')
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.source, args.output, args.batch_id, args.authorize), indent=2))
    except Hold as error:
        print(json.dumps({'status': 'HELD', 'code': error.code, 'detail': str(error)}))
        sys.exit(2)

