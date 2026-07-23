from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy

from gre_vocab_app.domain import BrowseOrder, SessionSnapshot, StudyMode
from gre_vocab_app.ui.study_page import StudyPage


def snapshot(sample_word, **changes):
    values = dict(
        word=sample_word,
        index=0,
        total=105,
        mode=StudyMode.RECALL,
        order=BrowseOrder.SOURCE,
        answer_visible=False,
        star_rating=0,
        star_filter=None,
        list_key="list1",
        list_label="List 1",
        can_complete_round=False,
        at_start=True,
        at_end=False,
    )
    values.update(changes)
    return SessionSnapshot(**values)


def test_study_render_modes_navigation_and_position_context(qtbot, sample_word):
    page = StudyPage()
    qtbot.addWidget(page)
    page.show()
    page.render(snapshot(sample_word, index=8, at_start=False))
    assert page.position_label.text() == "List 1 · 9 / 105"
    assert page.recall_button.isChecked()
    assert not page.word_detail.is_revealed()
    assert page.previous_button.isEnabled()
    assert page.next_button.isEnabled()
    assert page.first_button.isEnabled()
    assert page.last_button.isEnabled()

    with qtbot.waitSignal(page.answerToggleRequested):
        page.word_detail.reveal_button.click()
    with qtbot.waitSignal(page.modeRequested) as mode:
        page.brief_button.click()
    assert mode.args == [StudyMode.BRIEF]


def test_list_boundary_buttons_emit_and_disable_at_edges(qtbot, sample_word):
    page = StudyPage()
    qtbot.addWidget(page)
    page.render(snapshot(sample_word, index=8, at_start=False, at_end=False))
    with qtbot.waitSignal(page.firstRequested):
        page.first_button.click()
    with qtbot.waitSignal(page.lastRequested):
        page.last_button.click()

    page.render(snapshot(sample_word, at_start=True, at_end=False))
    assert not page.first_button.isEnabled()
    page.render(snapshot(sample_word, index=104, at_start=False, at_end=True))
    assert not page.last_button.isEnabled()


def test_clicking_active_quiz_mode_does_not_emit_or_reset_answer(qtbot, sample_word):
    page = StudyPage()
    qtbot.addWidget(page)
    answered = snapshot(
        sample_word,
        mode=StudyMode.QUIZ,
        quiz_choices=("甲", "乙", "丙", "丁"),
        quiz_correct_index=2,
        quiz_selected_index=0,
    )
    page.render(answered)
    mode = QSignalSpy(page.modeRequested)
    page.quiz_button.click()
    assert mode.count() == 0
    assert page.word_detail._quiz_selected_index == 0


def test_quiz_auto_star_switches_are_available_only_in_quiz_mode(
    qtbot, sample_word
):
    page = StudyPage()
    qtbot.addWidget(page)
    page.show()
    page.render(snapshot(sample_word, mode=StudyMode.READING))
    assert page.quiz_automation_bar.isHidden()

    page.render(
        snapshot(
            sample_word,
            mode=StudyMode.QUIZ,
            quiz_choices=("甲", "乙", "丙", "丁"),
            quiz_correct_index=2,
        )
    )
    assert page.quiz_automation_bar.isVisible()
    with qtbot.waitSignal(page.quizWrongStarUpChanged) as wrong:
        page.quiz_wrong_star_up_checkbox.setChecked(True)
    assert wrong.args == [True]
    with qtbot.waitSignal(page.quizCorrectStarDownChanged) as correct:
        page.quiz_correct_star_down_checkbox.setChecked(True)
    assert correct.args == [True]
    page.set_quiz_star_adjustments(
        add_on_wrong=False,
        remove_on_correct=False,
    )
    assert not page.quiz_wrong_star_up_checkbox.isChecked()
    assert not page.quiz_correct_star_down_checkbox.isChecked()


def test_star_rating_is_zero_through_three_and_no_favorite_control(qtbot, sample_word):
    page = StudyPage()
    qtbot.addWidget(page)
    page.render(snapshot(sample_word, star_rating=3))
    assert page.star_button.text() == "★★★"
    with qtbot.waitSignal(page.starRatingRequested) as star:
        page.star_button.click()
    assert star.args == [0]
    assert "3 星后回到 0 星" in page.star_button.toolTip()
    assert not hasattr(page, "favorite_button")
    assert not hasattr(page, "favoriteRequested")


def test_end_of_full_list_becomes_explicit_finish_action(qtbot, sample_word):
    page = StudyPage()
    qtbot.addWidget(page)
    page.render(
        snapshot(
            sample_word,
            index=104,
            at_start=False,
            at_end=True,
            can_complete_round=True,
        )
    )
    assert page.next_button.text() == "完成本轮"
    assert page.next_button.isEnabled()
    with qtbot.waitSignal(page.finishRequested):
        page.next_button.click()

    page.render(
        snapshot(
            sample_word,
            total=1,
            at_end=True,
            star_filter=2,
            can_complete_round=False,
        )
    )
    assert page.next_button.text() == "下一词"
    assert not page.next_button.isEnabled()


def test_quiz_and_related_word_signals_are_forwarded(qtbot, sample_word):
    page = StudyPage()
    qtbot.addWidget(page)
    page.show()
    page.render(
        snapshot(
            sample_word,
            mode=StudyMode.QUIZ,
            quiz_choices=("甲", "乙", "丙", "丁"),
            quiz_correct_index=1,
        )
    )
    with qtbot.waitSignal(page.quizChoiceRequested) as answer:
        page.word_detail.quiz_buttons[0].click()
    assert answer.args == [0]

    with qtbot.waitSignal(page.relatedWordRequested) as related:
        page.word_detail.relatedWordRequested.emit(17)
    assert related.args == [17]


def test_keyboard_shortcuts_navigate_reveal_and_speak(qtbot, sample_word):
    page = StudyPage()
    qtbot.addWidget(page)
    page.show()
    page.render(snapshot(sample_word, at_start=False))
    page.setFocus()
    previous = QSignalSpy(page.previousRequested)
    next_word = QSignalSpy(page.nextRequested)
    reveal = QSignalSpy(page.answerToggleRequested)
    speech = QSignalSpy(page.speechRequested)
    qtbot.keyClick(page, Qt.Key_Left)
    qtbot.keyClick(page, Qt.Key_Right)
    qtbot.keyClick(page, Qt.Key_Space)
    qtbot.keyClick(page, Qt.Key_P)
    assert previous.count() == 1
    assert next_word.count() == 1
    assert reveal.count() == 1
    assert speech.at(0) == [sample_word.headword]


def test_editable_focus_keeps_native_space_and_unavailable_speech_is_disabled(
    qtbot, sample_word
):
    page = StudyPage()
    qtbot.addWidget(page)
    page.show()
    page.render(snapshot(sample_word))
    page.set_speech_available(False)
    assert not page.word_detail.speech_button.isEnabled()
    assert not page.speech_shortcut.isEnabled()

    page.word_detail.headword_label.setFocusPolicy(Qt.StrongFocus)
    page.word_detail.headword_label.setFocus()
    qtbot.waitUntil(page.word_detail.headword_label.hasFocus)
    with qtbot.assertNotEmitted(page.answerToggleRequested):
        qtbot.keyClick(page.word_detail.headword_label, Qt.Key_Space)
