from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gre_vocab_app.word_notes import MAX_NOTE_LENGTH, note_key


class _NoteEditor(QPlainTextEdit):
    def event(self, event):
        handled = super().event(event)
        if event.type() == QEvent.InputMethodQuery:
            # Qt reports these in viewport coordinates. IMEs need widget
            # coordinates, including the border and stylesheet padding.
            # Keep other query values in Qt to preserve its native MIME data.
            for query in (Qt.ImCursorRectangle, Qt.ImAnchorRectangle):
                if event.queries() & query:
                    event.setValue(
                        query, event.value(query).translated(self.viewport().pos())
                    )
        return handled


class WordNote(QWidget):
    editRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.headword = ""
        self.load_note = lambda _word: ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.button = QPushButton("添加备注")
        self.button.setObjectName("outlineButton")
        self.button.setMinimumHeight(36)
        self.button.clicked.connect(self._toggle_note)
        self.edit_button = QPushButton("编辑备注")
        self.edit_button.setObjectName("outlineButton")
        self.edit_button.setMinimumHeight(36)
        self.edit_button.clicked.connect(lambda: self.editRequested.emit(self.headword))
        self.preview = QLabel()
        self.preview.setObjectName("notePreview")
        self.preview.setTextFormat(Qt.PlainText)
        self.preview.setWordWrap(True)
        self.preview.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        actions = QHBoxLayout()
        actions.addWidget(self.button)
        actions.addWidget(self.edit_button)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addWidget(self.preview)
        self.preview.hide()
        self.edit_button.hide()
        self.hide()

    def set_word(self, headword: str):
        if note_key(headword) != note_key(self.headword):
            self.button.setChecked(False)
        self.headword = headword
        self.refresh()

    def refresh(self):
        text = self.load_note(self.headword) if self.headword else ""
        self.button.setCheckable(bool(text))
        if not text:
            self.button.setChecked(False)
        expanded = bool(text) and self.button.isChecked()
        self.button.setText(("收起备注" if expanded else "显示备注") if text else "添加备注")
        self.button.setAccessibleName(self.button.text())
        self.preview.setText(text)
        self.preview.setVisible(expanded)
        self.edit_button.setVisible(expanded)
        self.setVisible(bool(self.headword))

    def _toggle_note(self):
        if self.load_note(self.headword):
            self.refresh()
        else:
            self.editRequested.emit(self.headword)

    def hideEvent(self, event):
        self.button.setChecked(False)
        self.preview.hide()
        self.edit_button.hide()
        super().hideEvent(event)

    def showEvent(self, event):
        self.refresh()
        super().showEvent(event)


class WordNoteDialog(QDialog):
    def __init__(self, headword: str, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{headword} · 我的备注")
        self.resize(540, 360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)
        title = QLabel(headword)
        title.setObjectName("noteTitle")
        title.setTextFormat(Qt.PlainText)
        layout.addWidget(title)
        self.editor = _NoteEditor()
        self.editor.setObjectName("noteEditor")
        self.editor.setAccessibleName("单词备注")
        self.editor.setPlainText(text)
        layout.addWidget(self.editor, 1)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        save_button = self.buttons.button(QDialogButtonBox.Save)
        save_button.setText("保存备注")
        save_button.setObjectName("primaryButton")
        self.buttons.button(QDialogButtonBox.Cancel).setText("取消")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.editor.textChanged.connect(self._validate)
        self.editor.setFocus()
        self._validate()

    def _validate(self):
        valid = len(self.editor.toPlainText()) <= MAX_NOTE_LENGTH
        message = "" if valid else f"备注最多可保存 {MAX_NOTE_LENGTH} 字。"
        self.editor.setToolTip(message)
        self.editor.setAccessibleDescription(message)
        self.buttons.button(QDialogButtonBox.Save).setEnabled(valid)
