from __future__ import annotations

import argparse
import json
from pathlib import Path

from gre_vocab_app.db.content import ContentRepository


def build_payload(database: Path) -> dict[str, object]:
    with ContentRepository(database) as content:
        lists = [
            {
                "key": item.key,
                "label": item.label,
                "count": item.word_count,
                "first": item.first_order,
                "last": item.last_order,
            }
            for item in content.source_lists()
        ]
        words = []
        for word_id in content.ids_in_source_order():
            entry = content.get(word_id)
            words.append(
                {
                    "id": entry.id,
                    "order": entry.source_order,
                    "list": entry.source_section,
                    "word": entry.headword,
                    "phonetic": entry.phonetic,
                    "definition_en": entry.definition_en,
                    "definition_zh": entry.definition_zh,
                    "synonyms": entry.synonyms,
                    "example_en": entry.example_en,
                    "example_zh": entry.example_zh,
                    "machine7": content.in_machine7(entry.id),
                    "equivalents": [
                        related.word_id for related in content.equivalents(entry.id)
                    ],
                    "roots": [
                        {
                            "root": family.root,
                            "words": [related.word_id for related in family.words],
                        }
                        for family in content.root_families(entry.id)
                    ],
                    "lookalikes": [
                        related.word_id for related in content.lookalikes(entry.id)
                    ],
                }
            )
    return {
        "schema": "gre-vocab-content",
        "version": 1,
        "record_count": len(words),
        "lists": lists,
        "words": words,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the reviewed web word set")
    parser.add_argument("database", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = build_payload(args.database)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Exported {payload['record_count']} words to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
