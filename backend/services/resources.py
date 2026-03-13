from __future__ import annotations

import json
from pathlib import Path


class ResourceStore:
    def __init__(self) -> None:
        base_dir = Path(__file__).resolve().parents[2]
        self._data_path = base_dir / "data" / "resources_india.json"
        self._resources = self._load()

    def _load(self) -> list[dict[str, object]]:
        with self._data_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def search(
        self,
        query: str | None = None,
        mode: str | None = None,
        language: str | None = None,
    ) -> list[dict[str, object]]:
        query_text = (query or "").strip().lower()
        mode_text = (mode or "").strip().lower()
        language_text = (language or "").strip().lower()

        results = []
        for item in self._resources:
            searchable_blob = " ".join(
                [
                    str(item.get("name", "")),
                    str(item.get("notes", "")),
                    str(item.get("coverage", "")),
                    " ".join(item.get("tags", [])),
                ]
            ).lower()

            if query_text and query_text not in searchable_blob:
                continue
            if mode_text and mode_text not in str(item.get("mode", "")).lower():
                continue
            if language_text and language_text not in str(item.get("language", "")).lower():
                continue

            results.append(item)

        return results
