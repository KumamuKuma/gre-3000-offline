from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import fitz

from gre_vocab_app.db.content import ContentDatabaseError, ContentRepository
from gre_vocab_app.db.schema import CONTENT_SCHEMA, CONTENT_SCHEMA_VERSION

from .audit import (
    AuditSummary,
    build_audit_payload,
    render_audit_html,
    write_audit,
)
from .layout import (
    PhysicalRowCoverage,
    extract_page_spans,
    extract_page_word_row_bands,
    group_spans_into_rows,
    validate_physical_row_coverage,
)
from .normalize import (
    CJK,
    VALIDATION_FLAGS,
    WordDraft,
    normalize_row_with_diagnostics,
    validation_flags,
)
from .publication import (
    ArtifactSlot,
    cleanup_artifact_slots,
    plan_artifact_publication,
    publish_artifact_slots,
)
from .types import ParserState


APPROVED_SOURCE_PROFILE: dict[str, Any] = {
    "sha256": "8270d259f3457711a16c9f7a7d79f2d95f89fa83228a1b89e656546882f303a0",
    "overrides_sha256": "47fa8c54daa5fa7acc36a9ec50280d952c87ec2a4238ae6fc76fb7f3053d2d8e",
    "page_count": 288,
    "physical_row_bands": 3292,
    "record_count": 3292,
    "override_count": 203,
    "reviewed_count": 203,
    "first_source_order": 1,
    "last_source_order": 3292,
    "first_source_page": 5,
    "last_source_page": 288,
    "section_counts": {
        **{f"list{number}": 105 for number in range(1, 30)},
        "list30": 44,
        "supplement-1": 102,
        "supplement-2": 101,
    },
    "dewrap_counts": {
        "definition": {
            "normal_space": 3993,
            "hard_join": 0,
            "hard_join_records": 0,
        },
        "example": {
            "normal_space": 3416,
            "hard_join": 241,
            "hard_join_records": 212,
        },
        "synonyms": {
            "normal_space": 2,
            "hard_join": 255,
            "hard_join_records": 237,
        },
    },
    "reference_sources": {
        "equivalence": {
            "configured": True,
            "sha256": "c6f3c2326963319aa4281496295fc6d92569dfdf8b36da833bdd1bed70efaefd",
            "page_count": 32,
            "row_count": 940,
            "unique_headword_count": 930,
            "equivalent_mention_count": 1285,
            "matched_headword_rows": 864,
            "matched_equivalent_mentions": 931,
            "edge_count": 547,
            "unmatched_headword_count": 76,
            "unmatched_equivalent_count": 354,
        },
        "machine7": {
            "configured": True,
            "sha256": "2841887fc8fb9a65b39c10ae3b3a19fdd9b0d514c4e6de0520f0c5a9f85e5c65",
            "page_count": 157,
            "headword_count": 1450,
            "unique_headword_count": 1450,
            "matched_count": 1410,
            "unmatched_headword_count": 40,
        },
    },
}

CONTENT_OVERRIDE_FIELDS = (
    "headword",
    "phonetic",
    "definition_en",
    "definition_zh",
    "synonyms",
    "example_en",
    "example_zh",
)
from .reference_sources import (
    EquivalenceEdge,
    Machine7Membership,
    ReferenceData,
    load_reference_data,
)
CURATED_OVERRIDE_FIELDS = frozenset(
    {
        "source_order",
        "kinds",
        "reason",
        "evidence",
        "expected_before",
        "changes",
        "reviewed",
    }
)
CORRECTION_KIND_FIELDS: dict[str, frozenset[str]] = {
    "phonetic": frozenset({"phonetic"}),
    "definition": frozenset({"definition_en", "definition_zh"}),
    "part_of_speech": frozenset({"definition_en", "definition_zh"}),
    "example": frozenset({"example_en", "example_zh"}),
    "content_completion": frozenset(
        {"definition_en", "definition_zh", "example_en", "example_zh"}
    ),
}
NONEMPTY_CONTENT_FIELDS = frozenset(
    {"definition_en", "definition_zh", "example_en", "example_zh"}
)
FORBIDDEN_OVERRIDE_FIELDS = frozenset(
    {
        "source_order",
        "source_page",
        "source_section",
        "raw_definition",
        "raw_example",
        "quality_flags",
    }
)
OVERRIDE_KEY = re.compile(r"^[1-9]\d*:.+\S$")
ENGLISH_POS_IN_CHINESE = re.compile(
    r"(?<![A-Za-z])(?:adj|adv|n|v|vt|vi|pron|prep|conj|det|aux|"
    r"interj|int|num|art|modal|phrase)\.",
    re.IGNORECASE,
)
LATIN_RUN_IN_CHINESE = re.compile(
    r"(?<![A-Za-z])"
    r"[A-Za-z]+(?:['-][A-Za-z]+)*"
    r"(?:[ \t]+[A-Za-z]+(?:['-][A-Za-z]+)*)*"
    r"(?![A-Za-z])"
)
LATIN_WORD = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")


@dataclass(frozen=True, slots=True)
class RecordDewrapEvent:
    source_order: int
    field: str
    kind: str
    left: str
    right: str


@dataclass(frozen=True, slots=True)
class ExtractionDiagnostics:
    dewrap_counts: dict[str, dict[str, int]]
    dewrap_events: tuple[RecordDewrapEvent, ...]


