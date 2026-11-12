from datetime import datetime

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
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
    saveRequested = Signal(str, str)

    def __init__(self, parent=None, *, edit_only=False):
        super().__init__(parent)
        self.headword = ""
        self._edit_only = edit_only
        self.load_note = lambda _word: ""
        self.load_history = lambda _word: ()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.button = QPushButton("添加备注")
        self.button.setObjectName("outlineButton")
        self.button.setMinimumHeight(36)
        self.button.clicked.connect(self._toggle_note)
        self.edit_button = QPushButton("编辑备注")
        self.edit_button.setObjectName("outlineButton")
        self.edit_button.setMinimumHeight(36)
        self.edit_button.clicked.connect(self.begin_edit)
        self.button.setAutoDefault(False)
        self.edit_button.setAutoDefault(False)
        self.preview = QLabel()
        self.preview.setObjectName("notePreview")
        self.preview.setTextFormat(Qt.PlainText)
        self.preview.setWordWrap(True)
        self.preview.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        actions = QHBoxLayout()
        actions.addWidget(self.button)
        actions.addWidget(self.edit_button)
        actions.addStretch()
        self.actions = QWidget()
        actions.setContentsMargins(0, 0, 0, 0)
        self.actions.setLayout(actions)
        layout.addWidget(self.actions)
        layout.addWidget(self.preview)
        self.edit_panel = WordNoteEditor(show_headword=edit_only)
        self.edit_panel.saveRequested.connect(self._save_note)
        self.edit_panel.cancelRequested.connect(self.cancel_edit)
        layout.addWidget(self.edit_panel)
        self.edit_panel.hide()
        self.preview.hide()
        self.edit_button.hide()
        self.hide()

    def set_word(self, headword: str):
        if note_key(headword) != note_key(self.headword):
            self.edit_panel.hide()
            self.button.setChecked(False)
        self.headword = headword
        self.refresh()

    def refresh(self):
        text = self.load_note(self.headword) if self.headword else ""
        self.button.setCheckable(bool(text))
        if not text:
            self.button.setChecked(False)
        expanded = bool(text) and self.button.isChecked() and not self._edit_only and not self.editing
        self.button.setText(("收起备注" if expanded else "显示备注") if text else "添加备注")
        self.button.setAccessibleName(self.button.text())
        self.preview.setText(text)
        self.preview.setVisible(expanded)
        self.edit_button.setVisible(expanded)
        self.actions.setVisible(not self._edit_only and not self.editing)
        self.setVisible(bool(self.headword) and (not self._edit_only or self.editing))

    @property
    def editing(self):
        return not self.edit_panel.isHidden()

    def begin_edit(self):
        if not self.headword:
            return
        if not self.editing:
            self.edit_panel.set_note(self.headword, self.load_note(self.headword), self.load_history(self.headword))
            self.edit_panel.show()
            self.refresh()
        self.edit_panel.editor.setFocus()
        QTimer.singleShot(0, self, self._scroll_to_editor)

    def _scroll_to_editor(self):
        if not self.editing:
            return
        container = self.parentWidget()
        while container is not None:
            if isinstance(container, QScrollArea):
                container.ensureWidgetVisible(self.edit_panel, 0, 8)
                return
            container = container.parentWidget()

    def cancel_edit(self):
        self.edit_panel.hide()
        self.refresh()

    def _save_note(self, text):
        self.edit_panel.hide()
        self.saveRequested.emit(self.headword, text)
        if not self._edit_only and self.load_note(self.headword):
            self.button.setCheckable(True)
            self.button.setChecked(True)
        self.refresh()

    def _toggle_note(self):
        if self.load_note(self.headword):
            self.refresh()
        else:
            self.begin_edit()

    def hideEvent(self, event):
        self.edit_panel.hide()
        self.button.setChecked(False)
        self.preview.hide()
        self.edit_button.hide()
        super().hideEvent(event)

    def showEvent(self, event):
        self.refresh()
        super().showEvent(event)


class WordNoteEditor(QWidget):
    saveRequested = Signal(str)
    cancelRequested = Signal()

    def __init__(self, parent=None, *, show_headword=False):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.title = QLabel()
        self.title.setObjectName("sectionTitle")
        self.title.setTextFormat(Qt.PlainText)
        self.title.setVisible(show_headword)
        layout.addWidget(self.title)
        self.editor = _NoteEditor()
        self.editor.setObjectName("noteEditor")
        self.editor.setAccessibleName("单词备注")
        self.editor.setFixedHeight(128)
        layout.addWidget(self.editor)
        self.history_row = QWidget()
        history_layout = QHBoxLayout(self.history_row)
        history_layout.setContentsMargins(0, 0, 0, 0)
        self.history = QComboBox()
        self.history.setAccessibleName("备注历史")
        self.history.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.history.setMinimumContentsLength(12)
        self.restore_button = QPushButton("载入此版本")
        self.restore_button.setAutoDefault(False)
        self.restore_button.clicked.connect(self._choose_history)
        self.history.currentIndexChanged.connect(lambda index: self.restore_button.setEnabled(index > 0))
        history_layout.addWidget(self.history, 1)
        history_layout.addWidget(self.restore_button)
        layout.addWidget(self.history_row)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        save_button = self.buttons.button(QDialogButtonBox.Save)
        save_button.setText("保存备注")
        save_button.setObjectName("primaryButton")
        self.buttons.button(QDialogButtonBox.Cancel).setText("取消")
        for button in self.buttons.buttons():
            button.setAutoDefault(False)
        self.buttons.accepted.connect(lambda: self.saveRequested.emit(self.editor.toPlainText()))
        self.buttons.rejected.connect(self.cancelRequested)
        layout.addWidget(self.buttons)
        self.editor.textChanged.connect(self._validate)

    def set_note(self, headword, text, history=()):
        self.title.setText(headword)
        self.editor.setPlainText(text)
        self.history.clear()
        self.history.addItem("选择历史备注")
        for version in history:
            when = datetime.fromisoformat(version.archived_at).astimezone()
            summary = " ".join(version.value.split())[:30]
            self.history.addItem(f"{when:%Y-%m-%d %H:%M:%S} · {summary}", version.value)
        self.history_row.setVisible(bool(history))
        self._validate()

    def _choose_history(self):
        text = self.history.currentData()
        if text is not None:
            self.editor.selectAll()
            self.editor.insertPlainText(text)
            self.editor.setFocus()

    def _validate(self):
        valid = len(self.editor.toPlainText()) <= MAX_NOTE_LENGTH
        message = "" if valid else f"备注最多可保存 {MAX_NOTE_LENGTH} 字。"
        self.editor.setToolTip(message)
        self.editor.setAccessibleDescription(message)
        self.buttons.button(QDialogButtonBox.Save).setEnabled(valid)
