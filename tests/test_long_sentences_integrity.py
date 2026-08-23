from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NATIVE_DATA = ROOT / "resources" / "long_sentences.json"
WEB_DATA = ROOT / "web" / "public" / "data" / "long_sentences.json"


def _payload() -> dict[str, object]:
    return json.loads(NATIVE_DATA.read_text(encoding="utf-8"))


def _sentence_core(item: dict[str, object]) -> dict[str, object]:
    return {
        key: item[key]
        for key in ("id", "source_number", "text", "source_pages")
    }


def test_checked_in_long_sentence_data_is_identical_and_complete():
    native_bytes = NATIVE_DATA.read_bytes()
    assert WEB_DATA.read_bytes() == native_bytes

    payload = json.loads(native_bytes)
    assert payload["schema"] == "gre-long-sentences"
    assert payload["version"] == 2
    assert payload["count"] == len(payload["sentences"]) == 131
    assert payload["source"] == {
        "title": "杨鹏阅读长难句",
        "file_name": "杨鹏阅读长难句(2).pdf",
        "file_sha256": (
            "50b594880839f5733cfb07304706d4ca93e691a025590b768b0de0c8534d6a02"
        ),
        "page_count": 44,
        "missing_source_numbers": [70],
        "notes_extraction": (
            "Embedded PDF Unicode text layer with rendered-page review"
        ),
        "notes_review": (
            "Windows Simplified Chinese OCR and 4x rendered-page spot checks"
        ),
        "notes_audit": {
            "coverage_percent": 100,
            "source_characters": 69704,
            "note_count": 578,
            "sentences_with_notes": 131,
            "minimum_notes_per_sentence": 1,
            "maximum_notes_per_sentence": 8,
        },
    }

    sentences = payload["sentences"]
    assert [item["id"] for item in sentences] == list(range(1, 132))
    assert [item["source_number"] for item in sentences] == [
        number for number in range(1, 133) if number != 70
    ]


def test_every_annotation_is_structured_nonempty_and_unicode_clean():
    sentences = _payload()["sentences"]
    all_notes = [note for sentence in sentences for note in sentence["notes"]]

    assert len(all_notes) == 578
    assert all(sentence["notes"] for sentence in sentences)
    assert min(len(sentence["notes"]) for sentence in sentences) == 1
    assert max(len(sentence["notes"]) for sentence in sentences) == 8
    assert Counter(note["label"] for note in all_notes) == {
        "译文": 131,
        "难度": 129,
        "难句类型": 129,
        "解释": 128,
        "意群训练": 50,
        "A": 3,
        "B": 3,
        "C": 2,
        "D": 1,
        "补充": 2,
    }

    for sentence in sentences:
        assert set(sentence) == {
            "id",
            "source_number",
            "text",
            "source_pages",
            "notes",
        }
        for note in sentence["notes"]:
            assert set(note) == {"label", "text"}
            assert isinstance(note["label"], str) and note["label"].strip()
            assert isinstance(note["text"], str) and note["text"].strip()
            assert "\ufffd" not in note["label"] + note["text"]
            assert "\x00" not in note["label"] + note["text"]
            assert "\n" not in note["text"] and "\r" not in note["text"]
            assert "  " not in note["text"]


def test_annotation_boundaries_and_special_source_layouts_are_preserved():
    by_source_number = {
        item["source_number"]: item for item in _payload()["sentences"]
    }

    assert by_source_number[1]["notes"][:3] == [
        {"label": "难度", "text": "（难度系数5，下同）"},
        {
            "label": "译文",
            "text": (
                "那种性别比例能在最大程度上增加一个个体所能拥有的后代数量，"
                "并因此能在最大程度上增加所传递到后代身上去的基因复制品的数量。"
            ),
        },
        {"label": "难句类型", "text": "倒装、省略"},
    ]
    assert [note["label"] for note in by_source_number[2]["notes"]] == [
        "难度",
        "难句类型",
        "译文",
        "解释",
        "A",
        "B",
        "C",
        "D",
    ]
    assert by_source_number[5]["notes"][1]["label"] == "难句类型"
    assert by_source_number[25]["notes"][1] == {
        "label": "补充",
        "text": "注意：bring A to B ——〉bring to B A",
    }
    assert by_source_number[45]["notes"][1]["text"].endswith(
        "（复杂修饰+插入+省略+倒装）"
    )
    assert by_source_number[119]["notes"] == [
        {
            "label": "译文",
            "text": (
                "现在，这已成为一个不争的事实：银河系要比迄今为止所想象的"
                "要来得远为浩瀚广阔，并具有远高得多的质量。（原书无此句）"
            ),
        }
    ]
    assert by_source_number[129]["notes"][0]["label"] == "译文"
    assert by_source_number[129]["notes"][0]["text"].endswith("(原书无此句)")
    assert by_source_number[132]["notes"][-1]["label"] == "解释"


