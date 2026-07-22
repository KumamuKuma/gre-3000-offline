from __future__ import annotations

from scripts.export_web_data import build_payload
from gre_vocab_app.importer.build import build_database
from gre_vocab_app.importer.normalize import WordDraft


def test_web_export_matches_reviewed_database(tmp_path):
    content_db = tmp_path / "words.db"
    build_database(
        [
            WordDraft(
                source_order=1,
                source_section="list1",
                source_page=5,
                headword="abate",
                phonetic="[əˈbeɪt]",
                definition_en="v. become less intense",
                definition_zh="减轻",
                synonyms="subside",
                example_en="The storm began to abate.",
                example_zh="暴风雨开始减弱。",
                raw_definition="v. become less intense 减轻",
                raw_example="The storm began to abate. 暴风雨开始减弱。",
                quality_flags=(),
            )
        ],
        content_db,
    )
    payload = build_payload(content_db)

    assert payload["schema"] == "gre-vocab-content"
    assert payload["version"] == 1
    assert payload["record_count"] == len(payload["words"])
    assert payload["lists"]
    first = payload["words"][0]
    assert first["id"] > 0
    assert first["word"]
    assert isinstance(first["equivalents"], list)
    assert isinstance(first["roots"], list)
    assert isinstance(first["lookalikes"], list)
