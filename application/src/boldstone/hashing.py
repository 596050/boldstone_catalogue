"""Dropbox content-hash reference helper, independent of the Dropbox SDK.

Source algorithm: https://www.dropbox.com/developers/reference/content-hash
A regular file SHA-256 is a different checksum and should be recorded separately.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO

BLOCK_SIZE = 4 * 1024 * 1024


def dropbox_content_hash(stream: BinaryIO) -> str:
    """Hash a binary stream correctly even when read() returns partial blocks."""
    outer = hashlib.sha256()
    block = bytearray()
    while True:
        part = stream.read(BLOCK_SIZE - len(block))
        if not part:
            if block:
                outer.update(hashlib.sha256(block).digest())
            break
        block.extend(part)
        if len(block) == BLOCK_SIZE:
            outer.update(hashlib.sha256(block).digest())
            block.clear()
    return outer.hexdigest()


def hash_file(path: str | Path) -> str:
    with Path(path).open("rb") as stream:
        return dropbox_content_hash(stream)