def test_every_long_sentence_is_nonempty_clean_english_with_valid_pages():
    forbidden_fragments = (
        "译文",
        "难句类型",
        "解释",
        "意群训练",
        "难度系数",
        "GRE 和",
        "GMAT",
        "\ufffd",
        "\x00",
    )
    for item in _payload()["sentences"]:
        text = item["text"]
        pages = item["source_pages"]
        assert text == text.strip()
        assert len(text) >= 35
        assert "\n" not in text and "\r" not in text and "  " not in text
        assert not re.search(r"[\u3400-\u9fff]", text)
        assert not any(fragment in text for fragment in forbidden_fragments)
        assert re.search(r"[.?!][\"”]?$", text)
        assert pages == sorted(set(pages))
        assert pages and all(1 <= page <= 44 for page in pages)


def test_boundary_and_text_layer_repair_sentences_match_rendered_pdf():
    by_source_number = {
        item["source_number"]: item for item in _payload()["sentences"]
    }

    assert _sentence_core(by_source_number[1]) == {
        "id": 1,
        "source_number": 1,
        "text": (
            "That sex ratio will be favored which maximizes the number of "
            "descendants an individual will have and hence the number of gene "
            "copies transmitted."
        ),
        "source_pages": [1],
    }
    assert _sentence_core(by_source_number[27]) == {
        "id": 27,
        "source_number": 27,
        "text": (
            "The role those anthropologists ascribe to evolution is not of "
            "dictating the details of human behavior but one of imposing "
            "constraints—ways of feeling, thinking, and acting that \"come "
            "naturally\" in archetypal situations in any culture."
        ),
        "source_pages": [9],
    }
    assert by_source_number[62]["text"].startswith(
        "Many critics of Emily Bronte’s novel Wuthering Heights"
    )
    assert "the fact that many" in by_source_number[30]["text"]
    assert "(on Mars)" in by_source_number[80]["text"]
    assert "what manufacturers and servicing trades thought" in (
        by_source_number[100]["text"]
    )
    assert by_source_number[69]["id"] == 69
    assert by_source_number[69]["source_pages"] == [23]
    assert by_source_number[69]["text"].startswith(
        'Even the "radical" critiques of this mainstream research model'
    )
    assert by_source_number[71]["id"] == 70
    assert by_source_number[71]["source_pages"] == [24]
    assert by_source_number[71]["text"].startswith(
        "Open acknowledgement of the existence of women’s oppression"
    )
    assert 70 not in by_source_number

    assert _sentence_core(by_source_number[129]) == {
        "id": 128,
        "source_number": 129,
        "text": (
            "To measure them properly, monitoring equipment would have to be "
            "laid out on a grid at intervals of at most 50 kilometers, with "
            "sensors at each grid point lowered deep in the ocean and kept "
            "there for many months."
        ),
        "source_pages": [43],
    }
    assert _sentence_core(by_source_number[132]) == {
        "id": 131,
        "source_number": 132,
        "text": (
            "This doctrine has broadened the application of the Fourteenth "
            "Amendment to other, nonracial forms of discrimination, for while "
            "some justices have refused to find any legislative classification "
            "other than race to be constitutionally disfavored, most have been "
            "receptive to arguments that at least some nonracial "
            "discriminations, sexual discrimination in particular, are "
            '"suspect" and deserve this heightened scrutiny by the courts.'
        ),
        "source_pages": [43],
    }


def test_cross_page_source_locations_are_preserved():
    by_source_number = {
        item["source_number"]: item for item in _payload()["sentences"]
    }
    assert {
        number: by_source_number[number]["source_pages"]
        for number in (17, 67, 116, 121)
    } == {
        17: [5, 6],
        67: [22, 23],
        116: [39, 40],
        121: [40, 41],
    }
