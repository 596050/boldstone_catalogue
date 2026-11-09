import os
import sys
import logging
from pathlib import Path

# Add script dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from object_storage import ObjectStorage

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MigrateSingle")

def migrate_folder(target_folder: str):
    storage = ObjectStorage()
    base_dir = Path(target_folder)
    
    if not base_dir.exists():
        logger.error(f"Local directory '{base_dir}' does not exist.")
        return

    logger.info(f"Starting migration of '{base_dir}' to {storage.backend.__class__.__name__}...")

    upload_map = {}
    total_files = 0
    
    for root, _, files in os.walk(base_dir):
        for file in files:
            file_path = Path(root) / file
            
            # Skip hidden files
            if file.startswith('.'):
                continue

            # Calculate relative path from the project root
            # e.g. prospects/cii.co.uk/data.json
            cloud_key = str(file_path) 
            
            upload_map[cloud_key] = file_path
            total_files += 1

    if total_files > 0:
        logger.info(f"Found {total_files} files in '{target_folder}'. Uploading...")
        
        # Batch upload
        chunk_size = 10
        keys = list(upload_map.keys())
        processed = 0
        
        for i in range(0, total_files, chunk_size):
            chunk_keys = keys[i : i + chunk_size]
            batch_data = {}
            file_handles = []
            
            try:
                for key in chunk_keys:
                    # Check existence to skip
                    if storage.exists(key):
                        logger.info(f"Skipping existing: {key}")
                        processed += 1
                        continue
                        
                    path = upload_map[key]
                    f = open(path, 'rb')
                    file_handles.append(f)
                    batch_data[key] = f
                
                if batch_data:
                    storage.batch_save(batch_data, max_workers=4, atomic=True)
                    processed += len(batch_data)
                    logger.info(f"Progress: {processed}/{total_files} files uploaded.")
                    
            except Exception as e:
                logger.error(f"Batch failed: {e}")
            finally:
                for f in file_handles: f.close()
    else:
        logger.info(f"No files found in {target_folder}")

    logger.info("\nMigration Complete.")
    
    # Verification
    logger.info("\n--- Verification ---")
    # List files in the cloud folder
    # Note: list_objects takes a prefix. For Google Drive backend it resolves folders.
    # We want to see if 'prospects/cii.co.uk/' exists and has items.
    cloud_items = storage.list_objects(prefix=f"{target_folder}/")
    logger.info(f"Found {len(cloud_items)} items in cloud under '{target_folder}/'")
    if len(cloud_items) > 0:
        logger.info(f"Sample: {cloud_items[:5]}")
    else:
        logger.warning("No items found in cloud verification!")

if __name__ == "__main__":
    migrate_folder("prospects/cii.co.uk")
