from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

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


def _json_cell(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_audit(
    entries: Sequence[WordDraft],
    json_path: Path,
    html_path: Path,
    *,
    source_path: Path | None = None,
    page_count: int = 0,
    approved_source_profile: Mapping[str, Any] | None = None,
    physical_coverage: Mapping[str, Any] | None = None,
    continuity: Mapping[str, Any] | None = None,
    page_range: Mapping[str, Any] | None = None,
    dewrap_counts: Mapping[str, Mapping[str, int]] | None = None,
    override_details: Sequence[Mapping[str, Any]] = (),
    semantic_checks: Sequence[Mapping[str, Any]] = (),
    strict_checks: Sequence[Mapping[str, Any]] = (),
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
    source_sha256 = _source_hash(source_path)
    actual_profile = {
        "sha256": source_sha256,
        "page_count": page_count,
        "record_count": len(ordered),
        "section_counts": section_counts,
    }
    payload = {
        # Retain the original flat values for machine consumers from the first audit schema.
        "source_sha256": source_sha256,
        "page_count": page_count,
        "record_count": len(ordered),
        "source_profile": {
            "approved": dict(approved_source_profile or {}),
            "actual": actual_profile,
        },
        "physical_coverage": dict(physical_coverage or {}),
        "section_counts": section_counts,
        "continuity": dict(continuity or {}),
        "page_range": dict(page_range or {}),
        "dewrap_counts": {
            field: dict(values) for field, values in (dewrap_counts or {}).items()
        },
        "override_details": [dict(item) for item in override_details],
        "semantic_checks": [dict(item) for item in semantic_checks],
        "strict_checks": [dict(item) for item in strict_checks],
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
    source_profile_rows = [
        ("Approved", _json_cell(payload["source_profile"]["approved"])),
        ("Actual", _json_cell(payload["source_profile"]["actual"])),
    ]
    dewrap_rows = [
        (
            field,
            values.get("normal_space", 0),
            values.get("hard_join", 0),
            values.get("hard_join_records", 0),
        )
        for field, values in payload["dewrap_counts"].items()
    ]
    override_rows = [
        (
            item.get("key", ""),
            item.get("source_order", ""),
            ", ".join(item.get("original_issues", [])),
            ", ".join(item.get("changed_fields", [])),
            _json_cell(item.get("before", {})),
            _json_cell(item.get("after", {})),
        )
        for item in payload["override_details"]
    ]
    semantic_rows = [
        (
            item.get("name", ""),
            item.get("pass", False),
            item.get("count", ""),
            _json_cell(item.get("source_orders", [])),
        )
        for item in payload["semantic_checks"]
    ]
    strict_rows = [
        (
            item.get("name", ""),
            item.get("pass", False),
            _json_cell(item.get("expected")),
            _json_cell(item.get("actual")),
        )
        for item in payload["strict_checks"]
    ]
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
            "<h2>Source profile</h2>",
            _table(("Profile", "Values"), source_profile_rows),
            "<h2>Physical coverage</h2>",
            _table(("Metric", "Value"), payload["physical_coverage"].items()),
            "<h2>Sections</h2>",
            _table(("Section", "Records"), section_counts.items()),
            "<h2>Continuity</h2>",
            _table(
                ("Metric", "Value"),
                (
                    (key, _json_cell(value))
                    for key, value in payload["continuity"].items()
                ),
            ),
            "<h2>Source page range</h2>",
            _table(("Metric", "Value"), payload["page_range"].items()),
            "<h2>De-wrap counts</h2>",
            _table(
                ("Field", "Normal space", "Hard join", "Hard-join records"),
                dewrap_rows,
            ),
            "<h2>Override details</h2>",
            _table(
                ("Key", "Order", "Original issues", "Changed fields", "Before", "After"),
                override_rows,
            ),
            "<h2>Semantic checks</h2>",
            _table(("Check", "Pass", "Count", "Source orders"), semantic_rows),
            "<h2>Strict checks</h2>",
            _table(("Check", "Pass", "Expected", "Actual"), strict_rows),
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
