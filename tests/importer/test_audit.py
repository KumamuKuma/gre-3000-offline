import hashlib
import json
import re
from pathlib import Path

import fitz
import pytest

from gre_vocab_app.importer import build as build_module
from gre_vocab_app.importer.audit import write_audit
from gre_vocab_app.importer.build import ExtractionDiagnostics, main
from gre_vocab_app.importer.layout import PhysicalRowCoverage
from gre_vocab_app.importer.normalize import WordDraft


def draft(
    word: str,
    order: int,
    *,
    section: str = "list1",
    flags: tuple[str, ...] = (),
    definition: str = "adj. sample",
) -> WordDraft:
    return WordDraft(
        source_order=order,
        source_section=section,
        source_page=5,
        headword=word,
        phonetic="[x]",
        definition_en=definition,
        definition_zh="示例",
        synonyms="",
        example_en="",
        example_zh="",
        raw_definition=f"{definition} 示例",
        raw_example="",
        quality_flags=flags,
    )


def test_audit_contains_counts_categories_duplicates_and_escaped_html(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"source bytes")
    entries = [
        draft("<alpha>", 1, flags=("missing_phonetic",), definition="<b>bad</b>"),
        draft("<alpha>", 2, flags=("reviewed:split_token",)),
        draft("beta", 3, section="list2"),
    ]
    json_path = tmp_path / "audit" / "report.json"
    html_path = tmp_path / "audit" / "report.html"

    summary = write_audit(
        entries,
        json_path,
        html_path,
        source_path=source,
        page_count=288,
        approved_source_profile={
            "sha256": "approved",
            "page_count": 288,
            "physical_row_bands": 3292,
            "record_count": 3292,
        },
        physical_coverage={
            "physical_row_bands": 3292,
            "empty_row_bands": 0,
            "multi_anchor_row_bands": 0,
        },
        continuity={
            "first_source_order": 1,
            "last_source_order": 3,
            "missing_source_orders": [],
            "duplicate_source_orders": [],
        },
        page_range={"first_source_page": 5, "last_source_page": 5},
        dewrap_counts={
            "definition": {
                "normal_space": 4,
                "hard_join": 0,
                "hard_join_records": 0,
            }
        },
        override_details=[
            {
                "key": "5:<alpha>",
                "source_order": 2,
                "kinds": ["part_of_speech", "example"],
                "reason": "The label and example disagree.",
                "evidence": ["source_pdf:5", "manual:grammar-review"],
                "original_issues": ["split_token"],
                "changed_fields": ["definition_en"],
                "before": {"definition_en": "bad"},
                "after": {"definition_en": "fixed"},
            }
        ],
        semantic_checks=[
            {"name": "language_contamination", "pass": True, "count": 0}
        ],
        strict_checks=[
            {"name": "source_sha256", "pass": True, "expected": "x", "actual": "x"}
        ],
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(payload["source_sha256"]) == 64
    assert payload["page_count"] == 288
    assert payload["record_count"] == 3
    assert payload["section_counts"] == {"list1": 2, "list2": 1}
    assert [item["headword"] for item in payload["unresolved_records"]] == [
        "<alpha>"
    ]
    assert [item["headword"] for item in payload["reviewed_records"]] == [
        "<alpha>"
    ]
    assert payload["duplicate_headwords"] == [
        {"headword": "<alpha>", "source_orders": [1, 2]}
    ]
    assert payload["source_profile"]["approved"]["physical_row_bands"] == 3292
    assert payload["source_profile"]["actual"]["page_count"] == 288
    assert payload["physical_coverage"]["physical_row_bands"] == 3292
    assert payload["continuity"]["missing_source_orders"] == []
    assert payload["page_range"] == {
        "first_source_page": 5,
        "last_source_page": 5,
    }
    assert payload["dewrap_counts"]["definition"]["normal_space"] == 4
    assert payload["override_details"][0]["before"] == {"definition_en": "bad"}
    assert payload["override_kind_counts"] == {
        "example": 1,
        "part_of_speech": 1,
    }
    assert payload["semantic_checks"][0]["pass"] is True
    assert payload["strict_checks"][0]["pass"] is True
    assert summary.unresolved_count == 1
    assert summary.reviewed_count == 1

    html = html_path.read_text(encoding="utf-8")
    assert "&lt;alpha&gt;" in html
    assert "&lt;b&gt;bad&lt;/b&gt;" in html
    assert "<alpha>" not in html
    assert "<b>bad</b>" not in html
    assert "part_of_speech" in html
    assert "The label and example disagree." in html
    assert "manual:grammar-review" in html
    for heading in (
        "Source profile",
        "Physical coverage",
        "Continuity",
        "De-wrap counts",
        "Override details",
        "Semantic checks",
        "Strict checks",
    ):
        assert heading in html


def test_audit_uses_stable_supplied_hashes_without_rereading_source(tmp_path):
    missing_source = tmp_path / "source-was-removed.pdf"
    json_path = tmp_path / "report.json"
    html_path = tmp_path / "report.html"
    source_sha256 = "a" * 64
    overrides_sha256 = "b" * 64

    write_audit(
        [draft("alpha", 1)],
        json_path,
        html_path,
        source_path=missing_source,
        source_sha256=source_sha256,
        overrides_sha256=overrides_sha256,
        approved_source_profile={
            "sha256": "c" * 64,
            "overrides_sha256": "d" * 64,
        },
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["source_sha256"] == source_sha256
    assert payload["overrides_sha256"] == overrides_sha256
    assert payload["source_profile"]["actual"]["sha256"] == source_sha256
    assert (
        payload["source_profile"]["actual"]["overrides_sha256"]
        == overrides_sha256
    )
    html = html_path.read_text(encoding="utf-8")
    assert source_sha256 in html
    assert overrides_sha256 in html
    json_digest = hashlib.sha256(json_path.read_bytes()).hexdigest()
    assert (
        f'<meta name="audit-json-sha256" content="{json_digest}">' in html
    )


def _stub_successful_extract(monkeypatch, entries=None):
    extracted_entries = [draft("alpha", 1)] if entries is None else entries
    diagnostics = ExtractionDiagnostics(
        dewrap_counts={
            field: {
                "normal_space": 0,
                "hard_join": 0,
                "hard_join_records": 0,
            }
            for field in ("definition", "example", "synonyms")
        },
        dewrap_events=(),
    )
    monkeypatch.setattr(
        build_module,
        "_extract_with_diagnostics",
        lambda _path: (
            extracted_entries,
            5,
            PhysicalRowCoverage(len(extracted_entries), 0, 0),
            diagnostics,
        ),
    )


def _import_arguments(tmp_path, output, audit_json, audit_html):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"synthetic source")
    overrides = tmp_path / "overrides.json"
    overrides.write_text("{}", encoding="utf-8")
    return [
        "--pdf",
        str(source),
        "--output",
        str(output),
        "--audit-json",
        str(audit_json),
        "--audit-html",
        str(audit_html),
        "--overrides",
        str(overrides),
    ]


def _publication_leftovers(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if ".candidate-" in path.name or ".backup-" in path.name
    )


def _rewrite_audit_and_sync_html(json_path, html_path, mutate):
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    mutate(payload)
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(json_path.read_bytes()).hexdigest()
    marker = f'<meta name="audit-json-sha256" content="{digest}">'
    html = html_path.read_text(encoding="utf-8")
    if 'name="audit-json-sha256"' in html:
        html = re.sub(
            r'<meta name="audit-json-sha256" content="[0-9a-f]{64}">',
            marker,
            html,
            count=1,
        )
    else:
        html = html.replace("<head>", "<head>" + marker, 1)
    html_path.write_text(html, encoding="utf-8")


def test_cli_strict_mode_rejects_unapproved_pdf_without_replacing_outputs(
    tmp_path, capsys
):
    pdf = tmp_path / "source.pdf"
    document = fitz.open()
    for _ in range(5):
        document.new_page(width=596, height=842)
    page = document[4]
    for y in (11.16, 40.16, 101.16):
        page.draw_rect(
            fitz.Rect(17.16, y, 569.52, y + 0.36),
            color=None,
            fill=(0, 0, 0),
        )
    for x in (17.16, 98.16, 186.16, 323.16, 382.16, 569.16):
        page.draw_rect(
            fitz.Rect(x, 11.16, x + 0.36, 101.52),
            color=None,
            fill=(0, 0, 0),
        )
    page.insert_text((19, 70), "alpha", fontsize=10)
    page.insert_text((100, 70), "[a]", fontsize=10)
    page.insert_text((188, 70), "adj. sample", fontsize=10)
    page.insert_text((384, 70), "An example.", fontsize=10)
    document.save(pdf)
    document.close()

    output = tmp_path / "build" / "words.db"
    audit_json = tmp_path / "audit" / "report.json"
    audit_html = tmp_path / "audit" / "report.html"
    output.parent.mkdir(parents=True)
    audit_json.parent.mkdir(parents=True)
    output.write_bytes(b"trusted database")
    audit_json.write_text("trusted json", encoding="utf-8")
    audit_html.write_text("trusted html", encoding="utf-8")
    overrides = tmp_path / "overrides.json"
    overrides.write_text("{}", encoding="utf-8")

    result = main(
        [
            "--pdf",
            str(pdf),
            "--output",
            str(output),
            "--audit-json",
            str(audit_json),
            "--audit-html",
            str(audit_html),
            "--overrides",
            str(overrides),
            "--strict",
        ]
    )

    assert result == 1
    assert output.read_bytes() == b"trusted database"
    assert audit_json.read_text(encoding="utf-8") == "trusted json"
    assert audit_html.read_text(encoding="utf-8") == "trusted html"
    captured = capsys.readouterr()
    assert "strict validation failed" in captured.err
    assert captured.out == ""


def test_cli_strict_mode_rejects_four_page_empty_pdf(tmp_path, capsys):
    pdf = tmp_path / "empty.pdf"
    with fitz.open() as document:
        for _ in range(4):
            document.new_page(width=596, height=842)
        document.save(pdf)
    overrides = tmp_path / "overrides.json"
    overrides.write_text("{}", encoding="utf-8")

    result = main(
        [
            "--pdf",
            str(pdf),
            "--output",
            str(tmp_path / "words.db"),
            "--audit-json",
            str(tmp_path / "audit.json"),
            "--audit-html",
            str(tmp_path / "audit.html"),
            "--overrides",
            str(overrides),
            "--strict",
        ]
    )

    assert result == 1
    assert not (tmp_path / "words.db").exists()
    assert not (tmp_path / "audit.json").exists()
    assert not (tmp_path / "audit.html").exists()
    assert "strict validation failed" in capsys.readouterr().err


def test_cli_returns_one_for_missing_input(tmp_path, capsys):
    result = main(
        [
            "--pdf",
            str(tmp_path / "missing.pdf"),
            "--output",
            str(tmp_path / "words.db"),
            "--audit-json",
            str(tmp_path / "report.json"),
            "--audit-html",
            str(tmp_path / "report.html"),
            "--overrides",
            str(tmp_path / "overrides.json"),
        ]
    )
    assert result == 1
    assert "error:" in capsys.readouterr().err.lower()


@pytest.mark.parametrize("failed_publish", [2, 3])
def test_cli_rolls_back_all_artifacts_when_later_publish_replace_fails(
    tmp_path, monkeypatch, capsys, failed_publish
):
    _stub_successful_extract(monkeypatch)
    output = tmp_path / "build" / "words.db"
    audit_json = tmp_path / "audit" / "report.json"
    audit_html = tmp_path / "audit" / "report.html"
    output.parent.mkdir()
    audit_json.parent.mkdir()
    output.write_bytes(b"trusted database")
    audit_json.write_text("trusted json", encoding="utf-8")
    audit_html.write_text("trusted html", encoding="utf-8")
    final_paths = {
        Path(path).resolve()
        for path in (output, audit_json, audit_html)
    }
    real_replace = build_module.os.replace
    publish_calls = 0

    def fail_selected_publish(source, destination):
        nonlocal publish_calls
        if Path(destination).resolve() in final_paths:
            publish_calls += 1
            if publish_calls == failed_publish:
                raise OSError(f"publish {failed_publish} failed")
        return real_replace(source, destination)

    monkeypatch.setattr(build_module.os, "replace", fail_selected_publish)

    result = main(
        _import_arguments(tmp_path, output, audit_json, audit_html)
    )

    assert result == 1
    assert output.read_bytes() == b"trusted database"
    assert audit_json.read_text(encoding="utf-8") == "trusted json"
    assert audit_html.read_text(encoding="utf-8") == "trusted html"
    assert _publication_leftovers(tmp_path) == []
    assert f"publish {failed_publish} failed" in capsys.readouterr().err


def test_cli_candidate_write_failure_preserves_old_artifact_set(
    tmp_path, monkeypatch, capsys
):
    _stub_successful_extract(monkeypatch)
    output = tmp_path / "words.db"
    audit_json = tmp_path / "audit.json"
    audit_html = tmp_path / "audit.html"
    output.write_bytes(b"trusted database")
    audit_json.write_text("trusted json", encoding="utf-8")
    audit_html.write_text("trusted html", encoding="utf-8")

    def fail_during_audit_write(_entries, json_path, _html_path, **_kwargs):
        json_path.write_text("partial candidate", encoding="utf-8")
        raise OSError("candidate HTML write failed")

    monkeypatch.setattr(build_module, "write_audit", fail_during_audit_write)

    result = main(
        _import_arguments(tmp_path, output, audit_json, audit_html)
    )

    assert result == 1
    assert output.read_bytes() == b"trusted database"
    assert audit_json.read_text(encoding="utf-8") == "trusted json"
    assert audit_html.read_text(encoding="utf-8") == "trusted html"
    assert _publication_leftovers(tmp_path) == []
    assert "candidate HTML write failed" in capsys.readouterr().err


@pytest.mark.parametrize(
    "tamper",
    (
        "source_hash",
        "overrides_hash",
        "strict_checks",
        "unresolved_records",
        "reviewed_records",
        "json_numeric_type",
        "duplicate_key",
        "database_metadata_count",
        "database_content",
        "database_quality_flags",
        "database_id",
        "database_schema_version",
        "duplicate_headwords",
        "html_link",
        "html_body",
    ),
)
def test_cli_rejects_tampered_candidate_audit_and_preserves_old_artifact_set(
    tmp_path, monkeypatch, capsys, tamper
):
    extracted_entries = None
    if tamper == "unresolved_records":
        extracted_entries = [
            draft("alpha", 1, flags=("missing_phonetic",))
        ]
    elif tamper == "reviewed_records":
        extracted_entries = [
            draft("alpha", 1, flags=("reviewed:sample",))
        ]
    _stub_successful_extract(monkeypatch, extracted_entries)
    output = tmp_path / "words.db"
    audit_json = tmp_path / "audit.json"
    audit_html = tmp_path / "audit.html"
    output.write_bytes(b"trusted database")
    audit_json.write_text("trusted json", encoding="utf-8")
    audit_html.write_text("trusted html", encoding="utf-8")
    if tamper in {
        "database_metadata_count",
        "database_content",
        "database_quality_flags",
        "database_id",
        "database_schema_version",
    }:
        real_build_database = build_module.build_database

        def build_then_tamper_metadata(entries, database_path):
            real_build_database(entries, database_path)
            database = build_module.sqlite3.connect(database_path)
            try:
                if tamper == "database_metadata_count":
                    database.execute(
                        "update metadata set value='999' "
                        "where key='record_count'"
                    )
                elif tamper == "database_content":
                    database.execute(
                        "update words set definition_en='forged' where id=1"
                    )
                elif tamper == "database_quality_flags":
                    database.execute(
                        "update words set quality_flags='[\"forged\"]' "
                        "where id=1"
                    )
                elif tamper == "database_id":
                    database.execute("update words set id=99 where id=1")
                else:
                    database.execute(
                        "update metadata set value='999' "
                        "where key='schema_version'"
                    )
                database.commit()
            finally:
                database.close()

        monkeypatch.setattr(
            build_module, "build_database", build_then_tamper_metadata
        )
    real_write_audit = build_module.write_audit

    def write_then_tamper(entries, json_path, html_path, **kwargs):
        summary = real_write_audit(entries, json_path, html_path, **kwargs)

        def mutate(payload):
            if tamper == "source_hash":
                payload["source_sha256"] = "0" * 64
                payload["source_profile"]["actual"]["sha256"] = "0" * 64
            elif tamper == "overrides_hash":
                payload["overrides_sha256"] = "1" * 64
                payload["source_profile"]["actual"]["overrides_sha256"] = (
                    "1" * 64
                )
            elif tamper == "strict_checks":
                payload["strict_checks"][0]["pass"] = not payload[
                    "strict_checks"
                ][0]["pass"]
            elif tamper == "unresolved_records":
                payload["unresolved_records"] = [{"source_order": 999}]
            elif tamper == "reviewed_records":
                payload["reviewed_records"] = [{"source_order": 999}]
            elif tamper == "json_numeric_type":
                payload["record_count"] = float(payload["record_count"])
            elif tamper == "duplicate_headwords":
                payload["duplicate_headwords"] = [
                    {"headword": "forged", "source_orders": [1, 1]}
                ]

        _rewrite_audit_and_sync_html(json_path, html_path, mutate)
        if tamper == "json_numeric_type":
            forged_payload = json.loads(json_path.read_text(encoding="utf-8"))
            forged_digest = hashlib.sha256(json_path.read_bytes()).hexdigest()
            html_path.write_text(
                build_module.render_audit_html(
                    forged_payload, audit_json_sha256=forged_digest
                ),
                encoding="utf-8",
            )
        if tamper == "duplicate_key":
            raw_json = json_path.read_text(encoding="utf-8")
            json_path.write_text(
                raw_json.replace(
                    "{\n", '{\n  "record_count": 999,\n', 1
                ),
                encoding="utf-8",
            )
            digest = hashlib.sha256(json_path.read_bytes()).hexdigest()
            html = html_path.read_text(encoding="utf-8")
            html_path.write_text(
                re.sub(
                    r'(<meta name="audit-json-sha256" content=")[0-9a-f]{64}(">)',
                    r"\g<1>" + digest + r"\g<2>",
                    html,
                    count=1,
                ),
                encoding="utf-8",
            )
        if tamper == "html_link":
            html = html_path.read_text(encoding="utf-8")
            html_path.write_text(
                re.sub(
                    r'(<meta name="audit-json-sha256" content=")[0-9a-f]{64}(">)',
                    r"\g<1>" + "f" * 64 + r"\g<2>",
                    html,
                    count=1,
                ),
                encoding="utf-8",
            )
        if tamper == "html_body":
            html = html_path.read_text(encoding="utf-8")
            html_path.write_text(
                html.replace(
                    "<h1>Vocabulary import audit</h1>",
                    "<h1>Forged audit body</h1>",
                    1,
                ),
                encoding="utf-8",
            )
        return summary

    monkeypatch.setattr(build_module, "write_audit", write_then_tamper)

    result = main(
        _import_arguments(tmp_path, output, audit_json, audit_html)
    )

    assert result == 1
    expected_error = (
        "candidate database"
        if tamper
        in {
            "database_metadata_count",
            "database_content",
            "database_quality_flags",
            "database_id",
            "database_schema_version",
        }
        else "candidate audit"
    )
    assert expected_error in capsys.readouterr().err
    assert output.read_bytes() == b"trusted database"
    assert audit_json.read_text(encoding="utf-8") == "trusted json"
    assert audit_html.read_text(encoding="utf-8") == "trusted html"
    assert _publication_leftovers(tmp_path) == []


@pytest.mark.parametrize(
    "forged_field",
    ["key", "kinds", "reason", "evidence", "override_kind_counts"],
)
def test_cli_rejects_same_length_forged_override_details_and_preserves_outputs(
    tmp_path, monkeypatch, capsys, forged_field
):
    _stub_successful_extract(
        monkeypatch,
        [draft("alpha", 1, flags=("missing_phonetic",))],
    )
    output = tmp_path / "words.db"
    audit_json = tmp_path / "audit.json"
    audit_html = tmp_path / "audit.html"
    output.write_bytes(b"trusted database")
    audit_json.write_text("trusted json", encoding="utf-8")
    audit_html.write_text("trusted html", encoding="utf-8")
    arguments = _import_arguments(tmp_path, output, audit_json, audit_html)
    Path(arguments[-1]).write_text(
        json.dumps(
            {
                "5:alpha": {
                    "source_order": 1,
                    "kinds": ["phonetic"],
                    "reason": "The source pronunciation is invalid.",
                    "evidence": ["source_pdf:5", "dictionary:test"],
                    "expected_before": {"phonetic": "[x]"},
                    "changes": {"phonetic": "[a]"},
                    "reviewed": True,
                }
            }
        ),
        encoding="utf-8",
    )
    real_write_audit = build_module.write_audit

    def write_then_forge(entries, json_path, html_path, **kwargs):
        summary = real_write_audit(entries, json_path, html_path, **kwargs)

        def forge(payload):
            if forged_field == "override_kind_counts":
                payload["override_kind_counts"] = {"phonetic": 2}
            elif forged_field == "kinds":
                payload["override_details"][0]["kinds"] = ["example"]
            elif forged_field == "evidence":
                payload["override_details"][0]["evidence"] = ["forged"]
            else:
                payload["override_details"][0][forged_field] = "forged"

        _rewrite_audit_and_sync_html(json_path, html_path, forge)
        return summary

    monkeypatch.setattr(build_module, "write_audit", write_then_forge)

    result = main(arguments)

    assert result == 1
    assert "candidate audit" in capsys.readouterr().err
    assert output.read_bytes() == b"trusted database"
    assert audit_json.read_text(encoding="utf-8") == "trusted json"
    assert audit_html.read_text(encoding="utf-8") == "trusted html"
    assert _publication_leftovers(tmp_path) == []


@pytest.mark.parametrize(
    ("reviewed_count", "unresolved_count"), ((4, 0), (5, 1))
)
def test_strict_candidate_rechecks_review_counts_before_publication(
    tmp_path, monkeypatch, capsys, reviewed_count, unresolved_count
):
    diagnostics = ExtractionDiagnostics(
        dewrap_counts={
            field: {
                "normal_space": 0,
                "hard_join": 0,
                "hard_join_records": 0,
            }
            for field in ("definition", "example", "synonyms")
        },
        dewrap_events=(),
    )
    entries = [
        draft(
            f"reviewed-{order}",
            order,
            flags=("reviewed:sample",),
        )
        for order in range(1, reviewed_count + 1)
    ]
    entries.extend(
        draft(
            f"unresolved-{order}",
            reviewed_count + order,
            flags=("missing_phonetic",),
        )
        for order in range(1, unresolved_count + 1)
    )
    monkeypatch.setattr(
        build_module,
        "_extract_with_diagnostics",
        lambda _path: (
            entries,
            5,
            PhysicalRowCoverage(len(entries), 0, 0),
            diagnostics,
        ),
    )
    monkeypatch.setattr(
        build_module,
        "_source_sha256",
        lambda _path: build_module.APPROVED_SOURCE_PROFILE["sha256"],
    )
    monkeypatch.setattr(
        build_module,
        "_load_overrides_with_hash",
        lambda _path: (
            {},
            build_module.APPROVED_SOURCE_PROFILE["overrides_sha256"],
        ),
    )
    monkeypatch.setattr(
        build_module,
        "strict_checks_from_facts",
        lambda _facts: [
            {"name": "synthetic_gate", "pass": True, "expected": 1, "actual": 1}
        ],
    )
    output = tmp_path / "words.db"
    audit_json = tmp_path / "audit.json"
    audit_html = tmp_path / "audit.html"
    output.write_bytes(b"trusted database")
    audit_json.write_text("trusted json", encoding="utf-8")
    audit_html.write_text("trusted html", encoding="utf-8")
    arguments = _import_arguments(tmp_path, output, audit_json, audit_html)
    arguments.append("--strict")

    result = main(arguments)

    assert result == 1
    assert "candidate strict audit" in capsys.readouterr().err
    assert output.read_bytes() == b"trusted database"
    assert audit_json.read_text(encoding="utf-8") == "trusted json"
    assert audit_html.read_text(encoding="utf-8") == "trusted html"
    assert _publication_leftovers(tmp_path) == []


def test_cli_rejects_pdf_changed_during_extraction_without_replacing_outputs(
    tmp_path, monkeypatch, capsys
):
    output = tmp_path / "words.db"
    audit_json = tmp_path / "audit.json"
    audit_html = tmp_path / "audit.html"
    output.write_bytes(b"trusted database")
    audit_json.write_text("trusted json", encoding="utf-8")
    audit_html.write_text("trusted html", encoding="utf-8")
    arguments = _import_arguments(tmp_path, output, audit_json, audit_html)

    diagnostics = ExtractionDiagnostics(
        dewrap_counts={
            field: {
                "normal_space": 0,
                "hard_join": 0,
                "hard_join_records": 0,
            }
            for field in ("definition", "example", "synonyms")
        },
        dewrap_events=(),
    )

    def mutate_during_extract(source):
        Path(source).write_bytes(b"source changed while extracting")
        return (
            [draft("alpha", 1)],
            5,
            PhysicalRowCoverage(1, 0, 0),
            diagnostics,
        )

    monkeypatch.setattr(
        build_module, "_extract_with_diagnostics", mutate_during_extract
    )

    result = main(arguments)

    assert result == 1
    assert "changed during extraction" in capsys.readouterr().err
    assert output.read_bytes() == b"trusted database"
    assert audit_json.read_text(encoding="utf-8") == "trusted json"
    assert audit_html.read_text(encoding="utf-8") == "trusted html"
    assert _publication_leftovers(tmp_path) == []


def test_cli_html_output_directory_conflict_preserves_old_database_and_json(
    tmp_path, monkeypatch, capsys
):
    _stub_successful_extract(monkeypatch)
    output = tmp_path / "words.db"
    audit_json = tmp_path / "audit.json"
    audit_html = tmp_path / "audit.html"
    output.write_bytes(b"trusted database")
    audit_json.write_text("trusted json", encoding="utf-8")
    audit_html.mkdir()
    sentinel = audit_html / "sentinel.txt"
    sentinel.write_text("trusted directory", encoding="utf-8")

    result = main(
        _import_arguments(tmp_path, output, audit_json, audit_html)
    )

    assert result == 1
    assert output.read_bytes() == b"trusted database"
    assert audit_json.read_text(encoding="utf-8") == "trusted json"
    assert sentinel.read_text(encoding="utf-8") == "trusted directory"
    assert _publication_leftovers(tmp_path) == []
    assert "artifact output path is not a file" in capsys.readouterr().err


def test_cli_rejects_html_path_that_aliases_json_before_writing(
    tmp_path, monkeypatch, capsys
):
    _stub_successful_extract(monkeypatch)
    output = tmp_path / "words.db"
    audit = tmp_path / "audit"
    output.write_bytes(b"trusted database")
    audit.write_text("trusted audit", encoding="utf-8")

    result = main(_import_arguments(tmp_path, output, audit, audit))

    assert result == 1
    assert output.read_bytes() == b"trusted database"
    assert audit.read_text(encoding="utf-8") == "trusted audit"
    assert _publication_leftovers(tmp_path) == []
    assert "artifact output paths must be distinct" in capsys.readouterr().err
