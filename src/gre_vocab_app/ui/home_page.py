from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
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

from gre_vocab_app.domain import SourceList, WordEntry


class ListScopeDialog(QDialog):
    """Compact checkbox picker for a star-filtered multi-List scope."""

    def __init__(
        self,
        source_lists: Sequence[SourceList],
        selected_keys: Sequence[str],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("选择星级学习范围")
        self.setMinimumSize(440, 520)
        self._source_lists = tuple(source_lists)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)
        title = QLabel("选择要一起筛选的 List")
        title.setObjectName("sectionTitle")
        hint = QLabel("可任意多选；学习时会把所选 List 的同星级单词按原书顺序合并。")
        hint.setObjectName("sectionHint")
        hint.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(hint)

        self.all_checkbox = QCheckBox("全部 List")
        self.all_checkbox.setObjectName("scopeAllCheckbox")
        root.addWidget(self.all_checkbox)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("scopeList")
        selected = set(selected_keys)
        for source_list in self._source_lists:
            item = QListWidgetItem(
                f"{source_list.label} · {source_list.word_count} 词"
            )
            item.setData(Qt.UserRole, source_list.key)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(
                Qt.Checked if source_list.key in selected else Qt.Unchecked
            )
            self.list_widget.addItem(item)
        root.addWidget(self.list_widget, 1)

        self.selection_label = QLabel()
        self.selection_label.setObjectName("muted")
        root.addWidget(self.selection_label)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self.all_checkbox.toggled.connect(self._set_all)
        self.list_widget.itemChanged.connect(self._sync_state)
        self._sync_state()

    def selected_keys(self) -> tuple[str, ...]:
        return tuple(
            str(self.list_widget.item(index).data(Qt.UserRole))
            for index in range(self.list_widget.count())
            if self.list_widget.item(index).checkState() == Qt.Checked
        )

    def _set_all(self, checked: bool) -> None:
        with QSignalBlocker(self.list_widget):
            for index in range(self.list_widget.count()):
                self.list_widget.item(index).setCheckState(
                    Qt.Checked if checked else Qt.Unchecked
                )
        self._sync_state()

    def _sync_state(self, *_args: object) -> None:
        selected_count = len(self.selected_keys())
        total = self.list_widget.count()
        with QSignalBlocker(self.all_checkbox):
            self.all_checkbox.setChecked(total > 0 and selected_count == total)
        self.selection_label.setText(
            f"已选择 {selected_count} / {total} 个 List"
        )
        ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setEnabled(selected_count > 0)


