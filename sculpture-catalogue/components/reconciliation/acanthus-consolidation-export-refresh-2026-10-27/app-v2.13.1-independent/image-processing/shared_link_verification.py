"""Verify saved shared URLs without treating their display slug as identity."""
import hashlib
import re
from urllib.parse import quote, urlsplit, urlunsplit


def original_url(old, current_url):
    """Return only a URL whose exact bytes match the frozen original digest.

    Dropbox can turn spaces and punctuation in a display filename into hyphens
    in its shared URL. Neither the shared-link token nor query is changed here.
    A plausible-looking slug alone is never accepted as the original link.
    """
    digest = old['url_sha256']
    if hashlib.sha256(current_url.encode()).hexdigest() == digest:
        return current_url
    url = urlsplit(current_url)
    name = old['name']
    names = (name, name.replace(' ', '-'), re.sub(r'[ ,]+', '-', name))
    for tail in dict.fromkeys(quote(value, safe='-._~') for value in names):
        candidate = urlunsplit((url.scheme, url.netloc, url.path.rsplit('/', 1)[0] + '/' + tail,
                               url.query, url.fragment))
        if hashlib.sha256(candidate.encode()).hexdigest() == digest:
            return candidate
    return None


def link_proof(client, old, owned):
    for item in owned:
        current = item['record']
        if current['id'] != old['id']:
            continue
        candidate = original_url(old, item['url'])
        if candidate is None:
            continue
        same = current['url_sha256'] == old['url_sha256']
        if not same and client.sharing_get_shared_link_metadata(url=candidate).id != old['id']:
            continue
        return {'current': current, 'original_url_unchanged': same,
                'original_url_reconstructed_hash_verified': not same,
                'original_link_resolves_to_same_id': True}
    return None
