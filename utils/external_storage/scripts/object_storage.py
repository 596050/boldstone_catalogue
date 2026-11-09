import os
import sys
import shutil
import logging
import io
import mimetypes
import json
import zipfile
import time
import hashlib
import ssl
import threading
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Union, BinaryIO
from datetime import datetime
from pathlib import Path

# External libraries for robustness
try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, retry_if_result
    RETRIES_ENABLED = True
except ImportError as e:
    # Debugging import failure
    sys.stderr.write(f"Warning: tenacity module not found ({e}). Retries disabled.\n")
    RETRIES_ENABLED = False
    def retry(*args, **kwargs):
        def decorator(f): return f
        return decorator
    def stop_after_attempt(*args, **kwargs): pass
    def wait_exponential(*args, **kwargs): pass
    def retry_if_exception_type(*args, **kwargs): pass
    def retry_if_result(*args, **kwargs): pass

# Try to load dotenv
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(dotenv_path=None): pass

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Dependencies Check ---
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
    from googleapiclient.errors import HttpError
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    class HttpError(Exception): pass

try:
    import boto3
    from botocore.exceptions import ClientError
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False
    class ClientError(Exception): pass


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    def calculate_md5(self, data: Union[bytes, str, BinaryIO]) -> str:
        """Helper to calculate MD5 of data."""
        hash_md5 = hashlib.md5()
        if isinstance(data, str):
            hash_md5.update(data.encode('utf-8'))
        elif isinstance(data, bytes):
            hash_md5.update(data)
        elif hasattr(data, 'read'):
            # Save position
            pos = data.tell()
            for chunk in iter(lambda: data.read(4096), b""):
                hash_md5.update(chunk)
            # Reset position
            data.seek(pos)
        return hash_md5.hexdigest()

    @abstractmethod
    def save(self, key: str, data: Union[bytes, str, BinaryIO], content_type: Optional[str] = None) -> str:
        pass

    @abstractmethod
    def download(self, key: str) -> bytes:
        pass
    
    @abstractmethod
    def download_to_file(self, key: str, file_path: str) -> None:
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        pass
    
    @abstractmethod
    def rename(self, old_key: str, new_key: str) -> bool:
        """Rename/Move an object."""
        pass

    @abstractmethod
    def list_objects(self, prefix: str = "") -> List[str]:
        pass

    @abstractmethod
    def get_metadata(self, key: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_storage_usage(self) -> Dict[str, Union[int, float]]:
        """Returns storage usage statistics (used, total, percent)."""
        pass
        
    def upload_zip(self, local_folder: str, key: str) -> str:
        """Zips a local directory and uploads it."""
        logger.info(f"Zipping {local_folder}...")
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for root, _, files in os.walk(local_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, local_folder)
                    zip_file.write(file_path, arcname)
        
        zip_buffer.seek(0)
        return self.save_atomic(key, zip_buffer, content_type="application/zip")

    def download_unzip(self, key: str, extract_to: str) -> None:
        """Downloads a zip object and extracts it locally."""
        logger.info(f"Downloading and unzipping {key} to {extract_to}...")
        zip_data = self.download(key)
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_ref:
            zip_ref.extractall(extract_to)

    def save_atomic(self, key: str, data: Union[bytes, str, BinaryIO], content_type: Optional[str] = None) -> str:
        """
        Atomic Save:
        1. Upload to temporary key.
        2. Verify MD5 checksum.
        3. Rename/Move to final key.
        4. Cleanup on failure.
        """
        temp_key = f"{key}.tmp.{int(time.time())}"
        logger.debug(f"Starting atomic save for {key} via temp key {temp_key}")
        
        try:
            # 1. Calculate MD5 (and reset stream)
            logger.debug("Calculating local MD5...")
            expected_md5 = self.calculate_md5(data)
            logger.debug(f"Local MD5: {expected_md5}")
            
            if hasattr(data, 'seek'):
                data.seek(0)

            # 2. Upload
            logger.info(f"Uploading atomic: {temp_key}")
            self.save(temp_key, data, content_type)
            
            # 3. Verify
            logger.debug("Fetching cloud metadata for verification...")
            meta = self.get_metadata(temp_key)
            cloud_md5 = meta.get('md5')
            logger.debug(f"Cloud MD5: {cloud_md5}")
            
            # Note: S3 Multipart uploads don't have standard MD5s (they contain '-'), so we skip if detected
            if cloud_md5 and '-' not in cloud_md5 and cloud_md5 != expected_md5:
                raise ValueError(f"Integrity Check Failed! Local: {expected_md5}, Cloud: {cloud_md5}")
            
            logger.info(f"Integrity verified for {temp_key}")
            
            # 4. Rename/Move (Commit)
            # Delete existing target if any (overwrite behavior)
            if self.exists(key):
                logger.debug(f"Deleting existing target {key} before rename")
                self.delete(key)
            
            self.rename(temp_key, key)
            logger.info(f"Atomic save completed: {key}")
            return key
            
        except Exception as e:
            logger.error(f"Atomic save failed: {e}. Cleaning up {temp_key}")
            try:
                self.delete(temp_key)
            except:
                pass
            raise e


class LocalStorageBackend(StorageBackend):
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized LocalStorageBackend at {self.base_path}")

    def _get_full_path(self, key: str) -> Path:
        clean_key = key.strip("/")
        full_path = (self.base_path / clean_key).resolve()
        if not str(full_path).startswith(str(self.base_path.resolve())):
            raise ValueError(f"Invalid key: {key}")
        return full_path

    def save(self, key: str, data: Union[bytes, str, BinaryIO], content_type: Optional[str] = None) -> str:
        full_path = self._get_full_path(key)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        mode = 'wb'
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        with open(full_path, mode) as f:
            if hasattr(data, 'read'):
                shutil.copyfileobj(data, f)
            else:
                f.write(data)
        return key

    def download(self, key: str) -> bytes:
        return self._get_full_path(key).read_bytes()

    def download_to_file(self, key: str, file_path: str) -> None:
        src = self._get_full_path(key)
        dest = Path(file_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    def delete(self, key: str) -> bool:
        p = self._get_full_path(key)
        if p.exists():
            p.unlink()
            return True
        return False

    def exists(self, key: str) -> bool:
        return self._get_full_path(key).exists()
        
    def rename(self, old_key: str, new_key: str) -> bool:
        old_path = self._get_full_path(old_key)
        new_path = self._get_full_path(new_key)
        if not old_path.exists(): return False
        new_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(old_path, new_path)
        return True

    def list_objects(self, prefix: str = "") -> List[str]:
        results = []
        for root, _, files in os.walk(self.base_path):
            for file in files:
                abs_p = Path(root) / file
                rel_p = str(abs_p.relative_to(self.base_path))
                if rel_p.startswith(prefix):
                    results.append(rel_p)
        return sorted(results)

    def get_metadata(self, key: str) -> Dict[str, Any]:
        stat = self._get_full_path(key).stat()
        # MD5 for local
        with open(self._get_full_path(key), 'rb') as f:
            md5 = hashlib.md5(f.read()).hexdigest()
        
        return {
            "size": stat.st_size, 
            "modified": datetime.fromtimestamp(stat.st_mtime), 
            "backend": "local",
            "md5": md5
        }

    def get_storage_usage(self) -> Dict[str, Union[int, float]]:
        total, used, free = shutil.disk_usage(self.base_path)
        return {
            "used_bytes": used,
            "total_bytes": total,
            "free_bytes": free,
            "usage_percent": (used / total) * 100 if total > 0 else 0
        }


class S3StorageBackend(StorageBackend):
    def __init__(self, bucket_name: str, region_name: str = None, access_key: str = None, secret_key: str = None, root_prefix: str = ""):
        if not S3_AVAILABLE:
            raise ImportError("boto3 not installed.")
        self.bucket = bucket_name
        self.client = boto3.client('s3', region_name=region_name, aws_access_key_id=access_key, aws_secret_access_key=secret_key)
        self.root_prefix = root_prefix.strip("/")
        if self.root_prefix:
            self.root_prefix += "/"

    def _get_key(self, key: str) -> str:
        return f"{self.root_prefix}{key.strip('/')}"

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=20), retry=retry_if_exception_type(ClientError))
    def save(self, key: str, data: Union[bytes, str, BinaryIO], content_type: Optional[str] = None) -> str:
        full_key = self._get_key(key)
        args = {'ContentType': content_type} if content_type else {}
        if isinstance(data, str): data = data.encode('utf-8')
        
        if hasattr(data, 'read'):
            self.client.upload_fileobj(data, self.bucket, full_key, ExtraArgs=args)
        else:
            self.client.put_object(Bucket=self.bucket, Key=full_key, Body=data, **args)
        return key

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=20), retry=retry_if_exception_type(ClientError))
    def download(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=self._get_key(key))['Body'].read()

    def download_to_file(self, key: str, file_path: str) -> None:
        self.client.download_file(self.bucket, self._get_key(key), file_path)

    def delete(self, key: str) -> bool:
        self.client.delete_object(Bucket=self.bucket, Key=self._get_key(key))
        return True

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._get_key(key))
            return True
        except ClientError:
            return False
            
    def rename(self, old_key: str, new_key: str) -> bool:
        # S3 rename is Copy + Delete
        old_full = self._get_key(old_key)
        new_full = self._get_key(new_key)
        self.client.copy_object(Bucket=self.bucket, CopySource={'Bucket': self.bucket, 'Key': old_full}, Key=new_full)
        self.client.delete_object(Bucket=self.bucket, Key=old_full)
        return True

    def list_objects(self, prefix: str = "") -> List[str]:
        full_prefix = self._get_key(prefix)
        res = self.client.list_objects_v2(Bucket=self.bucket, Prefix=full_prefix)
        objects = []
        for o in res.get('Contents', []):
            key = o['Key']
            if key.startswith(self.root_prefix):
                objects.append(key[len(self.root_prefix):])
            else:
                objects.append(key)
        return objects

    def get_metadata(self, key: str) -> Dict[str, Any]:
        res = self.client.head_object(Bucket=self.bucket, Key=self._get_key(key))
        # ETag is MD5 for normal uploads (wrapped in quotes)
        etag = res.get('ETag', '').strip('"')
        return {"size": res['ContentLength'], "modified": res['LastModified'], "backend": "s3", "md5": etag}

    def get_storage_usage(self) -> Dict[str, Union[int, float]]:
        # S3 metrics are complex and async. Returning placeholder.
        return {"used_bytes": -1, "total_bytes": -1, "free_bytes": -1, "usage_percent": 0}


