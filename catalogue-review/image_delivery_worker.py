#!/usr/bin/env python3
"""Read a known Dropbox image. Originals leave only through stdout, not a file."""
from contextlib import closing, contextmanager
from io import BytesIO
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys

from fetch_original import OriginalError, check_metadata
from image_formats import IMAGE_HEADER_BYTES, image_type_from_header


@contextmanager
def connection(project):
    sys.path.insert(0, str(Path(project) / 'image-processing'))
    import authorize
    from dropbox import Dropbox
    from dropbox.common import PathRoot
    raw = authorize.keychain_backend().get_password(authorize.SERVICE, authorize.CREDENTIAL_ACCOUNT)
    grant = json.loads(raw) if raw else {}
    if grant.get('app_key') != authorize.APP_KEY or not grant.get('refresh_token'):
        raise OriginalError('Existing Dropbox authorization is unavailable.')
    with Dropbox(app_key=authorize.APP_KEY, oauth2_refresh_token=grant['refresh_token'], timeout=25,
                 max_retries_on_error=0, max_retries_on_rate_limit=0) as client:
        rooted = client.with_path_root(PathRoot.namespace_id(authorize.NAMESPACE_ID))
        authorize.verify_identity(client.users_get_current_account(), rooted.files_get_metadata(authorize.ROOT_ID), grant.get('account_id'))
        yield rooted, '/BOLDSTONE MASTER'


def thumbnail(data):
    from PIL import Image, ImageOps
    with Image.open(data) as source:
        source.draft('RGB', (1024, 768))
        image = ImageOps.exif_transpose(source)
        image.thumbnail((1024, 768))
        if image.mode in ('RGBA', 'LA') or 'transparency' in image.info:
            canvas = Image.new('RGB', image.size, 'white')
            canvas.paste(image.convert('RGBA'), mask=image.convert('RGBA').getchannel('A'))
            image = canvas
        else:
            image = image.convert('RGB')
        output = BytesIO()
        image.save(output, format='JPEG', quality=82, optimize=True)
        return output.getvalue()


def mime_type(first):
    mime, _ = image_type_from_header(first)
    if mime in ('image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp', 'image/avif'):
        return mime
    raise OriginalError('Use the thumbnail or source link for this image format.')


def send_header(output, mime, length):
    output.write((json.dumps({'mime': mime, 'bytes': length}) + '\n').encode())
    output.flush()


def stream_original(client, spec, root, output):
    metadata, response = client.files_download(spec['id'])
    with closing(response):
        check_metadata(metadata, spec['id'], spec['hash'], spec['bytes'], root)
        chunks = iter(response.iter_content(chunk_size=64 * 1024))
        # HTTP chunks need not align with image signatures. Read a bounded
        # prefix before choosing the content type, then process every consumed
        # byte once through the same length/hash/final-chunk checks below.
        prefix, prefetched, prefetched_length = bytearray(), [], 0
        needed = min(IMAGE_HEADER_BYTES, spec['bytes'])
        for chunk in chunks:
            if not chunk:
                continue
            prefetched_length += len(chunk)
            if prefetched_length > spec['bytes']:
                raise OriginalError('Original exceeded its pinned size.')
            prefetched.append(chunk)
            prefix.extend(chunk[:needed - len(prefix)])
            if len(prefix) >= needed:
                break
        mime = mime_type(prefix)
        send_header(output, mime, spec['bytes'])
        # Keep only one Dropbox hash block in memory. Hold the final HTTP
        # chunk until the whole stream's length and hash have been verified;
        # a broken stream cannot become a complete browser-cached response.
        block_hashes, pending, length, last = hashlib.sha256(), bytearray(), 0, b''
        from itertools import chain
        for chunk in chain(prefetched, chunks):
            if not chunk:
                continue  # Keep the last actual bytes withheld until verification.
            length += len(chunk)
            if length > spec['bytes']:
                raise OriginalError('Original exceeded its pinned size.')
            pending.extend(chunk)
            while len(pending) >= 4 * 1024 * 1024:
                block_hashes.update(hashlib.sha256(pending[:4 * 1024 * 1024]).digest())
                del pending[:4 * 1024 * 1024]
            if last:
                output.write(last)
            last = chunk
        if pending:
            block_hashes.update(hashlib.sha256(pending).digest())
        if length != spec['bytes'] or block_hashes.hexdigest() != spec['hash']:
            raise OriginalError('Original failed byte verification.')
        output.write(last)
        output.flush()


def load_thumbnail(project, spec):
    # Existing previews are trusted as previews only, never as original bytes.
    local = spec.get('local')
    if local:
        try:
            return thumbnail(Path(local))
        except (OSError, ValueError):
            pass
    if not spec.get('native'):
        raise OriginalError('No retained preview is available.')
    from dropbox.files import PathOrLink, ThumbnailSize, ThumbnailMode
    with connection(project) as (client, root):
        result, response = client.files_get_thumbnail_v2(PathOrLink.path(spec['id']),
            size=ThumbnailSize.w1024h768, mode=ThumbnailMode.bestfit)
        with closing(response):
            check_metadata(result.file_metadata, spec['id'], spec['hash'], spec['bytes'], root)
            data = bytearray()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                data.extend(chunk)
                if len(data) > 8_000_000:
                    raise OriginalError('Thumbnail response exceeded its limit.')
        return thumbnail(BytesIO(data))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--action', required=True, choices=('thumbnail', 'original'))
    args = parser.parse_args()
    try:
        spec = json.loads(sys.stdin.buffer.read(32_768))
        if spec.get('native') and (not spec['id'].startswith('id:') or not re.fullmatch('[a-f0-9]{64}', spec['hash'])):
            raise OriginalError('Known native identity required.')
        if args.action == 'thumbnail':
            data = load_thumbnail(args.project, spec)
            send_header(sys.stdout.buffer, 'image/jpeg', len(data))
            sys.stdout.buffer.write(data)
        else:
            if not spec.get('native'):
                raise OriginalError('Known native identity required.')
            with connection(args.project) as (client, root):
                stream_original(client, spec, root, sys.stdout.buffer)
        return 0
    except Exception:
        # Never print exception text, temporary URLs, tokens or SDK responses.
        # If headers already went out, EOF causes a truncated HTTP response.
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
