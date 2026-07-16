import json

import fitz

from gre_vocab_app.importer.audit import write_audit
from gre_vocab_app.importer.build import main
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
    assert summary.unresolved_count == 1
    assert summary.reviewed_count == 1

    html = html_path.read_text(encoding="utf-8")
    assert "&lt;alpha&gt;" in html
    assert "&lt;b&gt;bad&lt;/b&gt;" in html
    assert "<alpha>" not in html
    assert "<b>bad</b>" not in html


def test_cli_strict_mode_writes_outputs_then_returns_two(tmp_path, capsys):
    pdf = tmp_path / "source.pdf"
    document = fitz.open()
    for _ in range(5):
        document.new_page(width=596, height=842)
    page = document[4]
    page.insert_text((19, 70), "alpha", fontsize=10)
    page.insert_text((100, 70), "[a]", fontsize=10)
    page.insert_text((188, 70), "adj. sample", fontsize=10)
    page.insert_text((384, 70), "An example.", fontsize=10)
    document.save(pdf)
    document.close()

    output = tmp_path / "build" / "words.db"
    audit_json = tmp_path / "audit" / "report.json"
    audit_html = tmp_path / "audit" / "report.html"
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

    assert result == 2
    assert output.exists() and audit_json.exists() and audit_html.exists()
    assert capsys.readouterr().out.strip().endswith(
        "records=1 unresolved=1 reviewed=0"
    )


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

