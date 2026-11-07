"""Search the company Dropbox for overlooked source photographs and folders."""
from pathlib import Path
from datetime import datetime,timezone
import sys,json
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review'))
from delete_dropbox import connection
from dropbox.files import SearchOptions,FileMetadata,FolderMetadata

queries=['spice','shellmoon','moonshell','soundwave','moon-ring','acanthus']
results=[]
with connection(ROOT) as (db,_):
    for query in queries:
        response=db.files_search_v2(query,options=SearchOptions(path='/BOLDSTONE MASTER',filename_only=True,max_results=1000))
        matches=[];pages=0
        while True:
            pages+=1
            for item in response.matches:
                if not item.metadata.is_metadata():continue
                m=item.metadata.get_metadata()
                if not isinstance(m,(FileMetadata,FolderMetadata)):continue
                if isinstance(m,FileMetadata) and Path(m.name).suffix.lower() not in {'.jpg','.jpeg','.png','.tif','.tiff','.heic','.webp'}:continue
                row=dict(id=m.id,name=m.name,path=m.path_display,type='folder' if isinstance(m,FolderMetadata) else 'file')
                if isinstance(m,FileMetadata):row.update(bytes=m.size,content_hash=m.content_hash,revision=m.rev,modified_utc=m.server_modified.isoformat())
                matches.append(row)
            if not response.has_more:break
            response=db.files_search_continue_v2(response.cursor)
        results.append(dict(query=query,pages=pages,has_more=False,matches=matches,checked_utc=datetime.now(timezone.utc).isoformat()))
        (OUT/'dropbox-overlooked-original-search.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(dict(query=query,matches=len(matches),folders=sum(r['type']=='folder' for r in matches))),flush=True)
print('Finished company Dropbox keyword searches without changing or downloading files',flush=True)
