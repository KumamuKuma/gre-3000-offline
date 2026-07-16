from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from dataclasses import fields, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import fitz

from gre_vocab_app.db.schema import CONTENT_SCHEMA, CONTENT_SCHEMA_VERSION

from .audit import write_audit
from .layout import (
    extract_page_row_boundaries,
    extract_page_spans,
    group_spans_into_rows,
)
from .normalize import WordDraft, normalize_row
from .types import ParserState


def apply_overrides(
    entries: Sequence[WordDraft], overrides: Mapping[str, Mapping[str, Any]]
) -> list[WordDraft]:
    allowed = {field.name for field in fields(WordDraft)}
    result: list[WordDraft] = []
    for entry in entries:
        values = dict(overrides.get(f"{entry.source_page}:{entry.headword}", {}))
        reviewed = bool(values.pop("reviewed", False))
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"unknown override fields: {', '.join(sorted(unknown))}")
        if "quality_flags" in values:
            values["quality_flags"] = tuple(values["quality_flags"])
        updated = replace(entry, **values) if values else entry
        if reviewed:
            flags = tuple(
                flag if flag.startswith("reviewed:") else f"reviewed:{flag}"
                for flag in updated.quality_flags
            )
            updated = replace(updated, quality_flags=flags)
        result.append(updated)
    return result


def _validate(entries: Sequence[WordDraft]) -> None:
    orders: set[int] = set()
    for entry in entries:
        if entry.source_order in orders:
            raise ValueError(f"duplicate source_order: {entry.source_order}")
        orders.add(entry.source_order)
        if not entry.headword.strip():
            raise ValueError(f"blank headword at source_order {entry.source_order}")


def build_database(entries: Sequence[WordDraft], output_path: Path) -> None:
    ordered = sorted(entries, key=lambda item: item.source_order)
    _validate(ordered)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        dir=output_path.parent,
        delete=False,
    )
    temporary = Path(handle.name)
    handle.close()
    try:
        database = sqlite3.connect(temporary)
        try:
            database.executescript(CONTENT_SCHEMA)
            database.executemany(
                "insert into metadata(key, value) values(?, ?)",
                (
                    ("schema_version", str(CONTENT_SCHEMA_VERSION)),
                    ("record_count", str(len(ordered))),
                ),
            )
            database.executemany(
                """
                insert into words(
                  source_order, source_section, source_page, headword, phonetic,
                  definition_en, definition_zh, synonyms, example_en, example_zh,
                  raw_definition, raw_example, quality_flags
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (
                        entry.source_order,
                        entry.source_section,
                        entry.source_page,
                        entry.headword,
                        entry.phonetic,
                        entry.definition_en,
                        entry.definition_zh,
                        entry.synonyms,
                        entry.example_en,
                        entry.example_zh,
                        entry.raw_definition,
                        entry.raw_example,
                        json.dumps(
                            list(entry.quality_flags),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    )
                    for entry in ordered
                ),
            )
            check = database.execute("pragma integrity_check").fetchone()
            if check is None or check[0] != "ok":
                raise sqlite3.IntegrityError(
                    f"content database integrity check failed: {check}"
                )
            database.commit()
        finally:
            database.close()
        os.replace(temporary, output_path)
    finally:
        temporary.unlink(missing_ok=True)


def _extract(pdf_path: Path) -> tuple[list[WordDraft], int]:
    entries: list[WordDraft] = []
    state = ParserState(next_order=1, section="unknown")
    with fitz.open(pdf_path) as document:
        if document.needs_pass:
            raise ValueError("encrypted PDF requires a password")
        page_count = len(document)
        for page_index in range(4, page_count):
            page = document[page_index]
            rows, state = group_spans_into_rows(
                extract_page_spans(page),
                page_number=page_index + 1,
                state=state,
                row_boundaries=extract_page_row_boundaries(page),
            )
            entries.extend(normalize_row(row) for row in rows)
    return entries, page_count


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the offline GRE word database")
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--audit-json", required=True, type=Path)
    parser.add_argument("--audit-html", required=True, type=Path)
    parser.add_argument("--overrides", required=True, type=Path)
    parser.add_argument("--strict", action="store_true")
    return parser


def _run(args: argparse.Namespace) -> int:
    entries, page_count = _extract(args.pdf)
    overrides = json.loads(args.overrides.read_text(encoding="utf-8"))
    if not isinstance(overrides, dict):
        raise ValueError("overrides must be a JSON object")
    entries = apply_overrides(entries, overrides)
    build_database(entries, args.output)
    summary = write_audit(
        entries,
        args.audit_json,
        args.audit_html,
        source_path=args.pdf,
        page_count=page_count,
    )
    print(
        f"records={summary.record_count} unresolved={summary.unresolved_count} "
        f"reviewed={summary.reviewed_count}"
    )
    return 2 if args.strict and summary.unresolved_count else 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return _run(args)
    except (OSError, RuntimeError, ValueError, sqlite3.DatabaseError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
