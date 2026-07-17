from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gre_vocab_app.domain import WordEntry


class FavoritesPage(QWidget):
    searchRequested = Signal(str)
    wordSelected = Signal(object)
    favoriteRemoved = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("appSurface")
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 26, 32, 28)
        root.setSpacing(14)

        title = QLabel("生词本")
        title.setObjectName("pageTitle")
        subtitle = QLabel("集中复习你收藏的单词。")
        subtitle.setObjectName("muted")
        root.addWidget(title)
        root.addWidget(subtitle)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("筛选生词")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(
            lambda text: self.searchRequested.emit(text.strip())
        )
        root.addWidget(self.search_edit)

        self.empty_state = QLabel("还没有生词。学习时点击收藏，即可在这里复习。")
        self.empty_state.setObjectName("muted")
        self.empty_state.setAlignment(Qt.AlignCenter)
        self.empty_state.setWordWrap(True)
        root.addWidget(self.empty_state, 1)

        self.words_list = QListWidget()
        self.words_list.itemActivated.connect(self._emit_selected)
        self.words_list.currentItemChanged.connect(self._update_actions)
        root.addWidget(self.words_list, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.open_button = QPushButton("打开词条")
        self.open_button.setObjectName("primaryButton")
        self.remove_button = QPushButton("取消收藏")
        self.remove_button.setObjectName("dangerButton")
        self.open_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        self.open_button.clicked.connect(self._open_current)
        self.remove_button.clicked.connect(self._remove_current)
        actions.addWidget(self.open_button)
        actions.addWidget(self.remove_button)
        root.addLayout(actions)
        self.set_words([])

    def set_words(self, words: list[WordEntry]) -> None:
        self.words_list.clear()
        for word in words:
            summary = word.definition_zh or word.definition_en
            item = QListWidgetItem(f"{word.headword}    {summary}")
            item.setData(Qt.UserRole, word)
            item.setToolTip(summary)
            self.words_list.addItem(item)
        has_words = bool(words)
        self.empty_state.setVisible(not has_words)
        self.words_list.setVisible(has_words)
        self._update_actions()

    def _current_word(self) -> WordEntry | None:
        item = self.words_list.currentItem()
        return None if item is None else item.data(Qt.UserRole)

    def _update_actions(self, *_args: object) -> None:
        enabled = self._current_word() is not None
        self.open_button.setEnabled(enabled)
        self.remove_button.setEnabled(enabled)

    def _emit_selected(self, item: QListWidgetItem) -> None:
        word = item.data(Qt.UserRole)
        if word is not None:
            self.wordSelected.emit(word)

    def _open_current(self) -> None:
        word = self._current_word()
        if word is not None:
            self.wordSelected.emit(word)

    def _remove_current(self) -> None:
        word = self._current_word()
        if word is not None:
            self.favoriteRemoved.emit(word.id)