class GoogleDriveStorageBackend(StorageBackend):
    SCOPES = ['https://www.googleapis.com/auth/drive']

    def __init__(self, token_path: str, client_secret_path: str, root_folder_name: str = "uk_financial_services"):
        if not GOOGLE_AVAILABLE:
            raise ImportError("Google client libraries not installed.")

        self.token_path = Path(token_path)
        self.client_secret_path = Path(client_secret_path)
        self.root_folder_name = root_folder_name
        self.creds = self._authenticate()

        # Thread-local storage for service instances
        self.thread_local = threading.local()

        # Lock for folder creation to prevent duplicates from race conditions
        self._folder_lock = threading.Lock()
        # Cache of folder paths to IDs to reduce API calls
        self._folder_cache: Dict[str, str] = {}

        # Initialize root folder (using a temporary service if needed, or Main Thread)
        # We use a temporary build here just for init to avoid thread sharing issues
        tmp_service = build('drive', 'v3', credentials=self.creds)
        self.root_id = self._get_or_create_folder(self.root_folder_name, service=tmp_service)
        logger.info(f"Initialized GoogleDriveStorageBackend. Root '{self.root_folder_name}' ID: {self.root_id}")

    def _get_service(self):
        """Returns a thread-local service instance."""
        if not hasattr(self.thread_local, "service"):
            self.thread_local.service = build('drive', 'v3', credentials=self.creds)
        return self.thread_local.service

    def _authenticate(self):
        creds = None
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), self.SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing Google Drive Access Token...")
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Failed to refresh token: {e}. Re-authenticating.")
                    creds = None
            
            if not creds:
                if not self.client_secret_path.exists():
                     raise FileNotFoundError(f"Client secret not found at {self.client_secret_path}. Cannot authenticate.")
                
                if not os.isatty(sys.stdin.fileno()):
                     logger.warning("Running in non-interactive mode but authentication is required.")

                flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secret_path), self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
        
        return creds

    def get_user_info(self) -> Dict[str, str]:
        try:
            about = self._get_service().about().get(fields="user").execute()
            return about.get('user', {})
        except Exception as e:
            logger.warning(f"Could not fetch user info: {e}")
            return {}
            
    def get_storage_usage(self) -> Dict[str, Union[int, float]]:
        try:
            about = self._get_service().about().get(fields="storageQuota").execute()
            quota = about.get('storageQuota', {})
            used = int(quota.get('usage', 0))
            limit = int(quota.get('limit', 0))
            return {
                "used_bytes": used,
                "total_bytes": limit,
                "free_bytes": limit - used if limit > 0 else 0,
                "usage_percent": (used / limit * 100) if limit > 0 else 0
            }
        except Exception as e:
            logger.warning(f"Could not fetch storage quota: {e}")
            return {}

    def get_item_link(self, file_id: str) -> str:
        try:
            f = self._get_service().files().get(fileId=file_id, fields="webViewLink").execute()
            return f.get('webViewLink', 'Unknown Link')
        except Exception:
            return "Unknown Link"

    def _get_or_create_folder(self, name: str, parent_id: str = None, service=None) -> str:
        """Get or create a folder, using a lock to prevent duplicate creation.

        Uses a cache to reduce API calls and a lock to prevent race conditions
        where multiple threads might create the same folder simultaneously.
        """
        # Use provided service (during init) or thread-local service
        srv = service if service else self._get_service()

        # Build cache key
        cache_key = f"{parent_id or 'root'}:{name}"

        # Check cache first (outside lock for performance)
        if cache_key in self._folder_cache:
            return self._folder_cache[cache_key]

        # Acquire lock to prevent race conditions
        with self._folder_lock:
            # Double-check cache inside lock (another thread may have populated it)
            if cache_key in self._folder_cache:
                return self._folder_cache[cache_key]

            q = f"mimeType='application/vnd.google-apps.folder' and name='{name}' and trashed=false"
            if parent_id:
                q += f" and '{parent_id}' in parents"

            results = srv.files().list(q=q, fields="files(id, name, webViewLink)").execute()
            files = results.get('files', [])

            if files:
                folder_id = files[0]['id']
                self._folder_cache[cache_key] = folder_id
                return folder_id

            metadata = {'name': name, 'mimeType': 'application/vnd.google-apps.folder'}
            if parent_id:
                metadata['parents'] = [parent_id]

            file = srv.files().create(body=metadata, fields='id').execute()
            folder_id = file.get('id')
            self._folder_cache[cache_key] = folder_id
            return folder_id

    def _resolve_path(self, key: str, create_dirs: bool = False) -> Optional[tuple[str, str]]:
        logger.debug(f"Resolving path: {key} (create_dirs={create_dirs})")
        parts = key.strip("/").split("/")
        filename = parts[-1]
        folders = parts[:-1]
        
        current_parent_id = self.root_id
        
        for folder in folders:
            if create_dirs:
                current_parent_id = self._get_or_create_folder(folder, current_parent_id)
            else:
                q = f"mimeType='application/vnd.google-apps.folder' and name='{folder}' and '{current_parent_id}' in parents and trashed=false"
                logger.debug(f"Searching for folder '{folder}' in parent {current_parent_id}")
                results = self._get_service().files().list(q=q, fields="files(id)").execute()
                files = results.get('files', [])
                if not files:
                    logger.debug(f"Folder '{folder}' not found.")
                    return None, None
                current_parent_id = files[0]['id']
        
        q = f"name='{filename}' and '{current_parent_id}' in parents and trashed=false"
        q += " and mimeType!='application/vnd.google-apps.folder'" 
        
        logger.debug(f"Searching for file '{filename}' in parent {current_parent_id}")
        results = self._get_service().files().list(q=q, fields="files(id)").execute()
        files = results.get('files', [])
        
        if files:
            file_id = files[0]['id']
            logger.debug(f"Found existing file: {file_id}")
            return file_id, current_parent_id
        
        logger.debug("File not found.")
        return None, current_parent_id

    @retry(stop=stop_after_attempt(6), wait=wait_exponential(multiplier=1, min=2, max=60), retry=retry_if_exception_type((HttpError, ssl.SSLError)))
    def save(self, key: str, data: Union[bytes, str, BinaryIO], content_type: Optional[str] = None) -> str:
        logger.debug(f"Starting raw save for {key}")
        file_id, parent_id = self._resolve_path(key, create_dirs=True)
        
        if isinstance(data, str):
            data_stream = io.BytesIO(data.encode('utf-8'))
        elif isinstance(data, bytes):
            data_stream = io.BytesIO(data)
        else:
            data_stream = data
        
        if not content_type:
            content_type, _ = mimetypes.guess_type(key)
        if not content_type:
            content_type = 'application/octet-stream'
        
        media = MediaIoBaseUpload(data_stream, mimetype=content_type, resumable=True)
        
        if file_id:
            logger.debug(f"Updating existing file ID {file_id}")
            self._get_service().files().update(fileId=file_id, media_body=media).execute()
        else:
            logger.debug(f"Creating new file in parent {parent_id}")
            metadata = {'name': key.split("/")[-1], 'parents': [parent_id]}
            self._get_service().files().create(body=metadata, media_body=media, fields='id').execute()
        
        logger.debug(f"Raw save completed for {key}")
        return key

    @retry(stop=stop_after_attempt(6), wait=wait_exponential(multiplier=1, min=2, max=60), retry=retry_if_exception_type((HttpError, ssl.SSLError)))
    def download(self, key: str) -> bytes:
        file_id, _ = self._resolve_path(key)
        if not file_id:
            raise FileNotFoundError(f"Key {key} not found in Drive.")
        
        request = self._get_service().files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        return fh.getvalue()

    def download_to_file(self, key: str, file_path: str) -> None:
        content = self.download(key)
        with open(file_path, 'wb') as f:
            f.write(content)

    @retry(stop=stop_after_attempt(6), wait=wait_exponential(multiplier=1, min=2, max=60), retry=retry_if_exception_type((HttpError, ssl.SSLError)))
    def delete(self, key: str) -> bool:
        file_id, _ = self._resolve_path(key)
        if file_id:
            self._get_service().files().delete(fileId=file_id).execute()
            return True
        return False
        
    def rename(self, old_key: str, new_key: str) -> bool:
        # Atomic rename (Move)
        file_id, _ = self._resolve_path(old_key)
        if not file_id: return False
        
        # Ensure destination folder exists
        _, dest_parent_id = self._resolve_path(new_key, create_dirs=True)
        new_name = new_key.split("/")[-1]
        
        # Patch request to move and rename
        # We need to get current parents to remove them
        file = self._get_service().files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents'))
        
        self._get_service().files().update(
            fileId=file_id,
            addParents=dest_parent_id,
            removeParents=previous_parents,
            body={'name': new_name},
            fields='id, parents'
        ).execute()
        return True

    def exists(self, key: str) -> bool:
        file_id, _ = self._resolve_path(key)
        return file_id is not None

    def list_objects(self, prefix: str = "") -> List[str]:
        """
        Lists files matching the prefix.
        Supports folder navigation e.g. 'tests/' lists files in 'tests' folder.
        """
        logger.info(f"Listing objects with prefix: {prefix}")
        
        parent_id = self.root_id
        name_filter = prefix
        
        # If prefix implies a subdirectory
        if "/" in prefix:
            if prefix.endswith("/"):
                folder_path = prefix.rstrip("/")
                name_filter = ""
            else:
                folder_path, name_filter = prefix.rsplit("/", 1)
            
            # Resolve folder
            current_id = self.root_id
            found_folder = True
            for folder_name in folder_path.split("/"):
                if not folder_name: continue
                q = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and '{current_id}' in parents and trashed=false"
                res = self._get_service().files().list(q=q, fields="files(id)").execute()
                files = res.get('files', [])
                if not files:
                    found_folder = False
                    break
                current_id = files[0]['id']
            
            if found_folder:
                parent_id = current_id
            else:
                logger.warning(f"Folder path '{folder_path}' not found.")
                return []

        # List files in the resolved parent folder
        q = f"'{parent_id}' in parents and trashed=false"
        results = []
        page_token = None
        while True:
            response = self._get_service().files().list(
                q=q, spaces='drive', fields='nextPageToken, files(id, name, mimeType)', pageToken=page_token
            ).execute()
            for file in response.get('files', []):
                # We interpret "objects" as files, not subfolders
                if file['mimeType'] != 'application/vnd.google-apps.folder':
                    if file['name'].startswith(name_filter):
                        if "/" in prefix:
                            full_key = f"{folder_path}/{file['name']}"
                        else:
                            full_key = file['name']
                        results.append(full_key)
            page_token = response.get('nextPageToken')
            if not page_token: break

        return sorted(results)

    def deduplicate_folders(self, prefix: str = "") -> Dict[str, Any]:
        """Find and consolidate duplicate folders under the given prefix.

        Google Drive allows multiple folders with the same name at the same level.
        This method finds such duplicates, moves all contents to the first folder,
        and trashes the empty duplicates.

        Args:
            prefix: Path prefix to deduplicate (e.g., "prospects/cii.co.uk").
                    If empty, deduplicates from root.

        Returns:
            Dict with stats: {folders_merged, files_moved, errors, details: [...]}
        """
        logger.info(f"Deduplicating folders under prefix: '{prefix}'")
        srv = self._get_service()

        result = {
            "folders_merged": 0,
            "files_moved": 0,
            "errors": 0,
            "details": [],
        }

        # Navigate to the starting folder
        start_id = self.root_id
        if prefix:
            parts = prefix.strip("/").split("/")
            for folder_name in parts:
                if not folder_name:
                    continue
                q = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and '{start_id}' in parents and trashed=false"
                res = srv.files().list(q=q, fields="files(id)").execute()
                files = res.get('files', [])
                if not files:
                    logger.warning(f"Folder '{folder_name}' not found under {start_id}")
                    return result
                start_id = files[0]['id']

        def dedupe_recursive(parent_id: str, path: str, depth: int = 0, max_depth: int = 20):
            """Recursively deduplicate folders."""
            if depth > max_depth:
                return

            # Find all subfolders in this parent
            q = f"mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
            folders_by_name: Dict[str, List[Dict]] = {}
            page_token = None

            while True:
                res = srv.files().list(
                    q=q,
                    fields="nextPageToken, files(id, name)",
                    pageToken=page_token,
                    pageSize=1000
                ).execute()

                for f in res.get('files', []):
                    name = f['name']
                    if name not in folders_by_name:
                        folders_by_name[name] = []
                    folders_by_name[name].append(f)

                page_token = res.get('nextPageToken')
                if not page_token:
                    break

            # Process folders with duplicates
            for name, folders in folders_by_name.items():
                folder_path = f"{path}/{name}" if path else name

                if len(folders) > 1:
                    # Keep the first folder, merge others into it
                    primary = folders[0]
                    duplicates = folders[1:]

                    logger.info(f"Found {len(duplicates)} duplicate(s) of '{folder_path}'")

                    for dup in duplicates:
                        try:
                            moved = self._merge_folder_contents(dup['id'], primary['id'], srv)
                            result["files_moved"] += moved
                            result["folders_merged"] += 1
                            result["details"].append({
                                "path": folder_path,
                                "merged_id": dup['id'],
                                "into_id": primary['id'],
                                "files_moved": moved,
                            })
                        except Exception as e:
                            logger.error(f"Error merging {folder_path}: {e}")
                            result["errors"] += 1

                # Recurse into the primary (or only) folder
                primary_id = folders[0]['id']
                dedupe_recursive(primary_id, folder_path, depth + 1, max_depth)

        dedupe_recursive(start_id, prefix)

        # Clear folder cache since structure changed
        self._folder_cache.clear()

        logger.info(
            f"Deduplication complete: {result['folders_merged']} folders merged, "
            f"{result['files_moved']} files moved, {result['errors']} errors"
        )
        return result

    def _merge_folder_contents(self, source_id: str, target_id: str, srv) -> int:
        """Move all contents from source folder to target, then trash source.

        Returns the number of items moved.
        """
        moved = 0
        page_token = None

        while True:
            # Get all items in source folder
            res = srv.files().list(
                q=f"'{source_id}' in parents and trashed=false",
                fields="nextPageToken, files(id, name, mimeType)",
                pageToken=page_token,
                pageSize=1000
            ).execute()

            for item in res.get('files', []):
                try:
                    # Move item to target folder
                    srv.files().update(
                        fileId=item['id'],
                        addParents=target_id,
                        removeParents=source_id,
                        fields='id'
                    ).execute()
                    moved += 1
                except Exception as e:
                    logger.warning(f"Failed to move {item['name']}: {e}")

            page_token = res.get('nextPageToken')
            if not page_token:
                break

        # Trash the now-empty source folder
        try:
            srv.files().update(fileId=source_id, body={'trashed': True}).execute()
            logger.debug(f"Trashed empty folder {source_id}")
        except Exception as e:
            logger.warning(f"Failed to trash folder {source_id}: {e}")

        return moved

    def get_metadata(self, key: str) -> Dict[str, Any]:
        file_id, _ = self._resolve_path(key)
        if not file_id:
            raise FileNotFoundError(f"Key {key} not found.")
        
        f = self._get_service().files().get(fileId=file_id, fields="size, modifiedTime, md5Checksum").execute()
        return {
            "size": int(f.get('size', 0)),
            "modified": f.get('modifiedTime'),
            "backend": "google_drive",
            "md5": f.get('md5Checksum')
        }


