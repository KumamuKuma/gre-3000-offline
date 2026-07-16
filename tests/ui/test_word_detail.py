from dataclasses import replace

from PySide6.QtCore import Qt

from gre_vocab_app.ui.word_detail import WordDetail


def test_word_detail_hides_reveals_and_emits_speech(qtbot, sample_word):
    detail = WordDetail()
    qtbot.addWidget(detail)
    detail.show()
    detail.set_word(sample_word, reveal=False)

    assert detail.meaning_panel.isHidden()
    assert detail.headword_label.text() == sample_word.headword

    detail.set_revealed(True)
    assert detail.meaning_panel.isVisible()
    assert sample_word.definition_zh in detail.definition_zh_label.text()

    with qtbot.waitSignal(detail.speechRequested) as signal:
        detail.speech_button.click()
    assert signal.args == [sample_word.headword]


def test_word_detail_clears_stale_optional_fields_and_supports_long_text(
    qtbot, sample_word
):
    detail = WordDetail()
    qtbot.addWidget(detail)
    detail.resize(420, 220)
    detail.show()
    first = replace(
        sample_word,
        synonyms="unavoidable, preordained, ineluctable",
        example_en="A very long example " * 20,
        example_zh="很长的例句" * 20,
    )
    detail.set_word(first, reveal=True)
    assert detail.synonyms_label.text()
    assert detail.example_en_label.wordWrap()
    qtbot.waitUntil(lambda: detail.scroll_area.verticalScrollBar().maximum() > 0)

    detail.set_word(
        replace(sample_word, synonyms="", example_en="", example_zh=""),
        reveal=True,
    )
    assert detail.synonyms_label.text() == ""
    assert detail.synonyms_label.isHidden()
    assert detail.example_en_label.text() == ""
    assert detail.example_en_label.isHidden()
    assert detail.definition_label.textInteractionFlags() & Qt.TextSelectableByMouse
