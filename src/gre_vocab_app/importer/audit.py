from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Iterable, Sequence

from .normalize import WordDraft


@dataclass(frozen=True, slots=True)
class AuditSummary:
    record_count: int
    unresolved_count: int
    reviewed_count: int


def _source_hash(path: Path | None) -> str:
    if path is None:
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record(entry: WordDraft) -> dict[str, object]:
    return {
        "source_order": entry.source_order,
        "source_page": entry.source_page,
        "source_section": entry.source_section,
        "headword": entry.headword,
        "definition_en": entry.definition_en,
        "quality_flags": list(entry.quality_flags),
    }


def _duplicates(entries: Sequence[WordDraft]) -> list[dict[str, object]]:
    grouped: dict[str, list[WordDraft]] = defaultdict(list)
    for entry in entries:
        grouped[entry.headword.casefold()].append(entry)
    result = []
    for group in grouped.values():
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda item: item.source_order)
        result.append(
            {
                "headword": ordered[0].headword,
                "source_orders": [item.source_order for item in ordered],
            }
        )
    return sorted(result, key=lambda item: str(item["headword"]).casefold())


def _table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    header_cells = "".join(f"<th>{escape(value, quote=True)}</th>" for value in headers)
    body = []
    for row in rows:
        body.append(
            "<tr>"
            + "".join(
                f"<td>{escape(str(value), quote=True)}</td>" for value in row
            )
            + "</tr>"
        )
    if not body:
        body.append(f'<tr><td colspan="{len(headers)}">None</td></tr>')
    return f"<table><thead><tr>{header_cells}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def _record_rows(records: Sequence[dict[str, object]]) -> list[tuple[object, ...]]:
    return [
        (
            item["source_order"],
            item["source_page"],
            item["source_section"],
            item["headword"],
            item["definition_en"],
            ", ".join(str(flag) for flag in item["quality_flags"]),
        )
        for item in records
    ]


def write_audit(
    entries: Sequence[WordDraft],
    json_path: Path,
    html_path: Path,
    *,
    source_path: Path | None = None,
    page_count: int = 0,
) -> AuditSummary:
    ordered = sorted(entries, key=lambda item: item.source_order)
    unresolved = [
        _record(entry)
        for entry in ordered
        if any(not flag.startswith("reviewed:") for flag in entry.quality_flags)
    ]
    reviewed = [
        _record(entry)
        for entry in ordered
        if any(flag.startswith("reviewed:") for flag in entry.quality_flags)
    ]
    section_counts = dict(
        sorted(Counter(entry.source_section for entry in ordered).items())
    )
    duplicates = _duplicates(ordered)
    payload = {
        "source_sha256": _source_hash(source_path),
        "page_count": page_count,
        "record_count": len(ordered),
        "section_counts": section_counts,
        "unresolved_records": unresolved,
        "reviewed_records": reviewed,
        "duplicate_headwords": duplicates,
    }

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary_rows = [
        ("Source SHA-256", payload["source_sha256"]),
        ("Page count", page_count),
        ("Record count", len(ordered)),
        ("Unresolved", len(unresolved)),
        ("Reviewed", len(reviewed)),
        ("Duplicate headwords", len(duplicates)),
    ]
    record_headers = (
        "Order",
        "Page",
        "Section",
        "Headword",
        "Definition",
        "Flags",
    )
    html = "".join(
        [
            "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
            "<title>Vocabulary import audit</title>",
            "<style>body{font:14px system-ui;margin:24px;color:#17202a}",
            "table{border-collapse:collapse;width:100%;margin:8px 0 22px}",
            "th,td{border:1px solid #d7dde5;padding:6px 8px;text-align:left;vertical-align:top}",
            "th{background:#f2f5f8}h1,h2{margin-bottom:8px}</style></head><body>",
            "<h1>Vocabulary import audit</h1><h2>Summary</h2>",
            _table(("Metric", "Value"), summary_rows),
            "<h2>Sections</h2>",
            _table(("Section", "Records"), section_counts.items()),
            "<h2>Unresolved records</h2>",
            _table(record_headers, _record_rows(unresolved)),
            "<h2>Reviewed records</h2>",
            _table(record_headers, _record_rows(reviewed)),
            "<h2>Duplicate headwords</h2>",
            _table(
                ("Headword", "Source orders"),
                (
                    (item["headword"], ", ".join(map(str, item["source_orders"])))
                    for item in duplicates
                ),
            ),
            "</body></html>\n",
        ]
    )
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    return AuditSummary(len(ordered), len(unresolved), len(reviewed))

