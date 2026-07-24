from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy

from gre_vocab_app.domain import RelatedWord, RootFamily, StudyMode
from gre_vocab_app.ui.word_detail import WordDetail


def test_recall_starts_hidden_and_reveals_only_brief_meaning(qtbot, sample_word):
    detail = WordDetail()
    qtbot.addWidget(detail)
    detail.show()
    detail.set_word(
        sample_word,
        mode=StudyMode.RECALL,
        answer_visible=False,
    )

    assert detail.meaning_panel.isHidden()
    assert detail.headword_label.text() == sample_word.headword
    assert detail.reveal_button.isVisible()
    assert detail.reveal_button.text() == "点击显示简义"
    assert detail.synonyms_label.isHidden()
    assert detail.example_en_label.isHidden()

    detail.set_revealed(True)
    assert detail.meaning_panel.isVisible()
    assert sample_word.definition_zh in detail.definition_zh_label.text()
    assert detail.synonyms_label.isHidden()
    assert detail.example_en_label.isHidden()

    with qtbot.waitSignal(detail.speechRequested) as signal:
        detail.speech_button.click()
    assert signal.args == [sample_word.headword]


def test_reading_shows_full_content_and_brief_hides_optional_sections(
    qtbot, sample_word
):
    detail = WordDetail()
    qtbot.addWidget(detail)
    detail.show()
    word = replace(
        sample_word,
        synonyms="unavoidable, preordained",
        example_en="The outcome was inevitable.",
        example_zh="这个结果无法避免。",
    )

    detail.set_word(word, mode=StudyMode.READING)
    assert detail.meaning_panel.isVisible()
    assert detail.synonyms_label.isVisible()
    assert detail.example_en_label.isVisible()
    assert detail.example_zh_label.isVisible()
    assert detail.example_speech_button.isVisible()
    assert detail.example_speech_button.isEnabled()
    assert detail.reveal_button.isHidden()

    with qtbot.waitSignal(detail.speechRequested) as signal:
        detail.example_speech_button.click()
    assert signal.args == [word.example_en]

    detail.set_word(word, mode=StudyMode.BRIEF)
    assert detail.meaning_panel.isVisible()
    assert detail.definition_label.isVisible()
    assert detail.definition_zh_label.isVisible()
    assert detail.synonyms_title.isHidden()
    assert detail.synonyms_label.isHidden()
    assert detail.example_title.isHidden()
    assert detail.example_en_label.isHidden()
    assert detail.example_zh_label.isHidden()
    assert detail.example_speech_button.isHidden()
    assert detail.reveal_button.isHidden()


def test_quiz_hides_answer_until_selection_then_marks_result(qtbot, sample_word):
    detail = WordDetail()
    qtbot.addWidget(detail)
    detail.show()
    choices = ("毫不避免的", "无害的", "短暂的", "隐秘的")
    detail.set_word(
        sample_word,
        mode=StudyMode.QUIZ,
        quiz_choices=choices,
        quiz_correct_index=2,
        quiz_selected_index=None,
    )

    assert detail.meaning_panel.isHidden()
    assert detail.quiz_panel.isVisible()
    assert detail.quiz_feedback_label.isHidden()
    assert [button.text() for button in detail.quiz_buttons] == list(choices)
    assert all(button.objectName() == "" for button in detail.quiz_buttons)
    assert all(button.focusPolicy() & Qt.StrongFocus for button in detail.quiz_buttons)

    choice_spy = QSignalSpy(detail.quizChoiceRequested)
    detail.quiz_buttons[1].click()
    assert choice_spy.count() == 1
    assert choice_spy.at(0) == [1]
    assert detail.quiz_buttons[1].text().startswith("✗ 你的选择")
    assert detail.quiz_buttons[2].text().startswith("✓ 正确答案")
    assert "回答错误" in detail.quiz_feedback_label.text()

    detail.set_word(
        sample_word,
        mode=StudyMode.QUIZ,
        quiz_choices=choices,
        quiz_correct_index=2,
        quiz_selected_index=1,
    )
    assert detail.quiz_buttons[1].text().startswith("✗ 你的选择")
    assert detail.quiz_buttons[1].objectName() == "dangerButton"
    assert detail.quiz_buttons[2].text().startswith("✓ 正确答案")
    assert detail.quiz_buttons[2].objectName() == "primaryButton"
    assert "回答错误" in detail.quiz_feedback_label.text()
    assert all(not button.isEnabled() for button in detail.quiz_buttons)
    detail.quiz_buttons[0].click()
    assert choice_spy.count() == 1

    detail.set_word(
        sample_word,
        mode=StudyMode.QUIZ,
        quiz_choices=choices,
        quiz_correct_index=2,
        quiz_selected_index=2,
    )
    assert detail.quiz_buttons[2].text().startswith("✓ 回答正确")
    assert detail.quiz_feedback_label.text() == "回答正确"


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
    detail.set_word(first, mode=StudyMode.READING)
    assert detail.synonyms_label.text()
    assert detail.example_en_label.wordWrap()
    qtbot.waitUntil(lambda: detail.scroll_area.verticalScrollBar().maximum() > 0)

    detail.set_word(
        replace(sample_word, synonyms="", example_en="", example_zh=""),
        mode=StudyMode.READING,
    )
    assert detail.synonyms_label.text() == ""
    assert detail.synonyms_label.isHidden()
    assert detail.example_en_label.text() == ""
    assert detail.example_en_label.isHidden()
    assert detail.example_speech_button.isHidden()
    assert not detail.example_speech_button.isEnabled()
    assert detail.definition_label.textInteractionFlags() & Qt.TextSelectableByMouse


