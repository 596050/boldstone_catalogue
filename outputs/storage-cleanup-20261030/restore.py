"""Restore one archived historical database to its original path, without overwriting."""
from pathlib import Path
import argparse
import json
import os
import uuid
import cleanup
import storage_primitives as native

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('original_path',help='Original database path, absolute or relative to Boldstone')
parser.add_argument('--apply',action='store_true')
args=parser.parse_args()
p=Path(args.original_path)
if not p.is_absolute():p=cleanup.ROOT/p
if p.resolve()!=p or not p.is_relative_to(cleanup.ROOT):parser.error('Path must be inside the Boldstone directory, without symlinks')
archive=Path(str(p)+'.gz');receipt=Path(str(archive)+'.restore.json')
info=json.loads(receipt.read_text())
assert info['original_path']==str(p) and info['archive_path']==str(archive)
assert native.digest(archive)==info['archive_sha256']
if p.exists():parser.error('Original path exists; nothing overwritten')
if not args.apply:
    print(json.dumps({'status':'PREVIEW_ONLY','archive':str(archive),'restore_to':str(p),'bytes':info['bytes'],'instruction':'Add --apply to restore this historical database.'},indent=2))
else:
    temporary=p.parent/('.boldstone-restore-'+uuid.uuid4().hex)
    try:
        cleanup.restore_to(archive,temporary,info)
        # Atomic exclusive installation: refuse a path created by another writer.
        native.native(native.LIB.renamex_np,os.fsencode(temporary),os.fsencode(p),4)
        assert native.digest(p)==info['sha256'] and native.metadata(p)==info['metadata']
        print(json.dumps({'status':'RESTORED_AND_BYTE_VERIFIED','path':str(p),'sha256':info['sha256'],'archive_retained':str(archive)},indent=2))
    finally:
        if temporary.exists():temporary.unlink()
