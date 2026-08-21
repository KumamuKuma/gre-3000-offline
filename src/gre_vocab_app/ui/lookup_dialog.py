from __future__ import annotations

import re
import unicodedata

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

from gre_vocab_app.services.dictionary import DictionarySense, LookupResult

from .lookup_label import LookupLabel


_TRANSLATION_PART_OF_SPEECH = re.compile(
    r"^(?:(?:n|v|vt|vi|a|adj|ad|adv|prep|conj|pron|num|art|int|aux|abbr)\.)\s*",
    re.IGNORECASE,
)


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
        self.primary_title = QLabel()
        self.primary_title.setObjectName("sectionTitle")
        self.translation_label = self._detail_label("lookupTranslation")
        self.definition_label = self._lookup_detail_label()
        self.gre_example_title = QLabel("GRE 原书例句")
        self.gre_example_title.setObjectName("sectionTitle")
        self.gre_example_label = self._lookup_detail_label()
        self.offline_title = QLabel("ECDICT 离线英汉词典 · 全部义项")
        self.offline_title.setObjectName("sectionTitle")
        self.offline_translation_label = self._detail_label(
            "lookupTranslation"
        )
        self.senses_title = QLabel("逐义项例句与语境提示")
        self.senses_title.setObjectName("sectionTitle")
        self.senses_label = self._lookup_detail_label()
        self.exchange_label = self._detail_label("muted")
        self.phrases_title = QLabel("常用词组")
        self.phrases_title.setObjectName("sectionTitle")
        self.phrases_label = self._lookup_detail_label()
        self.online_title = QLabel("选中内容翻译")
        self.online_title.setObjectName("sectionTitle")
        self.online_label = self._detail_label("lookupOnline")
        details.addWidget(self.primary_title)
        details.addWidget(self.translation_label)
        details.addWidget(self.definition_label)
        details.addWidget(self.gre_example_title)
        details.addWidget(self.gre_example_label)
        details.addWidget(self.offline_title)
        details.addWidget(self.offline_translation_label)
        details.addWidget(self.senses_title)
        details.addWidget(self.senses_label)
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
        has_gre = bool(result.gre_translation or result.gre_definition)
        has_offline = bool(result.offline_translation or result.senses)
        displayed_senses = self._senses_for_display(result.senses)
        displayed_offline_translation = self._summary_for_display(
            result.offline_translation,
            displayed_senses,
        )
        if has_gre:
            self.primary_title.setText("GRE 3000 已审核释义")
            primary_translation = result.gre_translation
            primary_definition = result.gre_definition
        elif has_offline:
            self.primary_title.setText("ECDICT 离线英汉词典 · 全部义项")
            primary_translation = displayed_offline_translation
            primary_definition = ""
        else:
            self.primary_title.setText("查询结果")
            primary_translation = "内置词典暂未收录，可使用联网翻译。"
            primary_definition = ""
        self.translation_label.setText(primary_translation)
        self.translation_label.setProperty("missing", not result.found)
        self.translation_label.setVisible(bool(primary_translation))
        self.definition_label.set_lookup_text(primary_definition)
        self.definition_label.setVisible(bool(primary_definition))
        gre_example = "\n".join(
            value
            for value in (result.gre_example_en, result.gre_example_zh)
            if value
        )
        self.gre_example_title.setVisible(bool(gre_example))
        self.gre_example_label.set_lookup_text(gre_example)
        self.gre_example_label.setVisible(bool(gre_example))
        show_separate_offline = has_gre and has_offline
        self.offline_title.setVisible(show_separate_offline)
        self.offline_translation_label.setText(displayed_offline_translation)
        self.offline_translation_label.setVisible(
            show_separate_offline and bool(displayed_offline_translation)
        )
        sense_text = "\n\n".join(
            self._sense_text(index, sense, display_translation)
            for index, (sense, display_translation) in enumerate(
                displayed_senses,
                start=1,
            )
        )
        self.senses_title.setVisible(bool(sense_text))
        self.senses_label.set_lookup_text(sense_text)
        self.senses_label.setVisible(bool(sense_text))
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
            self.gre_example_label.text(),
            (
                self.offline_translation_label.text()
                if not self.offline_translation_label.isHidden()
                else ""
            ),
            self.senses_label.text(),
            self.phrases_label.text(),
            self.online_label.text(),
        ]
        QGuiApplication.clipboard().setText(
            "\n".join(section for section in sections if section)
        )

    @staticmethod
    def _translation_key(value: str) -> str:
        lines = (
            _TRANSLATION_PART_OF_SPEECH.sub("", line.strip()).strip()
            for line in unicodedata.normalize("NFKC", value).splitlines()
        )
        compact = "\n".join(line for line in lines if line)
        compact = re.sub(r"\s+", " ", compact)
        compact = re.sub(r"\s*([,;:])\s*", r"\1", compact)
        return compact.casefold()

    @classmethod
    def _senses_for_display(
        cls,
        senses: tuple[DictionarySense, ...],
    ) -> tuple[tuple[DictionarySense, str], ...]:
        seen_translations: set[str] = set()
        displayed: list[tuple[DictionarySense, str]] = []
        for sense in senses:
            key = cls._translation_key(sense.translation)
            display_translation = (
                sense.translation.strip()
                if key and key not in seen_translations
                else ""
            )
            if key:
                seen_translations.add(key)
            displayed.append((sense, display_translation))
        return tuple(displayed)

    @classmethod
    def _summary_for_display(
        cls,
        summary: str,
        displayed_senses: tuple[tuple[DictionarySense, str], ...],
    ) -> str:
        displayed_keys = {
            key
            for _sense, translation in displayed_senses
            if (key := cls._translation_key(translation))
        }
        for _sense, translation in displayed_senses:
            for raw_line in translation.splitlines():
                body = _TRANSLATION_PART_OF_SPEECH.sub(
                    "", raw_line.strip()
                ).strip()
                for part in re.split(r"[,，;；、]", body):
                    if key := cls._translation_key(part):
                        displayed_keys.add(key)
        remaining_lines: list[str] = []
        for raw_line in summary.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if cls._translation_key(line) in displayed_keys:
                continue
            prefix_match = _TRANSLATION_PART_OF_SPEECH.match(line)
            prefix = prefix_match.group(0) if prefix_match else ""
            body = line[len(prefix):].strip()
            parts = [
                part.strip()
                for part in re.split(r"[,，;；、]", body)
                if part.strip()
            ]
            if len(parts) > 1:
                remaining_parts = [
                    part
                    for part in parts
                    if cls._translation_key(part) not in displayed_keys
                ]
                if not remaining_parts:
                    continue
                remaining_lines.append(f"{prefix}{'，'.join(remaining_parts)}")
                continue
            remaining_lines.append(line)
        return "\n".join(remaining_lines)

    @staticmethod
    def _sense_text(
        index: int,
        sense: DictionarySense,
        display_translation: str | None = None,
    ) -> str:
        heading = f"{index}. {sense.part_of_speech}".strip()
        values = [heading]
        translation = (
            sense.translation
            if display_translation is None
            else display_translation
        )
        if translation:
            values.append(translation)
        if sense.definition:
            values.append(f"英文释义：{sense.definition}")
        for example in sense.examples:
            label = (
                "释义语境提示"
                if example.source.startswith("释义语境")
                else "例句"
            )
            values.append(f"{label} · {example.source}\n{example.text}")
        return "\n".join(values)
