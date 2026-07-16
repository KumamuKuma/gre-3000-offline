from __future__ import annotations

from typing import Any

from gre_vocab_app.domain import WordEntry


class SearchService:
    def __init__(self, content_repository: Any):
        self._content = content_repository

    def search(self, query: str) -> list[WordEntry]:
        value = query.strip()
        if not value:
            return []
        return list(self._content.search(value, limit=50))[:50]