class ObjectStorage:
    ROOT_CONTAINER = "uk_financial_services"

    def __init__(self, env_file_path: Optional[str] = None):
        if env_file_path is None:
            env_file_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
        
        load_dotenv(env_file_path)
        
        backend = os.getenv("STORAGE_BACKEND", "google_drive").lower()
        
        if backend == "google_drive":
            cred_dir = Path(__file__).resolve().parent.parent / "credentials"
            token_file = os.getenv("GOOGLE_TOKEN_FILE", str(cred_dir / "google_drive_token.json"))
            secret_file = os.getenv("GOOGLE_CLIENT_SECRET_FILE", str(cred_dir / "client_secret.json"))
            self.backend = GoogleDriveStorageBackend(token_file, secret_file, root_folder_name=self.ROOT_CONTAINER)
        elif backend == "s3":
            self.backend = S3StorageBackend(
                bucket_name=os.getenv("S3_BUCKET_NAME"),
                region_name=os.getenv("AWS_REGION"),
                access_key=os.getenv("AWS_ACCESS_KEY_ID"),
                secret_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                root_prefix=self.ROOT_CONTAINER
            )
        else: # Local
            base = os.getenv("LOCAL_STORAGE_PATH", str(Path(__file__).resolve().parent.parent / "data"))
            full_path = str(Path(base) / self.ROOT_CONTAINER)
            self.backend = LocalStorageBackend(full_path)

    def save(self, key: str, data: Any, content_type: str = None, atomic: bool = True) -> str:
        if atomic:
            return self.backend.save_atomic(key, data, content_type)
        return self.backend.save(key, data, content_type)

    def download(self, *args, **kwargs): return self.backend.download(*args, **kwargs)
    def download_to_file(self, *args, **kwargs): return self.backend.download_to_file(*args, **kwargs)
    def delete(self, *args, **kwargs): return self.backend.delete(*args, **kwargs)
    def exists(self, *args, **kwargs): return self.backend.exists(*args, **kwargs)
    def list_objects(self, *args, **kwargs): return self.backend.list_objects(*args, **kwargs)
    def get_metadata(self, *args, **kwargs): return self.backend.get_metadata(*args, **kwargs)
    def get_storage_usage(self, *args, **kwargs): return self.backend.get_storage_usage(*args, **kwargs)

    def deduplicate_folders(self, prefix: str = "") -> Dict[str, Any]:
        """Find and consolidate duplicate folders under the given prefix.

        Only supported for Google Drive backend. Returns empty dict for others.
        """
        if hasattr(self.backend, 'deduplicate_folders'):
            return self.backend.deduplicate_folders(prefix)
        logger.warning("deduplicate_folders not supported for this backend")
        return {"folders_merged": 0, "files_moved": 0, "errors": 0, "details": []}
    
    def upload_zip(self, *args, **kwargs): return self.backend.upload_zip(*args, **kwargs)
    def download_unzip(self, *args, **kwargs): return self.backend.download_unzip(*args, **kwargs)
    
    def batch_save(self, file_map: Dict[str, Any], max_workers: int = 4, atomic: bool = True) -> List[str]:
        """
        Uploads multiple files in parallel.
        file_map: { 'key1': 'content/bytes1', 'key2': 'content/bytes2' }
        """
        logger.info(f"Batch saving {len(file_map)} files with {max_workers} threads...")
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_key = {
                executor.submit(self.save, key, data, atomic=atomic): key 
                for key, data in file_map.items()
            }
            for future in as_completed(future_to_key):
                key = future_to_key[future]
                try:
                    res = future.result()
                    results.append(res)
                    logger.info(f"Batch save success: {key}")
                except Exception as e:
                    logger.error(f"Batch save failed for {key}: {e}")
                    raise e
        return results

    def batch_download(self, keys: List[str], max_workers: int = 4) -> Dict[str, bytes]:
        """
        Downloads multiple files in parallel.
        Returns dictionary { 'key': bytes }
        """
        logger.info(f"Batch downloading {len(keys)} files with {max_workers} threads...")
        results = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_key = {executor.submit(self.download, key): key for key in keys}
            for future in as_completed(future_to_key):
                key = future_to_key[future]
                try:
                    data = future.result()
                    results[key] = data
                except Exception as e:
                    logger.error(f"Batch download failed for {key}: {e}")
                    raise e
        return results

    @contextmanager
    def lock(self, key: str, timeout: int = 60, poll_interval: float = 1.0):
        lock_key = f"{key}.lock"
        start_time = time.time()
        acquired = False
        while time.time() - start_time < timeout:
            if not self.exists(lock_key):
                try:
                    self.backend.save(lock_key, f"locked_at={datetime.now().isoformat()}")
                    acquired = True
                    break
                except Exception as e:
                    logger.warning(f"Lock race: {e}")
            logger.info(f"Waiting for lock on {key}...")
            time.sleep(poll_interval)
        
        if not acquired:
            raise TimeoutError(f"Could not acquire lock for {key}")
        
        logger.info(f"Lock acquired for {key}")
        try:
            yield
        finally:
            try:
                self.delete(lock_key)
                logger.info(f"Lock released for {key}")
            except Exception as e:
                logger.error(f"Failed to release lock for {key}: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    if len(sys.argv) > 1 and sys.argv[1] == "auth":
        try:
            storage = ObjectStorage()
            print("Authentication successful.")
        except Exception as e:
            print(f"Authentication failed: {e}")
    else:
        print(f"Test run with backend: {os.getenv('STORAGE_BACKEND', 'google_drive')}")
        try:
            storage = ObjectStorage()
            if isinstance(storage.backend, GoogleDriveStorageBackend):
                print(f"User: {storage.backend.get_user_info().get('emailAddress')}")

            # Test Atomic Save
            test_key = "setup/atomic_test.txt"
            print(f"Saving atomic: {test_key}")
            storage.save(test_key, "Critical Data with Verification", atomic=True)
            print("Atomic save success.")

            # Test Lock
            with storage.lock(test_key, timeout=5):
                print("Lock acquired.")
                time.sleep(1)
            print("Lock released.")

            print("--- ALL TESTS PASSED ---")
        except Exception as e:
            print(f"FAILED: {e}")