class HomePage(QWidget):
    searchRequested = Signal(str)
    listStudyRequested = Signal(object, object)
    listSelectionChanged = Signal(str)
    starFilterChanged = Signal(object)
    starStudyScopeChanged = Signal(object)
    listCompletionAdjustmentRequested = Signal(str, int)
    wordListRequested = Signal()
    wordSelected = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("appSurface")
        self._lists: dict[str, SourceList] = {}
        self._completion_counts: dict[str, int] = {}
        self._star_counts = (0, 0, 0, 0)
        self._star_list_keys: tuple[str, ...] = ()

        root = QVBoxLayout(self)
        root.setContentsMargins(38, 28, 38, 30)
        root.setSpacing(18)

        hero = QFrame(objectName="heroCard")
        hero.setMinimumHeight(150)
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(27, 22, 24, 22)
        hero_layout.setSpacing(24)

        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(7)
        hero_copy.addStretch(1)
        eyebrow = QLabel("GRE DESKTOP · OFFLINE")
        eyebrow.setObjectName("heroEyebrow")
        title = QLabel("GRE 3000 词汇训练")
        title.setObjectName("heroTitle")
        subtitle = QLabel("按原书词序专注学习 · 学习记录仅保存在本机")
        subtitle.setObjectName("heroSubtitle")
        hero_copy.addWidget(eyebrow)
        hero_copy.addWidget(title)
        hero_copy.addWidget(subtitle)
        hero_copy.addStretch(1)
        hero_layout.addLayout(hero_copy, 5)

        metrics = QHBoxLayout()
        metrics.setSpacing(10)
        self.total_value = self._hero_metric(metrics, "完整词库")
        self.rounds_value = self._hero_metric(metrics, "完成轮次")
        hero_layout.addLayout(metrics, 3)
        root.addWidget(hero)

        search_card = QFrame(objectName="searchCard")
        search_layout = QVBoxLayout(search_card)
        search_layout.setContentsMargins(20, 15, 20, 18)
        search_layout.setSpacing(10)
        search_header = QHBoxLayout()
        search_title = QLabel("快速查词")
        search_title.setObjectName("sectionTitle")
        search_hint = QLabel("Ctrl + F")
        search_hint.setObjectName("shortcutBadge")
        search_header.addWidget(search_title)
        search_header.addStretch(1)
        search_header.addWidget(search_hint)
        search_layout.addLayout(search_header)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("largeSearch")
        self.search_edit.setPlaceholderText("输入英文单词，立即搜索完整词库")
        self.search_edit.setAccessibleName("搜索英文单词")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_edit)
        root.addWidget(search_card)

        study_card = QFrame(objectName="studyCard")
        study_layout = QGridLayout(study_card)
        study_layout.setContentsMargins(21, 17, 21, 19)
        study_layout.setHorizontalSpacing(12)
        study_layout.setVerticalSpacing(9)
        study_layout.setColumnStretch(0, 3)
        study_layout.setColumnStretch(1, 2)
        study_layout.setColumnStretch(2, 1)
        study_title = QLabel("开始一次专注学习")
        study_title.setObjectName("sectionTitle")
        study_layout.addWidget(study_title, 0, 0, 1, 2)

        self.word_list_button = self._action("浏览完整词表")
        self.word_list_button.setObjectName("outlineButton")
        self.word_list_button.clicked.connect(self.wordListRequested.emit)
        study_layout.addWidget(self.word_list_button, 0, 2)

        study_hint = QLabel(
            "全部星级按单个 List 学习；选择具体星级后，可合并任意多个 List。"
        )
        study_hint.setObjectName("sectionHint")
        study_layout.addWidget(study_hint, 1, 0, 1, 3)

        list_label = QLabel("单 List 学习")
        list_label.setObjectName("fieldLabel")
        star_label = QLabel("星级筛选")
        star_label.setObjectName("fieldLabel")
        action_label = QLabel("学习")
        action_label.setObjectName("fieldLabel")
        study_layout.addWidget(list_label, 2, 0)
        study_layout.addWidget(star_label, 2, 1)
        study_layout.addWidget(action_label, 2, 2)

        self.list_combo = QComboBox()
        self.list_combo.setAccessibleName("选择学习 List")
        self.list_combo.setMinimumWidth(260)
        self.list_combo.currentIndexChanged.connect(self._on_list_changed)
        study_layout.addWidget(self.list_combo, 3, 0)

        self.star_combo = QComboBox()
        self.star_combo.setAccessibleName("选择星级范围")
        self.star_combo.setMinimumWidth(210)
        self.star_combo.addItem("全部星级", None)
        for rating in range(4):
            self.star_combo.addItem("", rating)
        self.star_combo.currentIndexChanged.connect(self._on_star_filter_changed)
        study_layout.addWidget(self.star_combo, 3, 1)

        self.start_button = self._action("开始 / 继续", primary=True)
        self.start_button.setMinimumWidth(142)
        self.start_button.clicked.connect(self._emit_list_study)
        study_layout.addWidget(self.start_button, 3, 2)

        star_scope_label = QLabel("星级学习范围")
        star_scope_label.setObjectName("fieldLabel")
        study_layout.addWidget(star_scope_label, 4, 0)
        self.star_list_button = self._action("选择多个 List")
        self.star_list_button.setObjectName("outlineButton")
        self.star_list_button.setAccessibleName("选择星级学习包含的多个 List")
        self.star_list_button.clicked.connect(self._choose_star_lists)
        study_layout.addWidget(self.star_list_button, 4, 1)
        self.star_scope_hint = QLabel("选择 0–3 星后可设置")
        self.star_scope_hint.setObjectName("muted")
        self.star_scope_hint.setAlignment(Qt.AlignCenter)
        study_layout.addWidget(self.star_scope_hint, 4, 2)

        progress_row = QHBoxLayout()
        self.list_meta_label = QLabel("请选择 List")
        self.list_meta_label.setObjectName("muted")
        progress_row.addWidget(self.list_meta_label)
        progress_row.addStretch(1)
        progress_label = QLabel("所选 List 已背")
        progress_label.setObjectName("fieldLabel")
        progress_row.addWidget(progress_label)
        self.decrease_rounds_button = QPushButton("−")
        self.decrease_rounds_button.setObjectName("compactButton")
        self.decrease_rounds_button.setAccessibleName("所选 List 已背次数减一")
        self.decrease_rounds_button.setToolTip("手动修正：已背次数减一")
        self.decrease_rounds_button.clicked.connect(
            lambda: self._emit_completion_adjustment(-1)
        )
        progress_row.addWidget(self.decrease_rounds_button)
        self.rounds_value_label = QLabel("0")
        self.rounds_value_label.setObjectName("countBadge")
        self.rounds_value_label.setMinimumWidth(30)
        self.rounds_value_label.setAlignment(Qt.AlignCenter)
        progress_row.addWidget(self.rounds_value_label)
        self.increase_rounds_button = QPushButton("+")
        self.increase_rounds_button.setObjectName("compactButton")
        self.increase_rounds_button.setAccessibleName("所选 List 已背次数加一")
        self.increase_rounds_button.setToolTip("手动记录：已背次数加一")
        self.increase_rounds_button.clicked.connect(
            lambda: self._emit_completion_adjustment(1)
        )
        progress_row.addWidget(self.increase_rounds_button)
        study_layout.addLayout(progress_row, 5, 0, 1, 3)
        root.addWidget(study_card)
        self.set_star_counts({})

        self.results_header = QWidget()
        results_header_layout = QHBoxLayout(self.results_header)
        results_header_layout.setContentsMargins(2, 0, 2, 0)
        self.results_title = QLabel("查词结果")
        self.results_title.setObjectName("sectionTitle")
        results_caption = QLabel("双击或按 Enter 打开词条")
        results_caption.setObjectName("sectionHint")
        results_header_layout.addWidget(self.results_title)
        results_header_layout.addStretch(1)
        results_header_layout.addWidget(results_caption)
        self.results_header.hide()
        root.addWidget(self.results_header)
        self.no_results_label = QLabel("没有找到匹配的单词。")
        self.no_results_label.setObjectName("emptyState")
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
    def _hero_metric(layout: QHBoxLayout, label_text: str) -> QLabel:
        card = QFrame(objectName="heroMetric")
        card.setMinimumWidth(118)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 13, 16, 14)
        card_layout.setSpacing(3)
        label = QLabel(label_text)
        label.setObjectName("heroMetricLabel")
        value = QLabel("0")
        value.setObjectName("heroMetricValue")
        card_layout.addWidget(label)
        card_layout.addWidget(value)
        layout.addWidget(card)
        return value

    def set_stats(self, total: int, completed_rounds: int) -> None:
        self.total_value.setText(f"{total:,}")
        self.rounds_value.setText(f"{completed_rounds:,}")

    def set_source_lists(
        self,
        source_lists: Sequence[SourceList],
        completion_counts: Mapping[str, int],
        *,
        selected_key: str | None = None,
        selected_star_keys: Sequence[str] | None = None,
    ) -> None:
        lists = tuple(source_lists)
        if any(not isinstance(item, SourceList) for item in lists):
            raise ValueError("source_lists must contain SourceList values")
        self._lists = {item.key: item for item in lists}
        self._completion_counts = {
            str(key): int(value) for key, value in completion_counts.items()
        }
        previous = selected_key or self.selected_list_key()
        requested_star_keys = (
            tuple(str(key) for key in selected_star_keys)
            if selected_star_keys is not None
            else self._star_list_keys
        )
        valid_star_keys = tuple(
            item.key for item in lists if item.key in set(requested_star_keys)
        )
        self._star_list_keys = valid_star_keys or tuple(item.key for item in lists)
        with QSignalBlocker(self.list_combo):
            self.list_combo.clear()
            for item in lists:
                self.list_combo.addItem(self._list_item_text(item), item.key)
            index = self.list_combo.findData(previous)
            self.list_combo.setCurrentIndex(index if index >= 0 else (0 if lists else -1))
        self._update_list_meta()
        self._update_star_scope_controls()
        self._update_start_state()

    def set_list_completion_counts(self, counts: Mapping[str, int]) -> None:
        self._completion_counts = {
            str(key): int(value) for key, value in counts.items()
        }
        with QSignalBlocker(self.list_combo):
            for index in range(self.list_combo.count()):
                key = str(self.list_combo.itemData(index))
                source_list = self._lists.get(key)
                if source_list is not None:
                    self.list_combo.setItemText(index, self._list_item_text(source_list))
        self._update_list_meta()

    def _list_item_text(self, source_list: SourceList) -> str:
        completed = self._completion_counts.get(source_list.key, 0)
        return (
            f"{source_list.label} · {source_list.word_count} 词 · "
            f"已完成 {completed} 次"
        )

    def selected_list_key(self) -> str | None:
        value = self.list_combo.currentData()
        return str(value) if value is not None else None

    def set_selected_list(self, key: str) -> bool:
        index = self.list_combo.findData(str(key))
        if index < 0:
            return False
        self.list_combo.setCurrentIndex(index)
        return True

    def set_star_counts(
        self, counts: Mapping[int, int] | Sequence[int]
    ) -> None:
        if isinstance(counts, Mapping):
            values = tuple(counts.get(rating, 0) for rating in range(4))
        else:
            values = tuple(counts)
            if len(values) != 4:
                raise ValueError("star counts must contain ratings 0 through 3")
        if any(type(value) is not int or value < 0 for value in values):
            raise ValueError("star counts must be non-negative integers")
        self._star_counts = values
        selected = self.star_combo.currentData()
        with QSignalBlocker(self.star_combo):
            self.star_combo.setItemText(0, f"全部星级（{sum(values):,} 词）")
            for rating, count in enumerate(values):
                text = (
                    f"0 星（未评级，{count:,} 词）"
                    if rating == 0
                    else f"{rating} 星（{count:,} 词）"
                )
                self.star_combo.setItemText(rating + 1, text)
            index = self.star_combo.findData(selected)
            if index >= 0:
                self.star_combo.setCurrentIndex(index)
        self._update_start_state()

    def set_selected_star_filter(self, rating: int | None) -> bool:
        index = self.star_combo.findData(rating)
        if index < 0:
            return False
        self.star_combo.setCurrentIndex(index)
        return True

    def selected_star_filter(self) -> int | None:
        value = self.star_combo.currentData()
        return None if value is None else int(value)

    def selected_star_list_keys(self) -> tuple[str, ...]:
        return self._star_list_keys

    def set_selected_star_lists(self, keys: Sequence[str]) -> bool:
        requested = tuple(str(key) for key in keys)
        if not requested or len(set(requested)) != len(requested):
            return False
        if any(key not in self._lists for key in requested):
            return False
        canonical = tuple(key for key in self._lists if key in set(requested))
        if not canonical:
            return False
        self._star_list_keys = canonical
        self._update_star_scope_controls()
        self._update_start_state()
        return True

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
        query = text.strip()
        self.results_header.setVisible(bool(query))
        self.searchRequested.emit(query)

    def focus_search(self) -> None:
        self.search_edit.setFocus(Qt.ShortcutFocusReason)

    def _on_list_changed(self, _index: int) -> None:
        self._update_list_meta()
        key = self.selected_list_key()
        if key is not None:
            self.listSelectionChanged.emit(key)

    def _on_star_filter_changed(self, _index: int) -> None:
        self._update_star_scope_controls()
        self._update_start_state()
        self.starFilterChanged.emit(self.star_combo.currentData())

    def _choose_star_lists(self) -> None:
        dialog = ListScopeDialog(
            tuple(self._lists.values()),
            self._star_list_keys,
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = dialog.selected_keys()
        if selected != self._star_list_keys and self.set_selected_star_lists(selected):
            self.starStudyScopeChanged.emit(selected)

    def _update_star_scope_controls(self) -> None:
        enabled = self.selected_star_filter() is not None and bool(self._lists)
        self.star_list_button.setEnabled(enabled)
        total = len(self._lists)
        selected = len(self._star_list_keys)
        if selected == total and total:
            summary = f"全部 {total} 个 List"
        else:
            summary = f"已选 {selected} 个 List"
        self.star_list_button.setText(summary if enabled else "选择具体星级后设置")
        self.star_scope_hint.setText(
            f"合并 {selected} 个 List" if enabled else "选择 0–3 星后可设置"
        )

    def _update_list_meta(self) -> None:
        key = self.selected_list_key()
        source_list = self._lists.get(key or "")
        if source_list is None:
            self.list_meta_label.setText("请选择 List")
            self.rounds_value_label.setText("0")
            self.decrease_rounds_button.setEnabled(False)
            self.increase_rounds_button.setEnabled(False)
            return
        completed = self._completion_counts.get(source_list.key, 0)
        self.list_meta_label.setText(
            f"原书第 {source_list.first_order}–{source_list.last_order} 词"
        )
        self.rounds_value_label.setText(str(completed))
        self.decrease_rounds_button.setEnabled(completed > 0)
        self.increase_rounds_button.setEnabled(True)

    def _update_start_state(self, *_args: object) -> None:
        rating = self.star_combo.currentData()
        available = sum(self._star_counts) if rating is None else self._star_counts[int(rating)]
        has_scope = (
            self.selected_list_key() is not None
            if rating is None
            else bool(self._star_list_keys)
        )
        self.start_button.setEnabled(has_scope and available > 0)

    def _emit_list_study(self) -> None:
        key = self.selected_list_key()
        rating = self.star_combo.currentData()
        if not self.start_button.isEnabled():
            return
        if rating is None and key is not None:
            self.listStudyRequested.emit(key, None)
        elif rating is not None and self._star_list_keys:
            self.listStudyRequested.emit(self._star_list_keys, rating)

    def _emit_completion_adjustment(self, delta: int) -> None:
        key = self.selected_list_key()
        if key is not None and delta in (-1, 1):
            self.listCompletionAdjustmentRequested.emit(key, delta)

    def _emit_word(self, item: QListWidgetItem) -> None:
        word = item.data(Qt.UserRole)
        if word is not None:
            self.wordSelected.emit(word)