def _source_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_overrides_with_hash(
    path: Path,
) -> tuple[dict[str, Mapping[str, Any]], str]:
    payload = path.read_bytes()
    parsed = json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=_duplicate_rejecting_object,
    )
    if not isinstance(parsed, dict):
        raise ValueError("overrides must be a JSON object")
    return parsed, hashlib.sha256(payload).hexdigest()


def load_overrides(path: Path) -> dict[str, Mapping[str, Any]]:
    return _load_overrides_with_hash(path)[0]


def _original_issues(entry: WordDraft) -> tuple[str, ...]:
    result: list[str] = []
    for flag in entry.quality_flags:
        issue = (
            flag.removeprefix("reviewed:")
            if flag.startswith("reviewed:")
            else flag
        )
        if issue not in result:
            result.append(issue)
    return tuple(result)


def _content_snapshot(entry: WordDraft) -> dict[str, str]:
    return {field: getattr(entry, field) for field in CONTENT_OVERRIDE_FIELDS}


def _issue_fields(issue: str) -> frozenset[str]:
    return {
        "missing_headword": frozenset({"headword"}),
        "missing_phonetic": frozenset({"phonetic"}),
        "invalid_phonetic": frozenset({"phonetic"}),
        "incomplete_definition": frozenset({"definition_en", "definition_zh"}),
        "incomplete_example": frozenset({"example_en", "example_zh"}),
        "definition_en_contains_cjk": frozenset({"definition_en"}),
        "example_en_contains_cjk": frozenset({"example_en"}),
    }.get(issue, frozenset())


def _curated_override(
    key: str,
    original: WordDraft,
    raw_values: Mapping[str, Any],
) -> tuple[WordDraft, dict[str, Any]]:
    unknown = set(raw_values) - CURATED_OVERRIDE_FIELDS
    if unknown:
        raise ValueError(
            "unknown curated override field: " + ", ".join(sorted(unknown))
        )
    if raw_values.get("reviewed") is not True:
        raise ValueError(f"override {key!r} must set reviewed to true")

    source_order = raw_values.get("source_order")
    if source_order is None:
        raise ValueError(f"override {key!r} must declare source_order")
    if not isinstance(source_order, int) or isinstance(source_order, bool):
        raise ValueError(f"override {key!r} source_order must be an integer")
    if source_order != original.source_order:
        raise ValueError(
            f"override {key!r} source_order mismatch: "
            f"expected {original.source_order}, got {source_order}"
        )

    kinds = raw_values.get("kinds")
    if (
        not isinstance(kinds, list)
        or not kinds
        or any(not isinstance(kind, str) or not kind.strip() for kind in kinds)
    ):
        raise ValueError(f"override {key!r} must declare correction kinds")
    if len(kinds) != len(set(kinds)):
        raise ValueError(f"override {key!r} has duplicate correction kinds")
    unknown_kinds = sorted(set(kinds) - set(CORRECTION_KIND_FIELDS))
    if unknown_kinds:
        raise ValueError(
            f"override {key!r} has unknown correction kind: "
            + ", ".join(unknown_kinds)
        )

    reason = raw_values.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError(f"override {key!r} must include a reason")
    evidence = raw_values.get("evidence")
    if (
        not isinstance(evidence, list)
        or not evidence
        or any(not isinstance(item, str) or not item.strip() for item in evidence)
    ):
        raise ValueError(f"override {key!r} must include evidence")
    if len(evidence) != len(set(evidence)):
        raise ValueError(f"override {key!r} has duplicate evidence")

    expected_before = raw_values.get("expected_before")
    if not isinstance(expected_before, Mapping):
        raise ValueError(f"override {key!r} must include expected_before")
    changes = raw_values.get("changes")
    if not isinstance(changes, Mapping) or not changes:
        raise ValueError(f"override {key!r} must include changes")
    expected_before = dict(expected_before)
    changes = dict(changes)
    if set(expected_before) != set(changes):
        raise ValueError(
            f"override {key!r} expected_before must cover exactly the changed fields"
        )
    forbidden = set(changes) & FORBIDDEN_OVERRIDE_FIELDS
    if forbidden:
        raise ValueError(
            "forbidden override field: " + ", ".join(sorted(forbidden))
        )
    unknown_changes = set(changes) - set(CONTENT_OVERRIDE_FIELDS)
    if unknown_changes:
        raise ValueError(
            "unknown override field: " + ", ".join(sorted(unknown_changes))
        )
    if any(
        not isinstance(value, str)
        for value in (*expected_before.values(), *changes.values())
    ):
        raise ValueError(f"override {key!r} content values must be strings")
    blank_changed_fields = sorted(
        field
        for field, value in changes.items()
        if field in NONEMPTY_CONTENT_FIELDS and not value.strip()
    )
    if blank_changed_fields:
        raise ValueError(
            f"override {key!r} has blank changed content: "
            + ", ".join(blank_changed_fields)
        )

    stale_fields = sorted(
        field
        for field, expected in expected_before.items()
        if getattr(original, field) != expected
    )
    if stale_fields:
        raise ValueError(
            f"override {key!r} expected_before mismatch: "
            + ", ".join(stale_fields)
        )
    changed_fields = sorted(
        field for field, value in changes.items() if getattr(original, field) != value
    )
    if set(changed_fields) != set(changes):
        raise ValueError(f"stale override {key!r} changes no content")
    completion_fields = {
        field
        for field in changed_fields
        if field in CORRECTION_KIND_FIELDS["content_completion"]
        and not getattr(original, field).strip()
        and changes[field].strip()
    }
    effective_kind_fields = {
        kind: (
            frozenset(completion_fields)
            if kind == "content_completion"
            else CORRECTION_KIND_FIELDS[kind]
        )
        for kind in kinds
    }
    allowed_changed_fields = frozenset().union(*effective_kind_fields.values())
    unauthorized_changed_fields = sorted(
        set(changed_fields) - allowed_changed_fields
    )
    if unauthorized_changed_fields:
        label = "field" if len(unauthorized_changed_fields) == 1 else "fields"
        raise ValueError(
            f"override {key!r} has unauthorized changed {label}: "
            + ", ".join(unauthorized_changed_fields)
        )
    unused_kinds = sorted(
        kind
        for kind in kinds
        if not set(changed_fields) & effective_kind_fields[kind]
    )
    if unused_kinds:
        raise ValueError(
            f"override {key!r} has correction kinds without changes: "
            + ", ".join(unused_kinds)
        )

    original_issues = _original_issues(original)
    extra_flags = [
        issue for issue in original_issues if issue not in VALIDATION_FLAGS
    ]
    updated = replace(original, **changes, quality_flags=())
    if bool(updated.example_en.strip()) != bool(updated.example_zh.strip()):
        raise ValueError(
            f"override {key!r} must keep English and Chinese examples paired"
        )
    detected = validation_flags(updated, extra_flags=extra_flags)
    new_issues = sorted(set(detected) - set(original_issues))
    invalid_changed_fields = sorted(
        {
            field
            for issue in detected
            for field in _issue_fields(issue)
            if field in changed_fields
        }
    )
    if new_issues or invalid_changed_fields:
        problems = new_issues or invalid_changed_fields
        raise ValueError(
            f"override {key!r} is invalid after override: {', '.join(problems)}"
        )
    remaining_issues = [issue for issue in detected if issue in original_issues]
    resolved_issues = [
        issue for issue in original_issues if issue not in remaining_issues
    ]
    reviewed_flags = list(remaining_issues)
    reviewed_flags.extend(f"reviewed:{issue}" for issue in resolved_issues)
    reviewed_flags.extend(f"reviewed:curated_{kind}" for kind in kinds)
    updated = replace(updated, quality_flags=tuple(dict.fromkeys(reviewed_flags)))
    detail = {
        "key": key,
        "source_order": original.source_order,
        "source_page": original.source_page,
        "source_section": original.source_section,
        "headword": original.headword,
        "reviewed": not remaining_issues,
        "kinds": list(kinds),
        "reason": reason.strip(),
        "evidence": list(evidence),
        "expected_before": expected_before,
        "original_issues": list(original_issues),
        "resolved_original_issues": resolved_issues,
        "remaining_original_issues": remaining_issues,
        "changed_fields": changed_fields,
        "before": _content_snapshot(original),
        "after": _content_snapshot(updated),
    }
    return updated, detail


