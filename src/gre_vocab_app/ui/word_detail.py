from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gre_vocab_app.domain import WordEntry


class WordDetail(QWidget):
    speechRequested = Signal(str)
    revealRequested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._word: WordEntry | None = None
        self._revealed = True
        self._speech_available = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        root = QVBoxLayout(content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)
        root.setSizeConstraint(QLayout.SetMinAndMaxSize)

        word_card = QWidget(objectName="wordCard")
        word_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        word_layout = QVBoxLayout(word_card)
        word_layout.setContentsMargins(24, 20, 24, 20)
        word_layout.setSpacing(8)
        title_row = QHBoxLayout()
        self.headword_label = self._label(object_name="headword")
        self.headword_label.setAccessibleName("单词")
        title_row.addWidget(self.headword_label, 1)
        self.speech_button = QPushButton("朗读")
        self.speech_button.setAccessibleName("朗读当前单词")
        self.speech_button.setEnabled(False)
        self.speech_button.clicked.connect(self._request_speech)
        title_row.addWidget(self.speech_button)
        word_layout.addLayout(title_row)
        self.phonetic_label = self._label(object_name="phonetic")
        word_layout.addWidget(self.phonetic_label)
        root.addWidget(word_card)

        self.reveal_button = QPushButton("点击显示释义")
        self.reveal_button.setAccessibleName("显示或隐藏释义")
        self.reveal_button.setFocusPolicy(Qt.StrongFocus)
        self.reveal_button.clicked.connect(self.revealRequested.emit)
        self.reveal_button.hide()
        root.addWidget(self.reveal_button)

        self.meaning_panel = QWidget(objectName="meaningPanel")
        self.meaning_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        meaning_layout = QVBoxLayout(self.meaning_panel)
        meaning_layout.setContentsMargins(24, 20, 24, 22)
        meaning_layout.setSpacing(8)

        self.definition_label = self._label(object_name="definition")
        self.definition_zh_label = self._label()
        meaning_layout.addWidget(self.definition_label)
        meaning_layout.addWidget(self.definition_zh_label)

        self.synonyms_title = self._section_title("近义词")
        self.synonyms_label = self._label()
        meaning_layout.addSpacing(5)
        meaning_layout.addWidget(self.synonyms_title)
        meaning_layout.addWidget(self.synonyms_label)

        self.example_title = self._section_title("例句")
        self.example_en_label = self._label()
        self.example_zh_label = self._label(object_name="muted")
        meaning_layout.addSpacing(5)
        meaning_layout.addWidget(self.example_title)
        meaning_layout.addWidget(self.example_en_label)
        meaning_layout.addWidget(self.example_zh_label)
        root.addWidget(self.meaning_panel)
        root.addStretch(1)
        self.scroll_area.setWidget(content)
        outer.addWidget(self.scroll_area)

    @staticmethod
    def _label(*, object_name: str = "") -> QLabel:
        label = QLabel()
        if object_name:
            label.setObjectName(object_name)
        label.setWordWrap(True)
        label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        return label

    @classmethod
    def _section_title(cls, text: str) -> QLabel:
        label = cls._label(object_name="sectionTitle")
        label.setText(text)
        return label

    def set_word(self, word: WordEntry, reveal: bool, *, recall: bool = False) -> None:
        self._word = word
        for label in (
            self.headword_label,
            self.phonetic_label,
            self.definition_label,
            self.definition_zh_label,
            self.synonyms_label,
            self.example_en_label,
            self.example_zh_label,
        ):
            label.clear()

        self.headword_label.setText(word.headword)
        self.phonetic_label.setText(word.phonetic)
        self.definition_label.setText(word.definition_en)
        self.definition_zh_label.setText(word.definition_zh)
        self.synonyms_label.setText(word.synonyms)
        self.example_en_label.setText(word.example_en)
        self.example_zh_label.setText(word.example_zh)

        self.phonetic_label.setVisible(bool(word.phonetic))
        self.definition_label.setVisible(bool(word.definition_en))
        self.definition_zh_label.setVisible(bool(word.definition_zh))
        has_synonyms = bool(word.synonyms)
        self.synonyms_title.setVisible(has_synonyms)
        self.synonyms_label.setVisible(has_synonyms)
        has_example = bool(word.example_en or word.example_zh)
        self.example_title.setVisible(has_example)
        self.example_en_label.setVisible(bool(word.example_en))
        self.example_zh_label.setVisible(bool(word.example_zh))
        self.speech_button.setEnabled(
            self._speech_available and bool(word.headword)
        )
        self.reveal_button.setVisible(bool(recall))
        self.set_revealed(reveal)

    def set_revealed(self, revealed: bool) -> None:
        self._revealed = bool(revealed)
        self.meaning_panel.setVisible(self._revealed)
        self.reveal_button.setText(
            "隐藏释义" if self._revealed else "点击显示释义"
        )

    def is_revealed(self) -> bool:
        return self._revealed

    def set_speech_available(self, available: bool) -> None:
        self._speech_available = bool(available)
        self.speech_button.setEnabled(
            self._speech_available
            and self._word is not None
            and bool(self._word.headword)
        )

    def _request_speech(self) -> None:
        if (
            self._speech_available
            and self._word is not None
            and self._word.headword
        ):
            self.speechRequested.emit(self._word.headword)
