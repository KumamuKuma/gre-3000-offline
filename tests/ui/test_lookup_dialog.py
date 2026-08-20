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
    assert dialog.offline_translation_label.text() == (
        "a. 不可避免的, 必然的\n[法] 无法规避的"
    )
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
    assert dialog.translation_label.text() == "n. 工作"
    assert not dialog.offline_title.isVisible()
    assert dialog.senses_title.isVisible()

    dialog.copy_button.click()
    copied = QGuiApplication.clipboard().text()
    assert copied.splitlines().count("n. 工作") == 1
