from PySide6.QtGui import QGuiApplication

from gre_vocab_app.services.dictionary import (
    DictionarySense,
    LookupResult,
    SenseExample,
)
from gre_vocab_app.ui.lookup_dialog import LookupDialog


def test_gre_lookup_also_shows_full_offline_entry_and_sense_examples(qtbot):
    dialog = LookupDialog()
    qtbot.addWidget(dialog)
    result = LookupResult(
        query="inevitable",
        normalized="inevitable",
        kind="word",
        source="GRE 3000 已审核词库 + ECDICT 离线英汉词典",
        headword="inevitable",
        phonetic="[ɪnˈevɪtəbl]",
        translation="必然的",
        definition="adj. sure to happen",
        gre_word_id=1,
        gre_translation="必然的",
        gre_definition="adj. sure to happen",
        gre_example_en="It was inevitable.",
        gre_example_zh="这是不可避免的。",
        offline_translation="a. 不可避免的, 必然的\n[法] 无法规避的",
        offline_definition="a. incapable of being avoided",
        senses=(
            DictionarySense(
                part_of_speech="adj.",
                translation="不可避免的, 必然的",
                definition="incapable of being avoided",
                examples=(
                    SenseExample(
                        "The inevitable result finally arrived.",
                        "Princeton WordNet 3.0",
                    ),
                ),
            ),
        ),
    )

    dialog.show_result(result)

    assert dialog.primary_title.text() == "GRE 3000 已审核释义"
    assert dialog.translation_label.text() == "必然的"
    assert dialog.gre_example_label.text() == (
        "It was inevitable.\n这是不可避免的。"
    )
    assert dialog.offline_title.isVisible()
    assert dialog.offline_translation_label.text() == "[法] 无法规避的"
    assert dialog.senses_label.text().count("不可避免的, 必然的") == 1
    assert "The inevitable result finally arrived." in (
        dialog.senses_label.text()
    )
    assert "Princeton WordNet 3.0" in dialog.senses_label.text()


def test_offline_only_lookup_uses_offline_entry_as_primary_section(qtbot):
    dialog = LookupDialog()
    qtbot.addWidget(dialog)
    result = LookupResult(
        query="work",
        normalized="work",
        kind="word",
        source="ECDICT 离线英汉词典",
        headword="work",
        translation="n. 工作",
        offline_translation="n. 工作",
        senses=(
            DictionarySense(
                part_of_speech="n.",
                translation="工作",
                definition="activity involving effort",
                examples=(
                    SenseExample(
                        'In this context, "work" means activity involving effort.',
                        "释义语境（非语料例句）",
                    ),
                ),
            ),
        ),
    )

    dialog.show_result(result)

    assert dialog.primary_title.text() == "ECDICT 离线英汉词典 · 全部义项"
    assert dialog.translation_label.text() == ""
    assert not dialog.translation_label.isVisible()
    assert dialog.senses_label.text().count("工作") == 1
    assert not dialog.offline_title.isVisible()
    assert dialog.senses_title.isVisible()

    dialog.copy_button.click()
    copied = QGuiApplication.clipboard().text()
    assert copied.splitlines().count("工作") == 1


def test_repeated_sense_translation_is_shown_once_without_losing_details(qtbot):
    dialog = LookupDialog()
    qtbot.addWidget(dialog)
    repeated_translation = "使服从, 压制, 减弱, 抑制, 克制"
    result = LookupResult(
        query="subdue",
        normalized="subdue",
        kind="word",
        source="ECDICT 离线英汉词典",
        headword="subdue",
        translation=f"vt. {repeated_translation}",
        offline_translation=f"vt. {repeated_translation}",
        senses=tuple(
            DictionarySense(
                part_of_speech="v.",
                translation=repeated_translation,
                definition=definition,
                examples=(SenseExample(example, "Princeton WordNet 3.0"),),
            )
            for definition, example in (
                ("put down by force", "The army subdued the rebellion."),
                ("make less intense", "The lights subdued the room."),
                ("hold within limits", "She subdued her anger."),
            )
        ),
    )

    dialog.show_result(result)

    assert dialog.senses_label.text().count(repeated_translation) == 1
    assert dialog.senses_label.text().count("英文释义：") == 3
    for expected in (
        "put down by force",
        "make less intense",
        "hold within limits",
        "The army subdued the rebellion.",
        "The lights subdued the room.",
        "She subdued her anger.",
    ):
        assert expected in dialog.senses_label.text()

    dialog.copy_button.click()
    assert QGuiApplication.clipboard().text().count(repeated_translation) == 1


def test_duplicate_non_summary_translation_is_rendered_on_first_sense_only(qtbot):
    dialog = LookupDialog()
    qtbot.addWidget(dialog)
    senses = (
        DictionarySense(
            "adj.",
            "额外的",
            "more than needed",
            (SenseExample("Extra time was allowed.", "source"),),
        ),
        DictionarySense(
            "adj.",
            "额外的",
            "added to an existing amount",
            (SenseExample("She paid an extra fee.", "source"),),
        ),
        DictionarySense(
            "adj.",
            "不同的",
            "not the same",
            (SenseExample("They chose a different route.", "source"),),
        ),
    )

    displayed = dialog._senses_for_display(senses)

    assert [translation for _sense, translation in displayed] == [
        "额外的",
        "",
        "不同的",
    ]


def test_sense_without_chinese_still_shows_part_definition_and_example(qtbot):
    dialog = LookupDialog()
    qtbot.addWidget(dialog)
    result = LookupResult(
        query="temper",
        normalized="temper",
        kind="word",
        source="ECDICT 离线英汉词典",
        headword="temper",
        senses=(
            DictionarySense(
                part_of_speech="v.",
                translation="",
                definition="harden by reheating and cooling",
                examples=(
                    SenseExample(
                        "The smith tempered the steel.",
                        "Princeton WordNet 3.0",
                    ),
                ),
            ),
        ),
    )

    dialog.show_result(result)

    sense_text = dialog.senses_label.text()
    assert sense_text.startswith("1. v.")
    assert "英文释义：harden by reheating and cooling" in sense_text
    assert "The smith tempered the steel." in sense_text
