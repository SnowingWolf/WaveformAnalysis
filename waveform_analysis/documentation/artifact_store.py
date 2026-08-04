"""Atomic JSON persistence for documentation DAG state and artifacts."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
from typing import Any


class FileArtifactStore:
    """Stores each workflow state below one caller-provided directory."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def load_state(self, workflow_id: str) -> dict[str, Any] | None:
        path = self._state_path(workflow_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save_state(self, workflow_id: str, state: dict[str, Any]) -> Path:
        return self._write_json(self._state_path(workflow_id), state)

    def save_artifact(self, workflow_id: str, name: str, artifact: dict[str, Any]) -> Path:
        return self._write_json(self.root / workflow_id / "artifacts" / f"{name}.json", artifact)

    def load_artifact(self, workflow_id: str, name: str) -> dict[str, Any] | None:
        path = self.root / workflow_id / "artifacts" / f"{name}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _state_path(self, workflow_id: str) -> Path:
        return self.root / workflow_id / "state.json"

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            temporary_path = Path(handle.name)
        temporary_path.replace(path)
        return path
