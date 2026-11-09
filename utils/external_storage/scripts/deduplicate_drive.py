import sys
import os
from pathlib import Path

# Add script dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from object_storage import ObjectStorage

def deduplicate():
    storage = ObjectStorage()
    backend = storage.backend
    service = backend._get_service()
    
    root_id = backend.root_id
    
    # 1. Find all 'prospects' folders
    q = f"'{root_id}' in parents and name='prospects' and trashed=false"
    res = service.files().list(q=q, fields='files(id, name)').execute()
    prospects_folders = res.get('files', [])
    
    if len(prospects_folders) > 1:
        print(f"Found {len(prospects_folders)} prospects folders. Merging...")
        target_id = prospects_folders[0]['id']
        source_ids = [f['id'] for f in prospects_folders[1:]]
        
        for src_id in source_ids:
            print(f"Moving contents from {src_id} to {target_id}...")
            # List all items in source
            items = service.files().list(q=f"'{src_id}' in parents and trashed=false", fields='files(id, name)').execute()
            for item in items.get('files', []):
                print(f"  Moving {item['name']}...")
                service.files().update(
                    fileId=item['id'],
                    addParents=target_id,
                    removeParents=src_id,
                    fields='id, parents'
                ).execute()
            
            # Delete the now-empty source folder
            service.files().delete(fileId=src_id).execute()
            print(f"Deleted source folder {src_id}")
    else:
        print("Only one prospects folder found. No merge needed.")

    # 2. Delete stray zips in root
    print("Checking for stray zips in root...")
    res = service.files().list(q=f"'{root_id}' in parents and trashed=false", fields='files(id, name)').execute()
    for f in res.get('files', []):
        if f['name'].endswith('.zip'):
            print(f"Deleting stray zip: {f['name']}...")
            service.files().delete(fileId=f['id']).execute()

    print("Cleanup complete.")

if __name__ == "__main__":
    deduplicate()
