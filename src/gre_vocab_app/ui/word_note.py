from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from gre_vocab_app.word_notes import MAX_NOTE_LENGTH


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
        self.button.clicked.connect(lambda: self.editRequested.emit(self.headword))
        self.preview = QLabel()
        self.preview.setTextFormat(Qt.PlainText)
        self.preview.setWordWrap(True)
        self.preview.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        layout.addWidget(self.button, 0, Qt.AlignLeft)
        layout.addWidget(self.preview)
        self.hide()

    def set_word(self, headword: str):
        self.headword = headword
        self.refresh()

    def refresh(self):
        text = self.load_note(self.headword) if self.headword else ""
        self.button.setText("编辑备注" if text else "添加备注")
        self.preview.setText(text)
        self.preview.setVisible(bool(text))
        self.setVisible(bool(self.headword))


class WordNoteDialog(QDialog):
    def __init__(self, headword: str, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{headword} · 我的备注")
        self.resize(540, 360)
        layout = QVBoxLayout(self)
        title = QLabel(headword)
        title.setTextFormat(Qt.PlainText)
        layout.addWidget(title)
        self.editor = QPlainTextEdit()
        self.editor.setAccessibleName("单词备注")
        self.editor.setPlaceholderText("写下联想、词根拆解或自己的记忆方法……")
        self.editor.setPlainText(text)
        layout.addWidget(self.editor, 1)
        footer = QHBoxLayout()
        self.count = QLabel()
        footer.addWidget(self.count)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Save).setText("保存备注")
        self.buttons.button(QDialogButtonBox.Cancel).setText("取消")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        footer.addWidget(self.buttons)
        layout.addLayout(footer)
        self.editor.textChanged.connect(self._validate)
        self._validate()

    def _validate(self):
        length = len(self.editor.toPlainText())
        self.count.setText(f"{length} / {MAX_NOTE_LENGTH} 字 · 清空并保存可删除备注")
        self.buttons.button(QDialogButtonBox.Save).setEnabled(length <= MAX_NOTE_LENGTH)
