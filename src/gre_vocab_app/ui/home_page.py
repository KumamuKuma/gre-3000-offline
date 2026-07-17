from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
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


class HomePage(QWidget):
    searchRequested = Signal(str)
    continueRequested = Signal()
    sourceRequested = Signal()
    randomRequested = Signal()
    favoriteRequested = Signal()
    wordSelected = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("appSurface")
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 26, 32, 28)
        root.setSpacing(16)

        eyebrow = QLabel("GRE OFFLINE")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("GRE 3000 词离线版")
        title.setObjectName("pageTitle")
        subtitle = QLabel("按自己的节奏连续学习，所有进度只保存在这台电脑。")
        subtitle.setObjectName("muted")
        root.addWidget(eyebrow)
        root.addWidget(title)
        root.addWidget(subtitle)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索英文单词（Ctrl+F）")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_changed)
        root.addWidget(self.search_edit)

        stats = QHBoxLayout()
        self.total_value = self._stat_card(stats, "词库总数")
        self.seen_value = self._stat_card(stats, "已浏览")
        self.favorites_value = self._stat_card(stats, "生词")
        root.addLayout(stats)

        actions = QGridLayout()
        actions.setSpacing(10)
        self.continue_button = self._action("继续学习", primary=True)
        self.source_button = self._action("顺序学习")
        self.random_button = self._action("随机学习")
        self.favorites_button = self._action("生词本")
        actions.addWidget(self.continue_button, 0, 0)
        actions.addWidget(self.source_button, 0, 1)
        actions.addWidget(self.random_button, 1, 0)
        actions.addWidget(self.favorites_button, 1, 1)
        root.addLayout(actions)
        self.continue_button.clicked.connect(self.continueRequested.emit)
        self.source_button.clicked.connect(self.sourceRequested.emit)
        self.random_button.clicked.connect(self.randomRequested.emit)
        self.favorites_button.clicked.connect(self.favoriteRequested.emit)

        results_title = QLabel("搜索结果")
        results_title.setObjectName("sectionTitle")
        root.addWidget(results_title)
        self.no_results_label = QLabel("没有找到匹配的单词")
        self.no_results_label.setObjectName("muted")
        self.no_results_label.setAlignment(Qt.AlignCenter)
        self.no_results_label.hide()
        root.addWidget(self.no_results_label)
        self.results = QListWidget()
        self.results.setAlternatingRowColors(False)
        self.results.itemActivated.connect(self._emit_word)
        self.results.hide()
        root.addWidget(self.results, 1)

    @staticmethod
    def _action(text: str, *, primary: bool = False) -> QPushButton:
        button = QPushButton(text)
        button.setMinimumHeight(46)
        if primary:
            button.setObjectName("primaryButton")
        return button

    @staticmethod
    def _stat_card(layout: QHBoxLayout, label_text: str) -> QLabel:
        card = QFrame(objectName="card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 13)
        label = QLabel(label_text)
        label.setObjectName("muted")
        value = QLabel("0")
        value.setObjectName("statValue")
        card_layout.addWidget(label)
        card_layout.addWidget(value)
        layout.addWidget(card)
        return value

    def set_stats(self, total: int, seen: int, favorites: int) -> None:
        self.total_value.setText(f"{total:,}")
        self.seen_value.setText(f"{seen:,}")
        self.favorites_value.setText(f"{favorites:,}")

    def set_results(self, words: list[WordEntry]) -> None:
        self.results.clear()
        for word in words:
            summary = word.definition_zh or word.definition_en
            item = QListWidgetItem(f"{word.headword}    {summary}")
            item.setData(Qt.UserRole, word)
            item.setToolTip(summary)
            self.results.addItem(item)
        has_results = bool(words)
        self.results.setVisible(has_results)
        self.no_results_label.setVisible(
            not has_results and bool(self.search_edit.text().strip())
        )

    def _on_search_changed(self, text: str) -> None:
        self.results.clear()
        self.results.hide()
        self.no_results_label.hide()
        self.searchRequested.emit(text.strip())

    def focus_search(self) -> None:
        self.search_edit.setFocus(Qt.ShortcutFocusReason)

    def _emit_word(self, item: QListWidgetItem) -> None:
        word = item.data(Qt.UserRole)
        if word is not None:
            self.wordSelected.emit(word)
