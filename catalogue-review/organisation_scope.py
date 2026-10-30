"""Distinguish tag-only references from originals eligible for folder moves."""
from dropbox_sync import NAMESPACE, ROOT_PATH


OUTSIDE_MESSAGE = 'Automatic organisation is limited to the Wall Sculptures folders. This reference stays in its current location.'
REFERENCE_NOTICE = 'Tags and component choices are saved in the app. This reference stays in its existing Dropbox folder outside Wall Sculptures.'


def native_path(asset):
    path = asset.get('provenance', {}).get('path') or ''
    prefix = 'ns:' + NAMESPACE + '/'
    if path.startswith(prefix):
        path = '/' + path[len(prefix):].lstrip('/')
    return path


def external_reference(asset):
    path = native_path(asset)
    # Unknown paths still need verification. Never silently waive a missing or
    # malformed location, or broaden the native writer's approved root.
    return (asset.get('source') == 'Dropbox' and asset.get('id', '').startswith('id:')
            and path.startswith('/') and path.casefold() != ROOT_PATH.casefold()
            and not path.casefold().startswith(ROOT_PATH.casefold() + '/'))
