from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from gre_vocab_app.ui.word_note import WordNote, WordNoteDialog
from gre_vocab_app.domain import StudyMode
from gre_vocab_app.ui.word_detail import WordDetail


def test_notes_available_in_every_mode_and_literal_text(qtbot, sample_word):
    detail = WordDetail()
    qtbot.addWidget(detail)
    detail.show()
    detail.word_note.load_note = lambda word: "<b>联想</b>\n词根记忆" if word == sample_word.headword else ""
    for mode in StudyMode:
        detail.set_word(sample_word, mode=mode)
        assert detail.word_note.isVisible()
        assert detail.word_note.preview.text() == "<b>联想</b>\n词根记忆"
        assert detail.word_note.preview.textFormat() == Qt.PlainText
        assert not detail.word_note.preview.isVisible()
        assert not detail.word_note.edit_button.isVisible()
        detail.word_note.button.click()
        assert detail.word_note.preview.isVisible()
        assert detail.word_note.edit_button.isVisible()
        detail.word_note.refresh()
        assert detail.word_note.preview.isVisible()
        with qtbot.waitSignal(detail.word_note.editRequested) as signal:
            detail.word_note.edit_button.click()
        assert signal.args == [sample_word.headword]
        detail.word_note.button.click()
        assert not detail.word_note.preview.isVisible()

    detail.word_note.button.click()
    detail.word_note.set_word("another")
    assert not detail.word_note.preview.isVisible()
    with qtbot.waitSignal(detail.word_note.editRequested) as signal:
        detail.word_note.button.click()
    assert signal.args == ["another"]
    detail.word_note.set_word(sample_word.headword)
    assert not detail.word_note.preview.isVisible()
    detail.word_note.button.click()
    detail.hide()
    detail.show()
    assert not detail.word_note.preview.isVisible()
    assert detail.word_note.button.text() == "显示备注"


def test_editor_keeps_typing_keys_and_allows_delete(qtbot):
    dialog = WordNoteDialog("inevitable", "", None)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.editor.setFocus()
    qtbot.keyClicks(dialog.editor, "p space")
    qtbot.keyClick(dialog.editor, Qt.Key_Left)
    qtbot.keyClicks(dialog.editor, "!")
    assert dialog.editor.toPlainText() == "p spac!e"
    dialog.editor.setPlainText("字" * 4001)
    assert not dialog.buttons.button(QDialogButtonBox.Save).isEnabled()
    dialog.editor.clear()
    assert dialog.buttons.button(QDialogButtonBox.Save).isEnabled()
