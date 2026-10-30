from __future__ import annotations

import re
from pathlib import PurePosixPath

from .util import parent_path


def historical_relative_path(path):
    marker = "/01 Wall Sculptures/"
    return path.split(marker, 1)[1] if path and marker in path else None


def assess_name(metadata, row, scope_path, *, held=False, duplicate_target=False):
    name = metadata["name"]
    current_relative = metadata["path_lower"][len(scope_path) :].lstrip("/")
    old_path = row.get("Earlier detailed path") or row.get("Last detailed path (earlier evidence)")
    historical = historical_relative_path(old_path)
    result = {
        "current_name": name,
        "proposed_name": None,
        "proposal_is_approved": False,
        "historical_path": old_path,
        "format_verified": False,
        "generated_provenance_decision": "not_inferred_from_filename",
    }
    if held:
        return {**result, "outcome": "HELD_EXISTING_RESTRICTION"}
    if duplicate_target:
        return {**result, "outcome": "HELD_PENDING_DUPLICATE_DISPOSITION"}
    if not historical:
        return {**result, "outcome": "NAME_REVIEW_REQUIRED_NO_EXACT_HISTORICAL_REFERENCE"}
    previous_name = PurePosixPath(historical).name
    if parent_path(historical).lower() != parent_path(current_relative):
        return {**result, "outcome": "HELD_STALE_HISTORICAL_PARENT"}
    if name == previous_name:
        if re.search(r"chatgpt|gemini|(?:^|__)hf_", name, re.IGNORECASE):
            return {**result, "outcome": "NAME_REVIEW_REQUIRED_DISALLOWED_HISTORICAL_NAME"}
        return {**result, "outcome": "REVIEWED_NO_CHANGE_HISTORICAL_NAME_MATCH"}
    if name.casefold() == previous_name.casefold():
        return {**result, "outcome": "HELD_CASE_ONLY_RENAME"}
    if PurePosixPath(name).suffix.lower() != PurePosixPath(previous_name).suffix.lower():
        return {**result, "outcome": "HELD_EXTENSION_CHANGED"}
    if re.search(r"(?:^|__)asset-[a-z0-9]+", name):
        return {**result, "outcome": "HELD_PRESERVE_ESTABLISHED_ASSET_SUFFIX"}
    if re.search(r"chatgpt|gemini|(?:^|__)hf_", previous_name, re.IGNORECASE):
        return {**result, "outcome": "NAME_REVIEW_REQUIRED_HISTORICAL_NAME_DISALLOWED"}
    return {
        **result,
        "outcome": "REVIEWED_HISTORICAL_NAME_PROPOSAL",
        "proposed_name": previous_name,
        "proposal_basis": "exact_ID_dated_observed_name; requires separate approval",
    }
