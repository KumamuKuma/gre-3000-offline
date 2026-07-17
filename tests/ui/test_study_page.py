import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton

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


def test_recall_reveal_control_supports_mouse_and_focused_space(qtbot, sample_word):
    page = StudyPage()
    qtbot.addWidget(page)
    page.show()
    page.render(snapshot(sample_word, mode=StudyMode.RECALL, answer_visible=False))

    assert page.word_detail.reveal_button.isVisible()
    assert page.word_detail.reveal_button.text() == "点击显示释义"
    assert page.word_detail.reveal_button.focusPolicy() & Qt.StrongFocus
    with qtbot.waitSignal(page.answerToggleRequested):
        qtbot.mouseClick(page.word_detail.reveal_button, Qt.LeftButton)
    with qtbot.waitSignal(page.answerToggleRequested):
        page.word_detail.reveal_button.setFocus()
        qtbot.keyClick(page.word_detail.reveal_button, Qt.Key_Space)


def test_reading_space_keeps_normal_focused_button_behavior(qtbot, sample_word):
    page = StudyPage()
    qtbot.addWidget(page)
    page.show()
    page.render(snapshot(sample_word, mode=StudyMode.READING))
    ordinary = QPushButton("ordinary", page)
    ordinary.show()
    ordinary.setFocus()
    clicks = QSignalSpy(ordinary.clicked)
    answer = QSignalSpy(page.answerToggleRequested)

    qtbot.keyClick(ordinary, Qt.Key_Space)

    assert clicks.count() == 1
    assert answer.count() == 0


@pytest.mark.parametrize(
    "button_name",
    ("recall_button", "favorite_button", "next_button"),
)
def test_recall_space_on_an_ordinary_button_only_reveals_answer(
    qtbot, sample_word, button_name
):
    page = StudyPage()
    qtbot.addWidget(page)
    page.show()
    page.render(snapshot(sample_word, mode=StudyMode.RECALL))
    button = getattr(page, button_name)
    button.setFocus()
    qtbot.waitUntil(lambda: button.hasFocus())
    clicks = QSignalSpy(button.clicked)
    answers = QSignalSpy(page.answerToggleRequested)

    qtbot.keyClick(button, Qt.Key_Space)

    assert answers.count() == 1
    assert clicks.count() == 0


def test_keyboard_selectable_text_receives_study_shortcut_keys(qtbot, sample_word):
    class KeyRecordingLabel(QLabel):
        def __init__(self, parent):
            super().__init__("selectable", parent)
            self.received_keys = []

        def keyPressEvent(self, event):
            self.received_keys.append(event.key())
            super().keyPressEvent(event)

    page = StudyPage()
    qtbot.addWidget(page)
    page.show()
    page.render(snapshot(sample_word, mode=StudyMode.RECALL, at_start=False))
    label = KeyRecordingLabel(page)
    label.setTextInteractionFlags(
        Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
    )
    label.setFocusPolicy(Qt.StrongFocus)
    label.show()
    label.setFocus()
    qtbot.waitUntil(lambda: label.hasFocus())
    signal_spies = (
        QSignalSpy(page.previousRequested),
        QSignalSpy(page.nextRequested),
        QSignalSpy(page.speechRequested),
        QSignalSpy(page.favoriteRequested),
        QSignalSpy(page.answerToggleRequested),
    )

    for key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_P, Qt.Key_S, Qt.Key_Space):
        counts_before = tuple(spy.count() for spy in signal_spies)
        label.received_keys.clear()

        qtbot.keyClick(label, key)

        assert label.received_keys == [key]
        assert tuple(spy.count() for spy in signal_spies) == counts_before


def test_unavailable_speech_disables_button_and_p_shortcut(qtbot, sample_word):
    page = StudyPage()
    qtbot.addWidget(page)
    page.show()
    assert hasattr(page, "set_speech_available")
    page.set_speech_available(False)
    page.render(snapshot(sample_word))
    speech = QSignalSpy(page.speechRequested)

    assert not page.word_detail.speech_button.isEnabled()
    assert not page.speech_shortcut.isEnabled()
    qtbot.keyClick(page, Qt.Key_P)
    assert speech.count() == 0

    page.set_speech_available(True)
    assert page.word_detail.speech_button.isEnabled()
    assert page.speech_shortcut.isEnabled()