def test_word_detail_speech_button_respects_backend_availability(qtbot, sample_word):
    detail = WordDetail()
    qtbot.addWidget(detail)
    assert hasattr(detail, "set_speech_available")

    detail.set_speech_available(False)
    detail.set_word(sample_word, mode=StudyMode.READING)
    assert not detail.speech_button.isEnabled()
    assert not detail.example_speech_button.isEnabled()

    detail.set_speech_available(True)
    assert detail.speech_button.isEnabled()
    assert detail.example_speech_button.isEnabled()


def test_related_words_render_below_answer_and_do_not_leak_recall_or_quiz(
    qtbot, sample_word
):
    detail = WordDetail()
    qtbot.addWidget(detail)
    detail.show()
    family = (
        RootFamily(
            "cred（相信）",
            (RelatedWord(2, "credible", "可信的"),),
        ),
    )
    lookalikes = (RelatedWord(3, "casual", "随意的"),)
    equivalents = (RelatedWord(4, "inevitable", "不可避免的"),)
    detail.set_word(
        sample_word,
        mode=StudyMode.RECALL,
        root_families=family,
        lookalikes=lookalikes,
        equivalents=equivalents,
        in_machine7=True,
    )
    assert detail.machine7_badge.isVisible()
    assert detail.root_panel.isHidden()
    assert detail.lookalike_panel.isHidden()
    assert detail.equivalent_panel.isHidden()
    detail.set_revealed(True)
    assert detail.root_panel.isVisible()
    assert detail.lookalike_panel.isVisible()
    assert detail.equivalent_panel.isVisible()

    buttons = detail.root_panel.findChildren(type(detail.speech_button))
    relation_button = next(
        button for button in buttons if "credible" in button.text()
    )
    with qtbot.waitSignal(detail.relatedWordRequested) as selected:
        relation_button.click()
    assert selected.args == [2]

    equivalent_button = next(
        button
        for button in detail.equivalent_panel.findChildren(
            type(detail.speech_button)
        )
        if "inevitable" in button.text()
    )
    with qtbot.waitSignal(detail.relatedWordRequested) as equivalent_selected:
        equivalent_button.click()
    assert equivalent_selected.args == [4]

    detail.set_word(
        sample_word,
        mode=StudyMode.QUIZ,
        quiz_choices=("甲", "乙", "丙", "丁"),
        quiz_correct_index=0,
        root_families=family,
        lookalikes=lookalikes,
        equivalents=equivalents,
    )
    assert detail.root_panel.isHidden()
    assert detail.equivalent_panel.isHidden()
    detail.quiz_buttons[1].click()
    assert detail.root_panel.isVisible()
    assert detail.equivalent_panel.isVisible()