def apply_overrides_with_audit(
    entries: Sequence[WordDraft], overrides: Mapping[str, Mapping[str, Any]]
) -> tuple[list[WordDraft], list[dict[str, Any]]]:
    matches: dict[str, list[int]] = defaultdict(list)
    for index, entry in enumerate(entries):
        matches[f"{entry.source_page}:{entry.headword}"].append(index)

    result = list(entries)
    details: list[dict[str, Any]] = []
    for key, raw_values in overrides.items():
        if not isinstance(key, str) or OVERRIDE_KEY.fullmatch(key) is None:
            raise ValueError(f"malformed override key: {key!r}")
        matched = matches.get(key, [])
        if len(matched) != 1:
            raise ValueError(f"override {key!r} matched {len(matched)} rows")
        if not isinstance(raw_values, Mapping):
            raise ValueError(f"override {key!r} must be a JSON object")

        index = matched[0]
        original = result[index]
        curated_markers = {
            "kinds",
            "reason",
            "evidence",
            "expected_before",
            "changes",
        }
        if set(raw_values) & curated_markers:
            updated, detail = _curated_override(key, original, raw_values)
            result[index] = updated
            details.append(detail)
            continue

        values = dict(raw_values)
        forbidden = set(values) & FORBIDDEN_OVERRIDE_FIELDS
        if forbidden:
            raise ValueError(
                "forbidden override field: " + ", ".join(sorted(forbidden))
            )
        unknown = set(values) - set(CONTENT_OVERRIDE_FIELDS) - {"reviewed"}
        if unknown:
            raise ValueError(
                "unknown override field: " + ", ".join(sorted(unknown))
            )
        if values.pop("reviewed", None) is not True:
            raise ValueError(f"override {key!r} must set reviewed to true")
        if any(not isinstance(value, str) for value in values.values()):
            raise ValueError(f"override {key!r} content values must be strings")

        original_issues = _original_issues(original)
        if not original_issues:
            raise ValueError(f"override {key!r} has no original issue to review")
        changed_fields = sorted(
            field for field, value in values.items() if getattr(original, field) != value
        )
        allowed_changed_fields = frozenset().union(
            *(_issue_fields(issue) for issue in original_issues)
        )
        unauthorized_changed_fields = sorted(
            set(changed_fields) - allowed_changed_fields
        )
        if unauthorized_changed_fields:
            label = (
                "field"
                if len(unauthorized_changed_fields) == 1
                else "fields"
            )
            raise ValueError(
                f"override {key!r} has unauthorized changed {label}: "
                + ", ".join(unauthorized_changed_fields)
            )
        if values and not changed_fields:
            raise ValueError(f"stale override {key!r} changes no content")

        extra_flags = [
            issue for issue in original_issues if issue not in VALIDATION_FLAGS
        ]
        updated = replace(original, **values, quality_flags=())
        detected = validation_flags(updated, extra_flags=extra_flags)
        new_issues = sorted(set(detected) - set(original_issues))
        invalid_changed_fields = sorted(
            {
                field
                for issue in detected
                for field in _issue_fields(issue)
                if field in changed_fields
            }
        )
        if new_issues or invalid_changed_fields:
            problems = new_issues or invalid_changed_fields
            raise ValueError(
                f"override {key!r} is invalid after override: {', '.join(problems)}"
            )
        updated = replace(
            updated,
            quality_flags=tuple(
                f"reviewed:{issue}" for issue in original_issues
            ),
        )
        result[index] = updated
        details.append(
            {
                "key": key,
                "source_order": original.source_order,
                "source_page": original.source_page,
                "source_section": original.source_section,
                "headword": original.headword,
                "reviewed": True,
                "original_issues": list(original_issues),
                "changed_fields": changed_fields,
                "before": _content_snapshot(original),
                "after": _content_snapshot(updated),
            }
        )
    return result, details


