import pytest

from PySide6.QtCore import Qt
from PySide6.QtGui import QInputMethodEvent, QInputMethodQueryEvent, QTextCursor
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLabel

from gre_vocab_app.ui.theme import APP_STYLESHEET
from gre_vocab_app.ui.word_note import WordNoteEditor
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
        detail.word_note.edit_button.click()
        assert detail.word_note.edit_panel.isVisible()
        assert detail.word_note.edit_panel.editor.toPlainText() == "<b>联想</b>\n词根记忆"
        detail.word_note.edit_panel.buttons.button(QDialogButtonBox.Cancel).click()
        detail.word_note.button.click()
        assert not detail.word_note.preview.isVisible()

    detail.word_note.button.click()
    detail.word_note.set_word("another")
    assert not detail.word_note.preview.isVisible()
    detail.word_note.button.click()
    assert detail.word_note.edit_panel.isVisible()
    assert not detail.word_note.edit_panel.editor.toPlainText()
    detail.word_note.set_word(sample_word.headword)
    assert detail.word_note.edit_panel.isHidden()
    assert not detail.word_note.preview.isVisible()
    detail.word_note.button.click()
    detail.hide()
    detail.show()
    assert not detail.word_note.preview.isVisible()
    assert detail.word_note.button.text() == "显示备注"


def test_editor_keeps_typing_keys_and_allows_delete(qtbot):
    dialog = WordNoteEditor(show_headword=True)
    dialog.set_note("inevitable", "")
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.editor.placeholderText() == ""
    assert [label.text() for label in dialog.findChildren(QLabel)] == ["inevitable"]
    dialog.editor.setFocus()
    qtbot.keyClicks(dialog.editor, "p space")
    qtbot.keyClick(dialog.editor, Qt.Key_Left)
    qtbot.keyClicks(dialog.editor, "!")
    assert dialog.editor.toPlainText() == "p spac!e"
    dialog.editor.setPlainText("字" * 4001)
    assert not dialog.buttons.button(QDialogButtonBox.Save).isEnabled()
    dialog.editor.clear()
    assert dialog.buttons.button(QDialogButtonBox.Save).isEnabled()


@pytest.mark.parametrize("zoom", [0, 3])
@pytest.mark.parametrize(
    "text",
    ["", "中文备注\n第二行", "\n".join(f"第 {i} 行中文备注" for i in range(60))],
)
def test_ime_rectangles_match_the_padded_editor_after_scrolling(qtbot, text, zoom):
    dialog = WordNoteEditor()
    dialog.set_note("inevitable", text)
    qtbot.addWidget(dialog)
    editor = dialog.editor
    editor.setStyleSheet(APP_STYLESHEET)
    editor.zoomIn(zoom)
    dialog.show()
    editor.moveCursor(QTextCursor.End)
    editor.ensureCursorVisible()
    QApplication.processEvents()
    assert editor.viewport().pos().y() > editor.frameWidth() / 2

    event = QInputMethodQueryEvent(Qt.ImCursorRectangle | Qt.ImAnchorRectangle)
    QApplication.sendEvent(editor, event)
    caret = editor.cursorRect()
    caret.moveTopLeft(editor.viewport().mapTo(editor, caret.topLeft()))
    for query in (Qt.ImCursorRectangle, Qt.ImAnchorRectangle):
        assert event.value(query).toRect() == caret


def test_ime_preedit_and_selection_keep_their_position_and_text(qtbot):
    dialog = WordNoteEditor()
    dialog.set_note("inevitable", "中文备注")
    qtbot.addWidget(dialog)
    editor = dialog.editor
    editor.setStyleSheet(APP_STYLESHEET)
    dialog.show()
    editor.moveCursor(QTextCursor.End)
    editor.setFocus()
    QApplication.processEvents()

    preedit = QInputMethodEvent(
        "zhongwen",
        [QInputMethodEvent.Attribute(QInputMethodEvent.Cursor, 3, 1, None)],
    )
    QApplication.sendEvent(editor, preedit)
    event = QInputMethodQueryEvent(
        Qt.ImCursorRectangle | Qt.ImCursorPosition | Qt.ImSurroundingText
    )
    QApplication.sendEvent(editor, event)
    expected = editor.cursorRect().translated(editor.viewport().pos())
    assert event.value(Qt.ImCursorRectangle).toRect() == expected
    assert event.value(Qt.ImCursorPosition) == len("中文备注")
    assert event.value(Qt.ImSurroundingText) == "中文备注"
    assert editor.toPlainText() == "中文备注"

    commit = QInputMethodEvent()
    commit.setCommitString("中文")
    QApplication.sendEvent(editor, commit)
    assert editor.toPlainText() == "中文备注中文"
    cursor = editor.textCursor()
    cursor.setPosition(1)
    cursor.setPosition(4, QTextCursor.KeepAnchor)
    editor.setTextCursor(cursor)
    event = QInputMethodQueryEvent(Qt.ImQueryAll)
    QApplication.sendEvent(editor, event)
    anchor = editor.textCursor()
    anchor.setPosition(anchor.anchor())
    expected = editor.cursorRect(anchor).translated(editor.viewport().pos())
    assert event.value(Qt.ImAnchorRectangle).toRect() == expected
    assert editor.textCursor().selectedText() == "文备注"
