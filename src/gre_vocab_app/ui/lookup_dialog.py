from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gre_vocab_app.services.dictionary import LookupResult

from .lookup_label import LookupLabel


class LookupDialog(QDialog):
    translateRequested = Signal(str)
    openWordRequested = Signal(int)
    lookupRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("内置词典与翻译")
        self.setModal(False)
        self.resize(570, 620)
        self._result: LookupResult | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        self.query_label = QLabel()
        self.query_label.setObjectName("lookupHeadword")
        self.phonetic_label = QLabel()
        self.phonetic_label.setObjectName("phonetic")
        title_box.addWidget(self.query_label)
        title_box.addWidget(self.phonetic_label)
        header.addLayout(title_box, 1)
        self.source_label = QLabel()
        self.source_label.setObjectName("sourceBadge")
        header.addWidget(self.source_label)
        root.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        details = QVBoxLayout(content)
        details.setContentsMargins(0, 0, 0, 0)
        details.setSpacing(12)
        self.translation_label = self._detail_label("lookupTranslation")
        self.definition_label = self._lookup_detail_label()
        self.exchange_label = self._detail_label("muted")
        self.phrases_title = QLabel("常用词组")
        self.phrases_title.setObjectName("sectionTitle")
        self.phrases_label = self._lookup_detail_label()
        self.online_title = QLabel("选中内容翻译")
        self.online_title.setObjectName("sectionTitle")
        self.online_label = self._detail_label("lookupOnline")
        details.addWidget(self.translation_label)
        details.addWidget(self.definition_label)
        details.addWidget(self.exchange_label)
        details.addWidget(self.phrases_title)
        details.addWidget(self.phrases_label)
        details.addWidget(self.online_title)
        details.addWidget(self.online_label)
        details.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        privacy = QLabel(
            "点词释义来自本地；只有点击“联网翻译”时，当前文字才会发送给第三方 "
            "MyMemory 翻译服务。"
        )
        privacy.setObjectName("sectionHint")
        privacy.setWordWrap(True)
        root.addWidget(privacy)
        actions = QHBoxLayout()
        self.open_button = QPushButton("打开 GRE 词条")
        self.translate_button = QPushButton("联网翻译")
        self.translate_button.setObjectName("primaryButton")
        self.copy_button = QPushButton("复制结果")
        close_button = QPushButton("关闭")
        actions.addWidget(self.open_button)
        actions.addStretch(1)
        actions.addWidget(self.translate_button)
        actions.addWidget(self.copy_button)
        actions.addWidget(close_button)
        root.addLayout(actions)

        self.open_button.clicked.connect(self._open_word)
        self.translate_button.clicked.connect(self._translate)
        self.copy_button.clicked.connect(self._copy)
        close_button.clicked.connect(self.close)

    @staticmethod
    def _detail_label(object_name: str = "") -> QLabel:
        label = QLabel()
        if object_name:
            label.setObjectName(object_name)
        label.setWordWrap(True)
        label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        return label

    def _lookup_detail_label(self) -> LookupLabel:
        label = LookupLabel()
        label.lookupRequested.connect(self.lookupRequested.emit)
        return label

    def show_result(self, result: LookupResult) -> None:
        self._result = result
        self.query_label.setText(result.headword or result.query)
        self.phonetic_label.setText(result.phonetic)
        self.phonetic_label.setVisible(bool(result.phonetic))
        self.source_label.setText(result.source)
        self.translation_label.setText(
            result.translation or "内置词典暂未收录，可使用联网翻译。"
        )
        self.translation_label.setProperty("missing", not result.found)
        self.definition_label.set_lookup_text(result.definition)
        self.definition_label.setVisible(bool(result.definition))
        self.exchange_label.setText(
            f"词形变化：{result.exchange}" if result.exchange else ""
        )
        self.exchange_label.setVisible(bool(result.exchange))
        phrase_text = "\n\n".join(
            f"{item.phrase}\n{item.translation}" for item in result.phrases
        )
        self.phrases_title.setVisible(bool(phrase_text))
        self.phrases_label.set_lookup_text(phrase_text)
        self.phrases_label.setVisible(bool(phrase_text))
        self.online_title.hide()
        self.online_label.clear()
        self.online_label.hide()
        self.open_button.setVisible(result.gre_word_id is not None)
        self.translate_button.setText("联网翻译")
        self.translate_button.setEnabled(bool(result.query.strip()))
        self.show()
        self.raise_()
        self.activateWindow()

    def set_translating(self) -> None:
        self.translate_button.setText("正在翻译…")
        self.translate_button.setEnabled(False)
        self.online_title.show()
        self.online_label.setText("正在连接翻译服务…")
        self.online_label.show()

    def set_online_translation(self, value: str) -> None:
        self.online_title.show()
        self.online_label.setText(value)
        self.online_label.show()
        self.translate_button.setText("重新翻译")
        self.translate_button.setEnabled(True)

    def set_translation_error(self, message: str) -> None:
        self.online_title.show()
        self.online_label.setText(f"翻译失败：{message}")
        self.online_label.show()
        self.translate_button.setText("重试")
        self.translate_button.setEnabled(True)

    def _translate(self) -> None:
        if self._result is not None:
            self.translateRequested.emit(self._result.query)

    def _open_word(self) -> None:
        if self._result is not None and self._result.gre_word_id is not None:
            self.openWordRequested.emit(self._result.gre_word_id)

    def _copy(self) -> None:
        sections = [
            self.query_label.text(),
            self.phonetic_label.text(),
            self.translation_label.text(),
            self.definition_label.text(),
            self.phrases_label.text(),
            self.online_label.text(),
        ]
        QGuiApplication.clipboard().setText(
            "\n".join(section for section in sections if section)
        )