def apply_overrides(
    entries: Sequence[WordDraft], overrides: Mapping[str, Mapping[str, Any]]
) -> list[WordDraft]:
    return apply_overrides_with_audit(entries, overrides)[0]


def _validate(entries: Sequence[WordDraft]) -> None:
    orders: set[int] = set()
    for entry in entries:
        if entry.source_order in orders:
            raise ValueError(f"duplicate source_order: {entry.source_order}")
        orders.add(entry.source_order)
        if not entry.headword.strip():
            raise ValueError(f"blank headword at source_order {entry.source_order}")


def build_database(
    entries: Sequence[WordDraft],
    output_path: Path,
    *,
    equivalence_edges: Sequence[EquivalenceEdge] = (),
    machine7_memberships: Sequence[Machine7Membership] = (),
) -> None:
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
            database.execute("pragma foreign_keys=on")
            database.executescript(CONTENT_SCHEMA)
            database.executemany(
                "insert into metadata(key, value) values(?, ?)",
                (
                    ("schema_version", str(CONTENT_SCHEMA_VERSION)),
                    ("record_count", str(len(ordered))),
                    ("equivalence_edge_count", str(len(equivalence_edges))),
                    ("machine7_membership_count", str(len(machine7_memberships))),
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
            database.executemany(
                """
                insert into equivalence_edges(
                  left_word_id, right_word_id, source_pages
                ) values (?, ?, ?)
                """,
                (
                    (
                        edge.left_word_id,
                        edge.right_word_id,
                        json.dumps(
                            list(edge.source_pages),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    )
                    for edge in equivalence_edges
                ),
            )
            database.executemany(
                """
                insert into machine7_membership(
                  word_id, source_page, source_headword
                ) values (?, ?, ?)
                """,
                (
                    (
                        membership.word_id,
                        membership.source_page,
                        membership.source_headword,
                    )
                    for membership in machine7_memberships
                ),
            )
            foreign_key_errors = database.execute(
                "pragma foreign_key_check"
            ).fetchall()
            if foreign_key_errors:
                raise sqlite3.IntegrityError(
                    f"content database foreign-key check failed: {foreign_key_errors}"
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


def _summarize_dewrap_events(
    events: Sequence[RecordDewrapEvent],
) -> dict[str, dict[str, int]]:
    counts = {
        field: {"normal_space": 0, "hard_join": 0, "hard_join_records": 0}
        for field in ("definition", "example", "synonyms")
    }
    hard_records: dict[str, set[int]] = defaultdict(set)
    for event in events:
        counts[event.field][event.kind] += 1
        if event.kind == "hard_join":
            hard_records[event.field].add(event.source_order)
    for field in counts:
        counts[field]["hard_join_records"] = len(hard_records[field])
    return counts


def _extract_with_diagnostics(
    pdf_path: Path,
) -> tuple[list[WordDraft], int, PhysicalRowCoverage, ExtractionDiagnostics]:
    entries: list[WordDraft] = []
    dewrap_events: list[RecordDewrapEvent] = []
    state = ParserState(next_order=1, section="unknown")
    physical_row_bands = 0
    with fitz.open(pdf_path) as document:
        if document.needs_pass:
            raise ValueError("encrypted PDF requires a password")
        page_count = len(document)
        for page_index in range(4, page_count):
            page = document[page_index]
            spans = extract_page_spans(page)
            bands = extract_page_word_row_bands(
                page,
                spans,
                is_last_page=page_index + 1 == page_count,
            )
            coverage = validate_physical_row_coverage(
                spans,
                page_number=page_index + 1,
                physical_row_bands=bands,
            )
            physical_row_bands += coverage.physical_row_bands
            rows, state = group_spans_into_rows(
                spans,
                page_number=page_index + 1,
                state=state,
                physical_row_bands=bands,
            )
            for row in rows:
                entry, row_events = normalize_row_with_diagnostics(row)
                entries.append(entry)
                dewrap_events.extend(
                    RecordDewrapEvent(
                        source_order=row.source_order,
                        field=event.field,
                        kind=event.kind,
                        left=event.left,
                        right=event.right,
                    )
                    for event in row_events
                )
    diagnostics = ExtractionDiagnostics(
        dewrap_counts=_summarize_dewrap_events(dewrap_events),
        dewrap_events=tuple(dewrap_events),
    )
    return (
        entries,
        page_count,
        PhysicalRowCoverage(
            physical_row_bands=physical_row_bands,
            empty_row_bands=0,
            multi_anchor_row_bands=0,
        ),
        diagnostics,
    )


def _extract(
    pdf_path: Path,
) -> tuple[list[WordDraft], int, PhysicalRowCoverage]:
    entries, page_count, coverage, _ = _extract_with_diagnostics(pdf_path)
    return entries, page_count, coverage


def _boundary_context(left: str, right: str, separator: str) -> str:
    left_context = re.sub(r"\s+", " ", left).strip()[-48:]
    right_context = re.sub(r"\s+", " ", right).strip()[:48]
    return left_context + separator + right_context


def _definition_zh_has_english_sense(text: str) -> bool:
    if ENGLISH_POS_IN_CHINESE.search(text):
        return True
    for match in LATIN_RUN_IN_CHINESE.finditer(text):
        words = LATIN_WORD.findall(match.group())
        if not words:
            continue
        normalized = [word.replace("-", "").replace("'", "") for word in words]
        if not all(word.islower() for word in normalized):
            continue
        if len(words) > 1 or len(normalized[0]) >= 4:
            return True
    return False


def semantic_checks(
    entries: Sequence[WordDraft],
    diagnostics: ExtractionDiagnostics,
) -> list[dict[str, Any]]:
    by_order = {entry.source_order: entry for entry in entries}
    english_cjk = sorted(
        entry.source_order
        for entry in entries
        if CJK.search(entry.definition_en) or CJK.search(entry.example_en)
    )
    chinese_english_sense = sorted(
        entry.source_order
        for entry in entries
        if _definition_zh_has_english_sense(entry.definition_zh)
    )
    hard_residue: set[int] = set()
    normal_overjoin: set[int] = set()
    field_names = {
        "definition": ("definition_en",),
        "example": ("example_en", "example_zh"),
        "synonyms": ("synonyms",),
    }
    for event in diagnostics.dewrap_events:
        entry = by_order.get(event.source_order)
        if entry is None:
            hard_residue.add(event.source_order)
            continue
        values = [getattr(entry, name) for name in field_names[event.field]]
        if event.kind == "hard_join":
            expected = _boundary_context(event.left, event.right, "")
            if not any(expected in value for value in values):
                hard_residue.add(event.source_order)
        else:
            expected = _boundary_context(event.left, event.right, " ")
            if not any(expected in value for value in values):
                normal_overjoin.add(event.source_order)

    def check(name: str, source_orders: Sequence[int]) -> dict[str, Any]:
        return {
            "name": name,
            "pass": not source_orders,
            "count": len(source_orders),
            "source_orders": list(source_orders),
        }

    return [
        check("english_fields_contain_cjk", english_cjk),
        check("definition_zh_contains_english_sense", chinese_english_sense),
        check("hard_wrap_residue", sorted(hard_residue)),
        check("normal_wrap_overjoin", sorted(normal_overjoin)),
    ]


def semantic_checks_after_overrides(
    source_entries: Sequence[WordDraft],
    reviewed_entries: Sequence[WordDraft],
    diagnostics: ExtractionDiagnostics,
) -> list[dict[str, Any]]:
    source_checks = semantic_checks(source_entries, diagnostics)
    final_checks = semantic_checks(
        reviewed_entries,
        ExtractionDiagnostics(dewrap_counts={}, dewrap_events=()),
    )
    # Language assignment belongs to the reviewed final content. Physical
    # de-wrap checks belong to the source extraction that produced the rows;
    # replacement examples and definitions intentionally have no source wrap.
    return final_checks[:2] + source_checks[2:]


def _unresolved_count(entries: Sequence[WordDraft]) -> int:
    return sum(
        any(not flag.startswith("reviewed:") for flag in entry.quality_flags)
        for entry in entries
    )


def _continuity(entries: Sequence[WordDraft]) -> dict[str, Any]:
    orders = [entry.source_order for entry in entries]
    counts = Counter(orders)
    if not orders:
        return {
            "first_source_order": None,
            "last_source_order": None,
            "missing_source_orders": [],
            "duplicate_source_orders": [],
        }
    first, last = min(orders), max(orders)
    return {
        "first_source_order": first,
        "last_source_order": last,
        "missing_source_orders": sorted(set(range(first, last + 1)) - set(orders)),
        "duplicate_source_orders": sorted(
            order for order, count in counts.items() if count > 1
        ),
    }


def _page_range(entries: Sequence[WordDraft]) -> dict[str, int | None]:
    pages = [entry.source_page for entry in entries]
    return {
        "first_source_page": min(pages) if pages else None,
        "last_source_page": max(pages) if pages else None,
    }


def _check(
    name: str, passed: bool, expected: Any, actual: Any
) -> dict[str, Any]:
    return {"name": name, "pass": bool(passed), "expected": expected, "actual": actual}


def _reference_strict_profile(
    reference_sources: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    equivalence = dict(reference_sources.get("equivalence", {}))
    machine7 = dict(reference_sources.get("machine7", {}))
    return {
        "equivalence": {
            "configured": equivalence.get("configured", False),
            "sha256": equivalence.get("sha256", ""),
            "page_count": equivalence.get("page_count", 0),
            "row_count": equivalence.get("row_count", 0),
            "unique_headword_count": equivalence.get(
                "unique_headword_count", 0
            ),
            "equivalent_mention_count": equivalence.get(
                "equivalent_mention_count", 0
            ),
            "matched_headword_rows": equivalence.get(
                "matched_headword_rows", 0
            ),
            "matched_equivalent_mentions": equivalence.get(
                "matched_equivalent_mentions", 0
            ),
            "edge_count": equivalence.get("edge_count", 0),
            "unmatched_headword_count": (
                len(equivalence["unmatched_headwords"])
                if "unmatched_headwords" in equivalence
                else int(equivalence.get("unmatched_headword_count", 0))
            ),
            "unmatched_equivalent_count": (
                len(equivalence["unmatched_equivalents"])
                if "unmatched_equivalents" in equivalence
                else int(equivalence.get("unmatched_equivalent_count", 0))
            ),
        },
        "machine7": {
            "configured": machine7.get("configured", False),
            "sha256": machine7.get("sha256", ""),
            "page_count": machine7.get("page_count", 0),
            "headword_count": machine7.get("headword_count", 0),
            "unique_headword_count": machine7.get(
                "unique_headword_count", 0
            ),
            "matched_count": machine7.get("matched_count", 0),
            "unmatched_headword_count": (
                len(machine7["unmatched_headwords"])
                if "unmatched_headwords" in machine7
                else int(machine7.get("unmatched_headword_count", 0))
            ),
        },
    }


def strict_checks_from_facts(facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    coverage = facts["physical_coverage"]
    continuity = facts["continuity"]
    page_range = facts["page_range"]
    override_use = facts["override_use"]
    semantic = facts["semantic_checks"]
    reference_profile = _reference_strict_profile(
        facts.get("reference_sources", {})
    )
    expected_continuity = {
        "first_source_order": APPROVED_SOURCE_PROFILE["first_source_order"],
        "last_source_order": APPROVED_SOURCE_PROFILE["last_source_order"],
        "missing_source_orders": [],
        "duplicate_source_orders": [],
    }
    expected_page_range = {
        "first_source_page": APPROVED_SOURCE_PROFILE["first_source_page"],
        "last_source_page": APPROVED_SOURCE_PROFILE["last_source_page"],
    }
    return [
        _check(
            "source_sha256",
            facts["source_sha256"] == APPROVED_SOURCE_PROFILE["sha256"],
            APPROVED_SOURCE_PROFILE["sha256"],
            facts["source_sha256"],
        ),
        _check(
            "overrides_sha256",
            facts["overrides_sha256"]
            == APPROVED_SOURCE_PROFILE["overrides_sha256"],
            APPROVED_SOURCE_PROFILE["overrides_sha256"],
            facts["overrides_sha256"],
        ),
        _check(
            "page_count",
            facts["page_count"] == APPROVED_SOURCE_PROFILE["page_count"],
            APPROVED_SOURCE_PROFILE["page_count"],
            facts["page_count"],
        ),
        _check(
            "physical_row_bands",
            coverage["physical_row_bands"]
            == APPROVED_SOURCE_PROFILE["physical_row_bands"],
            APPROVED_SOURCE_PROFILE["physical_row_bands"],
            coverage["physical_row_bands"],
        ),
        _check(
            "empty_row_bands",
            coverage["empty_row_bands"] == 0,
            0,
            coverage["empty_row_bands"],
        ),
        _check(
            "multi_anchor_row_bands",
            coverage["multi_anchor_row_bands"] == 0,
            0,
            coverage["multi_anchor_row_bands"],
        ),
        _check(
            "record_count",
            facts["record_count"] == APPROVED_SOURCE_PROFILE["record_count"],
            APPROVED_SOURCE_PROFILE["record_count"],
            facts["record_count"],
        ),
        _check(
            "source_order_continuity",
            continuity == expected_continuity,
            expected_continuity,
            continuity,
        ),
        _check(
            "source_page_range",
            page_range == expected_page_range,
            expected_page_range,
            page_range,
        ),
        _check(
            "section_counts",
            facts["section_counts"] == APPROVED_SOURCE_PROFILE["section_counts"],
            APPROVED_SOURCE_PROFILE["section_counts"],
            facts["section_counts"],
        ),
        _check(
            "override_use",
            override_use
            == {
                "declared": APPROVED_SOURCE_PROFILE["override_count"],
                "applied": APPROVED_SOURCE_PROFILE["override_count"],
            },
            {
                "declared": APPROVED_SOURCE_PROFILE["override_count"],
                "applied": APPROVED_SOURCE_PROFILE["override_count"],
            },
            override_use,
        ),
        _check(
            "unresolved_records",
            facts["unresolved_count"] == 0,
            0,
            facts["unresolved_count"],
        ),
        _check(
            "reviewed_records",
            facts["reviewed_count"] == APPROVED_SOURCE_PROFILE["reviewed_count"],
            APPROVED_SOURCE_PROFILE["reviewed_count"],
            facts["reviewed_count"],
        ),
        _check(
            "dewrap_profile",
            facts["dewrap_counts"] == APPROVED_SOURCE_PROFILE["dewrap_counts"],
            APPROVED_SOURCE_PROFILE["dewrap_counts"],
            facts["dewrap_counts"],
        ),
        _check(
            "reference_sources",
            reference_profile == APPROVED_SOURCE_PROFILE["reference_sources"],
            APPROVED_SOURCE_PROFILE["reference_sources"],
            reference_profile,
        ),
        _check(
            "semantic_scans",
            all(item.get("pass") is True for item in semantic),
            "all pass",
            semantic,
        ),
    ]


def _facts(
    entries: Sequence[WordDraft],
    *,
    source_sha256: str,
    overrides_sha256: str,
    page_count: int,
    coverage: PhysicalRowCoverage,
    diagnostics: ExtractionDiagnostics,
    override_declared: int,
    override_applied: int,
    checks: Sequence[Mapping[str, Any]],
    reference_sources: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "source_sha256": source_sha256,
        "overrides_sha256": overrides_sha256,
        "page_count": page_count,
        "physical_coverage": {
            "physical_row_bands": coverage.physical_row_bands,
            "empty_row_bands": coverage.empty_row_bands,
            "multi_anchor_row_bands": coverage.multi_anchor_row_bands,
        },
        "record_count": len(entries),
        "continuity": _continuity(entries),
        "page_range": _page_range(entries),
        "section_counts": dict(
            sorted(Counter(entry.source_section for entry in entries).items())
        ),
        "override_use": {
            "declared": override_declared,
            "applied": override_applied,
        },
        "unresolved_count": _unresolved_count(entries),
        "reviewed_count": sum(
            any(flag.startswith("reviewed:") for flag in entry.quality_flags)
            for entry in entries
        ),
        "dewrap_counts": diagnostics.dewrap_counts,
        "semantic_checks": list(checks),
        "reference_sources": dict(reference_sources),
    }


CANDIDATE_ENTRY_FIELDS = (
    "source_order",
    "source_section",
    "source_page",
    "headword",
    "phonetic",
    "definition_en",
    "definition_zh",
    "synonyms",
    "example_en",
    "example_zh",
    "raw_definition",
    "raw_example",
    "quality_flags",
)


def _validate_artifact_candidates(
    entries: Sequence[WordDraft],
    slots: Sequence[ArtifactSlot],
    summary: AuditSummary,
    *,
    facts: Mapping[str, Any],
    override_details: Sequence[Mapping[str, Any]],
    reference_data: ReferenceData,
    strict: bool,
) -> None:
    database_path, json_path, html_path = (
        slot.candidate for slot in slots
    )
    try:
        with ContentRepository(database_path) as repository:
            database_entries = tuple(
                repository.get(word_id)
                for word_id in repository.ids_in_source_order()
            )
            database_edges = tuple(
                EquivalenceEdge(
                    int(row[0]),
                    int(row[1]),
                    tuple(json.loads(str(row[2]))),
                )
                for row in repository.db.execute(
                    "select left_word_id, right_word_id, source_pages "
                    "from equivalence_edges order by left_word_id, right_word_id"
                )
            )
            database_memberships = tuple(
                Machine7Membership(int(row[0]), int(row[1]), str(row[2]))
                for row in repository.db.execute(
                    "select word_id, source_page, source_headword "
                    "from machine7_membership order by word_id"
                )
            )
    except ContentDatabaseError as error:
        raise ValueError(
            f"candidate database contract validation failed: {error}"
        ) from error

    ordered_entries = tuple(
        sorted(entries, key=lambda entry: entry.source_order)
    )
    if (
        len(database_entries) != len(ordered_entries)
        or len(database_entries) != facts["record_count"]
    ):
        raise ValueError(
            "candidate database record count mismatch: "
            f"entries={len(ordered_entries)}, facts={facts['record_count']}, "
            f"database={len(database_entries)}"
        )
    for expected_id, (expected, actual) in enumerate(
        zip(ordered_entries, database_entries, strict=True), start=1
    ):
        if actual.id != expected_id:
            raise ValueError(
                "candidate database id mismatch at source_order "
                f"{expected.source_order}: expected {expected_id}, got {actual.id}"
            )
        for field in CANDIDATE_ENTRY_FIELDS:
            expected_value = getattr(expected, field)
            actual_value = getattr(actual, field)
            if actual_value != expected_value:
                raise ValueError(
                    "candidate database field mismatch at source_order "
                    f"{expected.source_order}: {field}"
                )
    if database_edges != reference_data.equivalence_edges:
        raise ValueError("candidate database equivalence edges mismatch")
    if database_memberships != reference_data.machine7_memberships:
        raise ValueError("candidate database machine 7.0 memberships mismatch")

    json_bytes = json_path.read_bytes()
    try:
        payload = json.loads(
            json_bytes.decode("utf-8"),
            object_pairs_hook=_duplicate_rejecting_object,
        )
    except (UnicodeDecodeError, ValueError) as error:
        raise ValueError(
            f"candidate audit JSON validation failed: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise ValueError("candidate audit JSON must be an object")

    expected_strict_checks = strict_checks_from_facts(facts)
    expected_payload = build_audit_payload(
        entries,
        source_sha256=facts["source_sha256"],
        overrides_sha256=facts["overrides_sha256"],
        page_count=facts["page_count"],
        approved_source_profile=APPROVED_SOURCE_PROFILE,
        physical_coverage=facts["physical_coverage"],
        continuity=facts["continuity"],
        page_range=facts["page_range"],
        dewrap_counts=facts["dewrap_counts"],
        override_details=override_details,
        semantic_checks=facts["semantic_checks"],
        strict_checks=expected_strict_checks,
        reference_sources=facts["reference_sources"],
    )
    expected_json_bytes = (
        json.dumps(
            expected_payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    if json_bytes != expected_json_bytes:
        differing_fields = sorted(
            key
            for key in set(payload) | set(expected_payload)
            if payload.get(key) != expected_payload.get(key)
        )
        raise ValueError(
            "candidate audit JSON payload mismatch: "
            + (", ".join(differing_fields) or "serialized representation")
        )

    html = html_path.read_text(encoding="utf-8")
    json_digest = hashlib.sha256(json_bytes).hexdigest()
    expected_html = render_audit_html(
        payload, audit_json_sha256=json_digest
    )
    if html != expected_html:
        raise ValueError("candidate audit HTML content mismatch")
    if (
        summary.record_count != facts["record_count"]
        or summary.unresolved_count != facts["unresolved_count"]
        or summary.reviewed_count != facts["reviewed_count"]
    ):
        raise ValueError("candidate audit summary mismatch")

    if strict:
        if not all(check.get("pass") is True for check in expected_strict_checks):
            raise ValueError("candidate strict audit has a failed strict check")
        if facts["unresolved_count"] != 0:
            raise ValueError(
                "candidate strict audit requires zero unresolved records"
            )
        if (
            facts["reviewed_count"]
            != APPROVED_SOURCE_PROFILE["reviewed_count"]
        ):
            raise ValueError(
                "candidate strict audit reviewed record count mismatch"
            )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the offline GRE word database")
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--audit-json", required=True, type=Path)
    parser.add_argument("--audit-html", required=True, type=Path)
    parser.add_argument("--overrides", required=True, type=Path)
    parser.add_argument("--equivalence-pdf", type=Path)
    parser.add_argument("--machine7-pdf", type=Path)
    parser.add_argument("--strict", action="store_true")
    return parser


def _run(args: argparse.Namespace) -> int:
    source_hash = _source_sha256(args.pdf)
    entries, page_count, coverage, diagnostics = _extract_with_diagnostics(args.pdf)
    source_hash_after = _source_sha256(args.pdf)
    if source_hash_after != source_hash:
        raise ValueError("source PDF changed during extraction")
    source_entries = entries
    overrides, overrides_hash = _load_overrides_with_hash(args.overrides)
    entries, override_details = apply_overrides_with_audit(
        source_entries, overrides
    )
    semantic = semantic_checks_after_overrides(
        source_entries,
        entries,
        diagnostics,
    )
    if bool(args.equivalence_pdf) != bool(args.machine7_pdf):
        raise ValueError(
            "equivalence PDF and machine 7.0 PDF must be configured together"
        )
    reference_data = ReferenceData.empty()
    if args.equivalence_pdf is not None and args.machine7_pdf is not None:
        reference_data = load_reference_data(
            entries,
            equivalence_pdf=args.equivalence_pdf,
            machine7_pdf=args.machine7_pdf,
        )
    facts = _facts(
        entries,
        source_sha256=source_hash,
        overrides_sha256=overrides_hash,
        page_count=page_count,
        coverage=coverage,
        diagnostics=diagnostics,
        override_declared=len(overrides),
        override_applied=len(override_details),
        checks=semantic,
        reference_sources=reference_data.facts or {},
    )
    strict_checks = strict_checks_from_facts(facts)
    if args.strict:
        failed = [check["name"] for check in strict_checks if not check["pass"]]
        if failed:
            raise ValueError("strict validation failed: " + ", ".join(failed))

    # Generate and validate a complete sibling candidate set before publishing
    # any fixed output path. Publication rolls back the whole set on failure.
    slots = plan_artifact_publication(
        (args.output, args.audit_json, args.audit_html)
    )
    try:
        reference_database_arguments: dict[str, object] = {}
        if args.equivalence_pdf is not None:
            reference_database_arguments = {
                "equivalence_edges": reference_data.equivalence_edges,
                "machine7_memberships": reference_data.machine7_memberships,
            }
        build_database(
            entries,
            slots[0].candidate,
            **reference_database_arguments,
        )
        summary = write_audit(
            entries,
            slots[1].candidate,
            slots[2].candidate,
            source_path=args.pdf,
            source_sha256=source_hash,
            overrides_sha256=overrides_hash,
            page_count=page_count,
            approved_source_profile=APPROVED_SOURCE_PROFILE,
            physical_coverage=facts["physical_coverage"],
            continuity=facts["continuity"],
            page_range=facts["page_range"],
            dewrap_counts=diagnostics.dewrap_counts,
            override_details=override_details,
            semantic_checks=semantic,
            strict_checks=strict_checks,
            reference_sources=facts["reference_sources"],
        )
        _validate_artifact_candidates(
            entries,
            slots,
            summary,
            facts=facts,
            override_details=override_details,
            reference_data=reference_data,
            strict=args.strict,
        )
        publish_artifact_slots(slots)
    finally:
        cleanup_artifact_slots(slots)
    print(
        f"physical_row_bands={coverage.physical_row_bands} "
        f"empty_row_bands={coverage.empty_row_bands} "
        f"multi_anchor_row_bands={coverage.multi_anchor_row_bands}"
    )
    print(
        f"records={summary.record_count} unresolved={summary.unresolved_count} "
        f"reviewed={summary.reviewed_count}"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return _run(args)
    except (OSError, RuntimeError, ValueError, sqlite3.DatabaseError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
