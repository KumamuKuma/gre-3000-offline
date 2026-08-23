from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _word_forms(key: str, exchange: str) -> tuple[str, ...]:
    values = [key.lower().replace("’", "'")]
    recorded_markers = {"0", "d", "p", "i", "3", "s", "r", "t", "f"}
    for item in exchange.split("/"):
        marker, separator, value = item.partition(":")
        if marker not in recorded_markers:
            continue
        cleaned = value.lower().replace("’", "'").strip() if separator else ""
        if cleaned and re.fullmatch(r"[a-z][a-z' -]*", cleaned):
            values.append(cleaned)
    return tuple(dict.fromkeys(values))


def test_checked_in_click_dictionaries_are_identical_complete_version_two_data():
    native_bytes = (ROOT / "resources" / "click_dictionary.json").read_bytes()
    web_bytes = (
        ROOT / "web" / "public" / "data" / "click_dictionary.json"
    ).read_bytes()
    assert native_bytes == web_bytes

    payload = json.loads(native_bytes)
    assert payload["schema"] == "gre-click-dictionary"
    assert payload["version"] == 2
    assert payload["entry_count"] == len(payload["entries"]) == 12_060
    assert payload["target_count"] == 12_350
    assert payload["sources"] == [
        {"name": "ECDICT", "role": "词条与词性级中文汇总"},
        {"name": "Princeton WordNet 3.0", "role": "英文义项与例句"},
        {
            "name": "Chinese Open Wordnet 0.9",
            "role": "按 WordNet 3.0 synset 精确对应的中文同义词",
        },
        {
            "name": "项目内 COW 已审核修正",
            "role": "对高置信 COW 词义翻译错误的可追溯修正",
        },
    ]

    senses = [
        sense
        for entry in payload["entries"].values()
        for sense in entry["senses"]
    ]
    examples = [example for sense in senses for example in sense["examples"]]
    assert len(senses) == 33_291
    assert len(examples) == 38_282
    assert all(sense["translation"] or sense["definition"] for sense in senses)
    assert all(example["text"] and example["source"] for example in examples)
    assert sum(
        bool(sense["translation"] and sense["definition"])
        for sense in senses
    ) == 14_167
    assert sum(
        example["source"] == "Princeton WordNet 3.0"
        for example in examples
    ) == 20_608
    assert sum(
        example["source"] == "释义语境（非语料例句）"
        for example in examples
    ) == 17_674

    entries = payload["entries"]
    expected_curated_translations = {
        (
            "abstinence",
            "the trait of abstaining (especially from alcohol)",
        ): "戒酒；节制",
        (
            "abstinence",
            "act or practice of refraining from indulging an appetite",
        ): "节制；禁欲",
        ("angle", "move or proceed at an angle"): "斜向移动；转向",
        ("agree", "be agreeable or suitable"): "适合；相宜",
        ("abstain", "refrain from voting"): "弃权",
        ("diaper", "a fabric (usually cotton or linen) with a distinctive woven pattern of small repeated figures"): "菱形花纹布",
        ("apple", "native Eurasian tree widely cultivated in many varieties for its firm rounded edible fruits"): "苹果树",
        (
            "ashes",
            "strong elastic wood of any of various ash trees; used for furniture and tool handles and sporting goods such as baseball bats",
        ): "白蜡木",
        ("pounds", "the basic unit of money in Cyprus; equal to 100 cents"): "塞浦路斯镑",
        ("pounds", "the basic unit of money in Syria; equal to 100 piasters"): "叙利亚镑",
        ("decreasing", "music"): "渐弱的；渐慢的",
        ("amiable", "disposed to please"): "和蔼可亲的；友善的",
        (
            "affect",
            "the conscious subjective aspect of feeling or emotion",
        ): "情感；情绪",
        (
            "abundance",
            "(physics) the ratio of the number of atoms of a specific isotope of an element to the total number of isotopes present",
        ): "同位素丰度；同位素丰度比",
        ("accede", "take on duties or office"): "就任；承担（职务或职责）",
        (
            "articulate",
            "express or state clearly",
        ): "清晰表达；明确说明",
        ("philosophy", "the rational investigation of questions about existence and knowledge and ethics"): "哲学",
        (
            "nihilism",
            "complete denial of all established authority and institutions",
        ): "虚无主义；彻底否定既有权威和制度",
        (
            "nihilism",
            "a revolutionary doctrine that advocates destruction of the social system for its own sake",
        ): "虚无主义；主张摧毁现存社会制度的革命学说",
        (
            "forgo",
            "be earlier in time; go back further",
        ): "先于；早于（古义）",
        (
            "forgo",
            "lose (s.th.) or lose the right to (s.th.) by some error, offense, or crime",
        ): "因过失或违法而丧失（权利等）；被罚没",
        (
            "fathom",
            "(mining) a unit of volume (equal to 6 cubic feet) used in measuring bodies of ore",
        ): "（矿业）体积单位；立方英寻（6立方英尺）",
        (
            "filter",
            "an electrical device that alters the frequency spectrum of signals passing through it",
        ): "滤波器",
        (
            "dedicate",
            "open to public use, as of a highway, park, or building",
        ): "正式开放；启用（供公众使用）",
        (
            "tactless",
            "lacking or showing a lack of what is fitting and considerate in dealing with others",
        ): "不得体的；不机智的",
        (
            "slew",
            "(often followed by `of') a large number or amount or extent",
        ): "大量；许多；一连串",
        (
            "spate",
            "(often followed by `of') a large number or amount or extent",
        ): "大量；许多；一连串",
        (
            "obloquy",
            "state of disgrace resulting from public abuse",
        ): "耻辱；骂名；声名狼藉",
        (
            "opprobrium",
            "state of disgrace resulting from public abuse",
        ): "耻辱；骂名；声名狼藉",
        (
            "opprobrium",
            "a state of extreme dishonor",
        ): "奇耻大辱；极度耻辱",
        (
            "ammunition",
            "information that can be used to attack or defend a claim or argument or viewpoint",
        ): "论据；可用于攻防观点的信息",
        ("acts", "a manifestation of insincerity"): "装腔作势；虚伪的表现",
    }
    for (word, definition), translation in expected_curated_translations.items():
        matching = [
            sense
            for sense in entries[word]["senses"]
            if sense["definition"] == definition
        ]
        assert len(matching) == 1
        assert matching[0]["translation"] == translation

    assert entries["centralize"]["senses"][0]["translation"] == (
        "使集中；形成中心；把集中起来；集中，聚集；集结"
    )
    for key, entry in entries.items():
        for sense in entry["senses"]:
            lemmas = [
                value.strip()
                for value in sense["translation"].split("；")
                if value.strip()
            ]
            redundant = {
                part.strip()
                for lemma in lemmas
                for part in re.split(r"[，,]", lemma)
                if part.strip() != lemma and part.strip() in lemmas
            }
            assert not redundant, (key, sense["translation"], redundant)

    for contraction in ("can't", "i'd", "i'm", "won't"):
        senses_for_word = entries[contraction]["senses"]
        assert len(senses_for_word) == 1
        assert senses_for_word[0]["part_of_speech"] == ""
        assert senses_for_word[0]["definition"].startswith("A ")


def test_every_wordnet_example_contains_the_looked_up_word_or_recorded_form():
    payload = json.loads(
        (ROOT / "resources" / "click_dictionary.json").read_text(
            encoding="utf-8"
        )
    )
    for key, entry in payload["entries"].items():
        forms = _word_forms(key, entry.get("exchange", ""))
        for sense in entry["senses"]:
            for example in sense["examples"]:
                if example["source"] != "Princeton WordNet 3.0":
                    continue
                text = example["text"].lower().replace("’", "'")
                assert any(
                    re.search(
                        rf"(?<![a-z]){re.escape(form)}(?![a-z])",
                        text,
                    )
                    for form in forms
                ), (key, example["text"])


def test_dictionary_licenses_ship_for_native_and_web_distribution():
    for name in (
        "ECDICT-LICENSE.txt",
        "WORDNET-LICENSE.txt",
        "COW-LICENSE.txt",
    ):
        native = ROOT / "resources" / name
        web = ROOT / "web" / "public" / name
        assert native.is_file()
        assert web.is_file()
        assert native.read_text(encoding="utf-8").strip() == web.read_text(
            encoding="utf-8"
        ).strip()
