from datetime import datetime, timezone
from pathlib import Path
import json, sys

PROJECT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT / 'catalogue-review'))
from delete_dropbox import connection
from dropbox.common import PathRoot
from dropbox.files import FileMetadata, FolderMetadata

def info(m):
    result = {'object_type': 'file' if isinstance(m, FileMetadata) else 'folder'}
    for key in ('id', 'name', 'path_display', 'path_lower', 'rev', 'size', 'content_hash', 'server_modified', 'client_modified', 'is_downloadable', 'has_explicit_shared_members'):
        value = getattr(m, key, None)
        if value is not None:
            result[key] = value.isoformat() if isinstance(value, datetime) else value
    sharing = getattr(m, 'sharing_info', None)
    if sharing:
        result['sharing_info'] = {key:getattr(sharing,key) for key in ('parent_shared_folder_id','shared_folder_id','read_only','traverse_only') if getattr(sharing,key,None) is not None}
    return result

with connection(PROJECT) as (client, verified_catalogue_root):
    scoped = client.with_path_root(PathRoot.namespace_id('10782830832'))
    root = scoped.files_get_metadata('id:cnqzTNngPVsAAAAAAAgI_w')
    assert root.id == 'id:cnqzTNngPVsAAAAAAAgI_w' and root.name == 'Manning Books'
    response = scoped.files_list_folder('', recursive=True, limit=2000, include_deleted=False)
    rows = list(response.entries)
    while response.has_more:
        response = scoped.files_list_folder_continue(response.cursor)
        rows.extend(response.entries)
    links = []
    response = scoped.sharing_list_shared_links()
    links.extend(response.links)
    while response.has_more:
        response = scoped.sharing_list_shared_links(cursor=response.cursor)
        links.extend(response.links)
    relevant_links = []
    for link in links:
        path = getattr(link,'path_lower',None)
        if path and (path.startswith('/tom apps/manning books') or any(getattr(x,'path_lower',None)==path for x in rows)):
            relevant_links.append({'path_lower':path,'name':link.name,'url':link.url})
    result = {'status':'READ_ONLY_COMPLETE','checked_utc':datetime.now(timezone.utc).isoformat(),'root':info(root),'entries':[info(x) for x in rows], 'relevant_shared_links':relevant_links}
    (OUT / 'native-inventory.json').write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(json.dumps({'status':result['status'],'entries':len(rows),'files':sum(isinstance(x,FileMetadata) for x in rows),'shared_links_in_scope':len(relevant_links)}))
