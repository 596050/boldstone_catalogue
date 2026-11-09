import os
import sys
import shutil
import logging
import zipfile
import tempfile
from pathlib import Path

# Add script dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from object_storage import ObjectStorage

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MigrateProspects")

def migrate_prospects():
    storage = ObjectStorage()
    base_dir = Path("prospects")
    
    if not base_dir.exists():
        logger.error(f"Local directory '{base_dir}' does not exist.")
        return

    logger.info(f"Starting migration of '{base_dir}' to {storage.backend.__class__.__name__}...")

    # 1. Process Zip Files first (The large ones)
    zip_files = list(base_dir.glob("*.zip"))
    for zip_path in zip_files:
        logger.info(f"\n--- Processing Archive: {zip_path.name} ---")
        
        # Define destination "folder" in cloud (remove .zip extension)
        # e.g. prospects/financialadvisers.co.uk.zip -> prospects/financialadvisers.co.uk/
        dest_prefix = f"prospects/{zip_path.stem}"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"Extracting {zip_path} to temp dir...")
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    # Filter out purely "directory" entries to avoid clutter
                    files_to_extract = [f for f in zip_ref.namelist() if not f.endswith('/')]
                    zip_ref.extractall(temp_dir, members=files_to_extract)
                
                logger.info(f"Extraction complete. Scanning files...")
                upload_map = {}
                count = 0
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        local_path = Path(root) / file
                        # Calculate relative path inside the zip
                        rel_path = local_path.relative_to(temp_dir)
                        # Cloud Key: prospects/<zip_name>/<inner_path>
                        cloud_key = f"{dest_prefix}/{rel_path}"
                        
                        # Read file data
                        # Note: For massive files, we might want to read byte streams, 
                        # but batch_save expects data it can submit. 
                        # ObjectStorage.save handles paths/bytes. 
                        # Let's pass the Path object directly if backend supported it, 
                        # but currently it expects bytes/str/IO.
                        # We will open them lazily in the batch? 
                        # No, ObjectStorage.batch_save expects {key: data}. 
                        # Opening thousands of file handles is bad.
                        
                        # Better approach: Iterate and upload in chunks of 50
                        upload_map[cloud_key] = local_path
                        count += 1
                
                logger.info(f"Found {count} files in archive. Starting batch upload...")
                process_upload_queue(storage, upload_map)
                
            except zipfile.BadZipFile:
                logger.error(f"Failed to unzip {zip_path}: Bad Zip File")
            except Exception as e:
                logger.error(f"Error processing {zip_path}: {e}")

    # 2. Process Regular Folders
    # We walk 'prospects/' but exclude the zips we just processed
    logger.info(f"\n--- Processing Regular Folders in '{base_dir}' ---")
    upload_map = {}
    total_files = 0
    
    for root, _, files in os.walk(base_dir):
        for file in files:
            file_path = Path(root) / file
            
            # Skip the zips themselves (we processed their contents)
            if file_path in zip_files:
                continue
            
            # Skip hidden files
            if file.startswith('.'):
                continue

            rel_path = file_path.relative_to(Path(".")) # e.g. prospects/site/file.txt
            cloud_key = str(rel_path) # key matches local path
            
            upload_map[cloud_key] = file_path
            total_files += 1

    if total_files > 0:
        logger.info(f"Found {total_files} regular files. Uploading...")
        process_upload_queue(storage, upload_map)
    else:
        logger.info("No regular files found to migrate.")

    logger.info("\nMigration Complete.")

def process_upload_queue(storage, upload_map):
    """
    Helper to upload files in batches. 
    Keys are cloud keys, Values are LOCAL PATH objects.
    """
    chunk_size = 10 
    keys = list(upload_map.keys())
    
    total = len(keys)
    processed = 0
    
    # Process in chunks to avoid opening too many files at once
    for i in range(0, total, chunk_size):
        chunk_keys = keys[i : i + chunk_size]
        batch_data = {}
        file_handles = []
        
        try:
            for key in chunk_keys:
                # Check if file already exists in cloud (Resumable logic)
                if storage.exists(key):
                    logger.info(f"Skipping existing: {key}")
                    processed += 1 # Count as processed
                    continue

                path = upload_map[key]
                f = open(path, 'rb')
                file_handles.append(f)
                batch_data[key] = f
            
            # Upload this chunk (if any files remain)
            if batch_data:
                storage.batch_save(batch_data, max_workers=4, atomic=True)
                processed += len(batch_data)
                logger.info(f"Progress: {processed}/{total} files processed.")
            
        except Exception as e:
            logger.error(f"Batch failed: {e}")
        finally:
            # Close handles
            for f in file_handles:
                f.close()

if __name__ == "__main__":
    migrate_prospects()
