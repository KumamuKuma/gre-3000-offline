from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gre_vocab_app.services.long_sentences import LongSentence

from .lookup_label import LookupLabel


class LongSentencePage(QWidget):
    """Focused one-sentence-per-page reader with clickable English words."""

    backRequested = Signal()
    lookupRequested = Signal(str)
    selectionTranslationRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("appSurface")
        self._sentences: tuple[LongSentence, ...] = ()
        self._index = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(38, 28, 38, 30)
        root.setSpacing(18)

        header = QFrame(objectName="studyHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(21, 17, 21, 17)
        header_layout.setSpacing(18)
        copy = QVBoxLayout()
        copy.setSpacing(4)
        eyebrow = QLabel("SENTENCE READING · OFFLINE")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("杨鹏阅读长难句")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "一页一句精读；点击任意英文单词优先查看离线释义，"
            "未收录词可主动联网翻译。"
        )
        subtitle.setObjectName("sectionHint")
        subtitle.setWordWrap(True)
        copy.addWidget(eyebrow)
        copy.addWidget(title)
        copy.addWidget(subtitle)
        header_layout.addLayout(copy, 1)
        self.position_label = QLabel("0 / 0")
        self.position_label.setObjectName("positionPill")
        self.position_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.position_label, 0, Qt.AlignTop)
        root.addWidget(header)

        self.reader = QScrollArea()
        self.reader.setObjectName("longSentenceReader")
        self.reader.setWidgetResizable(True)
        card = QFrame(objectName="longSentenceCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(34, 30, 34, 30)
        card_layout.setSpacing(18)
        self.source_label = QLabel("原书句号与页码")
        self.source_label.setObjectName("sourceBadge")
        self.source_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.source_label, 0, Qt.AlignLeft)
        card_layout.addStretch(1)
        self.sentence_label = LookupLabel()
        self.sentence_label.setObjectName("longSentenceText")
        self.sentence_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.sentence_label.setMinimumHeight(190)
        self.sentence_label.setToolTip(
            "点击单词优先查看离线释义；未收录词可联网翻译；"
            "拖动选择可翻译整段文字"
        )
        self.sentence_label.lookupRequested.connect(self.lookupRequested.emit)
        self.sentence_label.selectionTranslationRequested.connect(
            self.selectionTranslationRequested.emit
        )
        card_layout.addWidget(self.sentence_label)
        card_layout.addStretch(1)
        self.reader.setWidget(card)
        self.reader.hide()
        root.addWidget(self.reader, 1)

        self.empty_state = QLabel("正在准备长难句内容……")
        self.empty_state.setObjectName("emptyState")
        self.empty_state.setAlignment(Qt.AlignCenter)
        self.empty_state.setWordWrap(True)
        root.addWidget(self.empty_state, 1)

        navigation = QFrame(objectName="navigationBar")
        navigation_layout = QHBoxLayout(navigation)
        navigation_layout.setContentsMargins(14, 12, 14, 12)
        navigation_layout.setSpacing(10)
        self.back_button = QPushButton("回到首页")
        self.back_button.setObjectName("backButton")
        self.back_button.clicked.connect(self.backRequested.emit)
        navigation_layout.addWidget(self.back_button)
        navigation_layout.addStretch(1)
        shortcut_hint = QLabel("← / → 切换句子")
        shortcut_hint.setObjectName("shortcutBadge")
        navigation_layout.addWidget(shortcut_hint)
        self.previous_button = QPushButton("上一句")
        self.next_button = QPushButton("下一句")
        self.next_button.setObjectName("primaryButton")
        self.previous_button.clicked.connect(self.previous)
        self.next_button.clicked.connect(self.next)
        navigation_layout.addWidget(self.previous_button)
        navigation_layout.addWidget(self.next_button)
        root.addWidget(navigation)

        self.previous_shortcut = self._shortcut(Qt.Key_Left, self.previous)
        self.next_shortcut = self._shortcut(Qt.Key_Right, self.next)
        application = QApplication.instance()
        if application is not None:
            application.focusChanged.connect(self._sync_shortcuts)
        for child in self.findChildren(QWidget):
            child.installEventFilter(self)
        self._render()

    def _shortcut(self, key: Qt.Key, callback) -> QShortcut:
        shortcut = QShortcut(QKeySequence(key), self)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        shortcut.activated.connect(callback)
        return shortcut

    def set_sentences(self, sentences: Sequence[LongSentence]) -> None:
        values = tuple(sentences)
        if any(not isinstance(sentence, LongSentence) for sentence in values):
            raise ValueError("sentences must contain LongSentence values")
        self._sentences = values
        self._index = 0
        self.empty_state.setText("这份资料暂时没有可显示的长难句。")
        self._render()

    def set_error(self, message: str) -> None:
        self._sentences = ()
        self._index = 0
        self.empty_state.setText(message.strip() or "长难句内容暂时无法读取。")
        self._render()

    def current_sentence(self) -> LongSentence | None:
        if not self._sentences:
            return None
        return self._sentences[self._index]

    def previous(self) -> None:
        if self._sentences and not self._focus_blocks_navigation():
            self._index = max(0, self._index - 1)
            self._render()

    def next(self) -> None:
        if self._sentences and not self._focus_blocks_navigation():
            self._index = min(len(self._sentences) - 1, self._index + 1)
            self._render()

    def eventFilter(self, watched, event) -> bool:
        if (
            event.type() == QEvent.KeyPress
            and event.key() in (Qt.Key_Left, Qt.Key_Right)
            and event.modifiers() == Qt.NoModifier
            and not self._focus_blocks_navigation()
        ):
            if event.key() == Qt.Key_Left:
                self.previous()
            else:
                self.next()
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def _focus_blocks_navigation(self) -> bool:
        focus = QApplication.focusWidget()
        return (
            focus is not None
            and self.isAncestorOf(focus)
            and isinstance(
                focus,
                (
                    QLineEdit,
                    QTextEdit,
                    QPlainTextEdit,
                    QAbstractSpinBox,
                    QComboBox,
                ),
            )
        )

    def _sync_shortcuts(self, *_focus_widgets: QWidget | None) -> None:
        enabled = bool(self._sentences) and not self._focus_blocks_navigation()
        self.previous_shortcut.setEnabled(enabled)
        self.next_shortcut.setEnabled(enabled)

    def _render(self) -> None:
        sentence = self.current_sentence()
        total = len(self._sentences)
        if sentence is None:
            self.position_label.setText("0 / 0")
            self.reader.hide()
            self.empty_state.show()
            self.previous_button.setEnabled(False)
            self.next_button.setEnabled(False)
            self._sync_shortcuts()
            return

        self.position_label.setText(f"{self._index + 1:,} / {total:,}")
        pages = "、".join(str(page) for page in sentence.source_pages)
        page_label = "页" if len(sentence.source_pages) == 1 else "页（跨页）"
        self.source_label.setText(
            f"原书第 {sentence.source_number} 句 · PDF 第 {pages} {page_label}"
        )
        self.sentence_label.set_lookup_text(sentence.text)
        self.reader.show()
        self.empty_state.hide()
        self.previous_button.setEnabled(self._index > 0)
        self.next_button.setEnabled(self._index + 1 < total)
        self._sync_shortcuts()
