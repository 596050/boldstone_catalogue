import sys
import os
from collections import defaultdict
from pathlib import Path

# Add script dir to path
sys.path.append(os.path.join(os.getcwd(), 'external_storage', 'scripts'))
from object_storage import ObjectStorage

def deep_inspect():
    storage = ObjectStorage()
    backend = storage.backend
    service = backend._get_service()
    
    root_id = backend.root_id
    print(f"Scanning directory structure starting from root: {backend.root_folder_name} ({root_id})...")
    
    # Queue for BFS: (folder_id, folder_name, path_string)
    queue = [(root_id, backend.root_folder_name, "")]
    
    issue_count = 0
    checked_folders = 0
    
    while queue:
        current_id, current_name, current_path = queue.pop(0)
        checked_folders += 1
        
        # List sub-folders only
        q = f"'{current_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        sub_folders = []
        page_token = None
        while True:
            res = service.files().list(
                q=q, 
                fields='nextPageToken, files(id, name)', 
                pageToken=page_token
            ).execute()
            sub_folders.extend(res.get('files', []))
            page_token = res.get('nextPageToken')
            if not page_token: break
        
        # Check for duplicates (siblings with same name)
        name_map = defaultdict(list)
        for f in sub_folders:
            name_map[f['name']].append(f)
            
        for name, instances in name_map.items():
            if len(instances) > 1:
                print(f"\n[!] DUPLICATE DETECTED at '{current_path}/{name}':")
                for inst in instances:
                    print(f"    - ID: {inst['id']}")
                issue_count += 1
        
        # Check for recursive nesting (child name == parent name)
        for f in sub_folders:
            new_path = f"{current_path}/{f['name']}"
            
            if f['name'] == current_name:
                print(f"\n[!] SUSPICIOUS NESTING DETECTED: '{new_path}'")
                print(f"    Parent '{current_name}' contains child '{f['name']}'")
                issue_count += 1
            
            # Add to queue for deeper scan
            # Limit depth/breadth if necessary, but we need to check full structure
            queue.append((f['id'], f['name'], new_path))
            
        if checked_folders % 10 == 0:
            sys.stdout.write(f"\rScanned {checked_folders} folders...")
            sys.stdout.flush()

    print(f"\n\nScan complete. Checked {checked_folders} folders.")
    if issue_count == 0:
        print("✅ Structure appears valid. No directory duplicates or recursive nesting found.")
    else:
        print(f"❌ Found {issue_count} structural issues.")

if __name__ == "__main__":
    deep_inspect()
