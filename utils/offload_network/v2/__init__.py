"""v2 offload orchestration — sealed self-contained bundles.

Phase 1 + Phase 4 implementation. Every job ships as a single sealed
archive (tar.zst preferred, tar.gz fallback) containing code + data +
manifest + bootstrap. Results pulled back automatically as a single
tar archive when the run exits.

Public entry points:
  - manifest.SealedManifest      — job description
  - seal.build_seal              — produce sealed archive from manifest
  - seal.verify_seal             — verify integrity of a sealed archive
  - transport.push_seal          — single-file rsync push to remote
  - transport.pull_result        — single-file rsync pull from remote
  - submit.submit_one            — full lifecycle of one job
  - submit.submit_many           — orchestrate many jobs
"""

from .manifest import (
    SealedManifest, SealedBlob, ResultSpec,
    SealError,
)
from .seal import build_seal, verify_seal, extract_seal

__all__ = [
    "SealedManifest", "SealedBlob", "ResultSpec",
    "SealError",
    "build_seal", "verify_seal", "extract_seal",
]
