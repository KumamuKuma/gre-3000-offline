from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QLineEdit

from gre_vocab_app.domain import BrowseOrder, SessionSnapshot, StudyMode
from gre_vocab_app.ui.study_page import StudyPage


def snapshot(sample_word, **changes):
    values = dict(
        word=sample_word,
        index=0,
        total=10,
        mode=StudyMode.RECALL,
        order=BrowseOrder.SOURCE,
        answer_visible=False,
        favorite=False,
        at_start=True,
        at_end=False,
    )
    values.update(changes)
    return SessionSnapshot(**values)


def test_study_mode_switch_does_not_emit_navigation(qtbot):
    page = StudyPage()
    qtbot.addWidget(page)
    next_spy = QSignalSpy(page.nextRequested)

    with qtbot.waitSignal(page.modeRequested) as mode_signal:
        page.recall_button.click()

    assert mode_signal.args == [StudyMode.RECALL]
    assert next_spy.count() == 0


def test_study_render_reveal_boundaries_and_keyboard_shortcuts(qtbot, sample_word):
    page = StudyPage()
    qtbot.addWidget(page)
    page.show()
    page.render(snapshot(sample_word))

    assert page.position_label.text() == "1 / 10"
    assert not page.previous_button.isEnabled()
    assert page.next_button.isEnabled()
    assert page.word_detail.meaning_panel.isHidden()

    with qtbot.waitSignal(page.answerToggleRequested):
        qtbot.keyClick(page, Qt.Key_Space)
    with qtbot.waitSignal(page.nextRequested):
        qtbot.keyClick(page, Qt.Key_Right)
    with qtbot.waitSignal(page.previousRequested):
        qtbot.keyClick(page, Qt.Key_Left)
    with qtbot.waitSignal(page.speechRequested) as speech:
        qtbot.keyClick(page, Qt.Key_P)
    assert speech.args == [sample_word.headword]
    with qtbot.waitSignal(page.favoriteRequested) as favorite:
        qtbot.keyClick(page, Qt.Key_S)
    assert favorite.args == [True]


def test_space_is_ignored_in_reading_mode_and_editable_focus(qtbot, sample_word):
    page = StudyPage()
    qtbot.addWidget(page)
    page.show()
    spy = QSignalSpy(page.answerToggleRequested)
    page.render(snapshot(sample_word, mode=StudyMode.READING))
    qtbot.keyClick(page, Qt.Key_Space)
    assert spy.count() == 0

    page.render(snapshot(sample_word, mode=StudyMode.RECALL))
    edit = QLineEdit(page)
    edit.show()
    edit.setFocus()
    qtbot.keyClick(edit, Qt.Key_Space)
    assert spy.count() == 0


def test_random_snapshot_exposes_reshuffle_and_end_boundary(qtbot, sample_word):
    page = StudyPage()
    qtbot.addWidget(page)
    page.show()
    page.render(
        snapshot(
            sample_word,
            index=9,
            order=BrowseOrder.RANDOM,
            at_start=False,
            at_end=True,
        )
    )
    assert page.reshuffle_button.isVisible()
    assert not page.next_button.isEnabled()
    with qtbot.waitSignal(page.reshuffleRequested):
        page.reshuffle_button.click()
