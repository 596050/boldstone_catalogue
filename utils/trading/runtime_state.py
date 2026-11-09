import json
import logging
import os
import tempfile
import time
from typing import Any, Dict


logger = logging.getLogger(__name__)


class RuntimeStateStore:
    SCHEMA_VERSION = 1

    def __init__(self, path: str = ".runtime/market_maker_state.json"):
        self.path = path

    def load(self) -> Dict[str, Any]:
        if not os.path.exists(self.path):
            return {"version": self.SCHEMA_VERSION, "written_at": 0.0, "symbols": {}}

        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception as exc:
            logger.error("Failed to load runtime state from %s: %s", self.path, exc)
            return {"version": self.SCHEMA_VERSION, "written_at": 0.0, "symbols": {}}

        if payload.get("version") != self.SCHEMA_VERSION:
            logger.warning(
                "Ignoring runtime state with unsupported schema version %s at %s",
                payload.get("version"),
                self.path,
            )
            return {"version": self.SCHEMA_VERSION, "written_at": 0.0, "symbols": {}}

        payload.setdefault("symbols", {})
        payload.setdefault("written_at", 0.0)
        return payload

    def load_symbol_states(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.load().get("symbols", {}))

    def save_symbol_states(self, symbol_states: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        payload = {
            "version": self.SCHEMA_VERSION,
            "written_at": time.time(),
            "symbols": symbol_states,
        }
        self._atomic_write(payload)
        return payload

    def _atomic_write(self, payload: Dict[str, Any]):
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)

        fd, temp_path = tempfile.mkstemp(
            prefix=".market_maker_state.",
            suffix=".tmp",
            dir=directory,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
