from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
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
    """Compact checkbox picker for a multi-List study scope."""

    def __init__(
        self,
        source_lists: Sequence[SourceList],
        selected_keys: Sequence[str],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("选择学习 List")
        self.setMinimumSize(440, 520)
        self._source_lists = tuple(source_lists)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)
        title = QLabel("选择要一起学习的 List")
        title.setObjectName("sectionTitle")
        hint = QLabel("可任意多选；学习时会把所选 List 按原书顺序合并。")
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


class StarScopeDialog(QDialog):
    """Checkbox picker for one or more star ratings."""

    def __init__(
        self,
        counts: Sequence[int],
        selected_ratings: Sequence[int],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("选择学习星级")
        self.setMinimumWidth(420)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)
        title = QLabel("选择要一起学习的星级")
        title.setObjectName("sectionTitle")
        hint = QLabel("可以同时选择多个星级，例如同时学习 1 星和 2 星单词。")
        hint.setObjectName("sectionHint")
        hint.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(hint)

        self.all_checkbox = QCheckBox("全部星级")
        root.addWidget(self.all_checkbox)
        selected = {int(value) for value in selected_ratings}
        self.checkboxes: list[QCheckBox] = []
        values = tuple(int(value) for value in counts)
        for rating in range(4):
            label = (
                f"0 星（未评级，{values[rating]:,} 词）"
                if rating == 0
                else f"{rating} 星（{values[rating]:,} 词）"
            )
            checkbox = QCheckBox(label)
            checkbox.setProperty("rating", rating)
            checkbox.setChecked(rating in selected)
            checkbox.toggled.connect(self._sync_state)
            self.checkboxes.append(checkbox)
            root.addWidget(checkbox)

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
        self._sync_state()

    def selected_ratings(self) -> tuple[int, ...]:
        return tuple(
            rating
            for rating, checkbox in enumerate(self.checkboxes)
            if checkbox.isChecked()
        )

    def _set_all(self, checked: bool) -> None:
        for checkbox in self.checkboxes:
            with QSignalBlocker(checkbox):
                checkbox.setChecked(checked)
        self._sync_state()

    def _sync_state(self, *_args: object) -> None:
        selected = self.selected_ratings()
        with QSignalBlocker(self.all_checkbox):
            self.all_checkbox.setChecked(len(selected) == 4)
        self.selection_label.setText(f"已选择 {len(selected)} / 4 个星级")
        ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setEnabled(bool(selected))


class HomePage(QWidget):
    searchRequested = Signal(str)
    listStudyRequested = Signal(object, object)
    listScopeChanged = Signal(object)
    starFiltersChanged = Signal(object)
    listCompletionAdjustmentRequested = Signal(str, int)
    wordListRequested = Signal()
    wordSelected = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("appSurface")
        self._lists: dict[str, SourceList] = {}
        self._completion_counts: dict[str, int] = {}
        self._star_counts = (0, 0, 0, 0)
        self._selected_list_keys: tuple[str, ...] = ()
        self._selected_star_ratings: tuple[int, ...] = (0, 1, 2, 3)

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
        eyebrow = QLabel("GRE DESKTOP · STUDY")
        eyebrow.setObjectName("heroEyebrow")
        title = QLabel("GRE 3000 Vocabulary Trainer")
        title.setObjectName("heroTitle")
        subtitle = QLabel("按原书词序专注学习 · 学习记录默认保存在本机")
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
            "List 和星级都可以多选；所选单词始终按原书词序合并学习。"
        )
        study_hint.setObjectName("sectionHint")
        study_layout.addWidget(study_hint, 1, 0, 1, 3)

        list_label = QLabel("学习 List")
        list_label.setObjectName("fieldLabel")
        star_label = QLabel("星级筛选")
        star_label.setObjectName("fieldLabel")
        action_label = QLabel("学习")
        action_label.setObjectName("fieldLabel")
        study_layout.addWidget(list_label, 2, 0)
        study_layout.addWidget(star_label, 2, 1)
        study_layout.addWidget(action_label, 2, 2)

        self.list_scope_button = self._action("选择学习 List")
        self.list_scope_button.setObjectName("outlineButton")
        self.list_scope_button.setAccessibleName("多选学习 List")
        self.list_scope_button.clicked.connect(self._choose_lists)
        study_layout.addWidget(self.list_scope_button, 3, 0)

        self.star_scope_button = self._action("选择学习星级")
        self.star_scope_button.setObjectName("outlineButton")
        self.star_scope_button.setAccessibleName("多选学习星级")
        self.star_scope_button.clicked.connect(self._choose_stars)
        study_layout.addWidget(self.star_scope_button, 3, 1)

        self.start_button = self._action("开始 / 继续", primary=True)
        self.start_button.setMinimumWidth(142)
        self.start_button.clicked.connect(self._emit_list_study)
        study_layout.addWidget(self.start_button, 3, 2)

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
        study_layout.addLayout(progress_row, 4, 0, 1, 3)
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
        selected_keys: Sequence[str] | None = None,
        selected_star_ratings: Sequence[int] | None = None,
    ) -> None:
        lists = tuple(source_lists)
        if any(not isinstance(item, SourceList) for item in lists):
            raise ValueError("source_lists must contain SourceList values")
        self._lists = {item.key: item for item in lists}
        self._completion_counts = {
            str(key): int(value) for key, value in completion_counts.items()
        }
        requested = (
            tuple(str(key) for key in selected_keys)
            if selected_keys is not None
            else (
                tuple(str(key) for key in selected_star_keys)
                if selected_star_keys is not None
                else (
                    (str(selected_key),)
                    if selected_key is not None
                    else self._selected_list_keys
                )
            )
        )
        requested_set = set(requested)
        valid_keys = tuple(
            item.key for item in lists if item.key in requested_set
        )
        self._selected_list_keys = valid_keys or (
            (lists[0].key,) if lists else ()
        )
        if selected_star_ratings is not None:
            self.set_selected_star_ratings(selected_star_ratings)
        self._update_list_meta()
        self._update_scope_controls()
        self._update_start_state()

    def set_list_completion_counts(self, counts: Mapping[str, int]) -> None:
        self._completion_counts = {
            str(key): int(value) for key, value in counts.items()
        }
        self._update_list_meta()

    def _list_item_text(self, source_list: SourceList) -> str:
        completed = self._completion_counts.get(source_list.key, 0)
        return (
            f"{source_list.label} · {source_list.word_count} 词 · "
            f"已完成 {completed} 次"
        )

    def selected_list_key(self) -> str | None:
        return (
            self._selected_list_keys[0]
            if len(self._selected_list_keys) == 1
            else None
        )

    def selected_list_keys(self) -> tuple[str, ...]:
        return self._selected_list_keys

    def set_selected_list(self, key: str) -> bool:
        return self.set_selected_lists((str(key),))

    def set_selected_lists(self, keys: Sequence[str]) -> bool:
        requested = tuple(str(key) for key in keys)
        if not requested or len(set(requested)) != len(requested):
            return False
        if any(key not in self._lists for key in requested):
            return False
        requested_set = set(requested)
        self._selected_list_keys = tuple(
            key for key in self._lists if key in requested_set
        )
        self._update_list_meta()
        self._update_scope_controls()
        self._update_start_state()
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
        self._update_scope_controls()
        self._update_start_state()

    def set_selected_star_filter(self, rating: int | None) -> bool:
        return self.set_selected_star_ratings(
            range(4) if rating is None else (int(rating),)
        )

    def selected_star_filter(self) -> int | None:
        return (
            self._selected_star_ratings[0]
            if len(self._selected_star_ratings) == 1
            else None
        )

    def selected_star_ratings(self) -> tuple[int, ...]:
        return self._selected_star_ratings

    def set_selected_star_ratings(self, ratings: Sequence[int]) -> bool:
        requested = tuple(int(rating) for rating in ratings)
        if (
            not requested
            or len(set(requested)) != len(requested)
            or any(rating not in range(4) for rating in requested)
        ):
            return False
        self._selected_star_ratings = tuple(
            rating for rating in range(4) if rating in set(requested)
        )
        self._update_scope_controls()
        self._update_start_state()
        return True

    def selected_star_list_keys(self) -> tuple[str, ...]:
        return self._selected_list_keys

    def set_selected_star_lists(self, keys: Sequence[str]) -> bool:
        return self.set_selected_lists(keys)

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

    def _choose_lists(self) -> None:
        dialog = ListScopeDialog(
            tuple(self._lists.values()),
            self._selected_list_keys,
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = dialog.selected_keys()
        if selected != self._selected_list_keys and self.set_selected_lists(selected):
            self.listScopeChanged.emit(selected)

    def _choose_stars(self) -> None:
        dialog = StarScopeDialog(
            self._star_counts,
            self._selected_star_ratings,
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = dialog.selected_ratings()
        if (
            selected != self._selected_star_ratings
            and self.set_selected_star_ratings(selected)
        ):
            self.starFiltersChanged.emit(selected)

    def _update_scope_controls(self) -> None:
        total = len(self._lists)
        selected_lists = len(self._selected_list_keys)
        if selected_lists == total and total:
            list_summary = f"全部 {total} 个 List"
        else:
            list_summary = f"已选 {selected_lists} 个 List"
        self.list_scope_button.setText(list_summary)

        ratings = self._selected_star_ratings
        if ratings == (0, 1, 2, 3):
            star_summary = f"全部星级（{sum(self._star_counts):,} 词）"
        else:
            labels = "、".join(f"{rating} 星" for rating in ratings)
            count = sum(self._star_counts[rating] for rating in ratings)
            star_summary = f"{labels}（{count:,} 词）"
        self.star_scope_button.setText(star_summary)
        self.list_scope_button.setEnabled(bool(self._lists))
        self.star_scope_button.setEnabled(bool(self._lists))

    def _update_list_meta(self) -> None:
        key = self.selected_list_key()
        source_list = self._lists.get(key or "")
        if source_list is None:
            selected = tuple(
                self._lists[key]
                for key in self._selected_list_keys
                if key in self._lists
            )
            if selected:
                word_count = sum(item.word_count for item in selected)
                self.list_meta_label.setText(
                    f"已合并 {len(selected)} 个 List · 共 {word_count:,} 词"
                )
            else:
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
        available = sum(
            self._star_counts[rating]
            for rating in self._selected_star_ratings
        )
        self.start_button.setEnabled(
            bool(self._selected_list_keys)
            and bool(self._selected_star_ratings)
            and available > 0
        )

    def _emit_list_study(self) -> None:
        if not self.start_button.isEnabled():
            return
        ratings: tuple[int, ...] | None = self._selected_star_ratings
        if ratings == (0, 1, 2, 3):
            ratings = None
        self.listStudyRequested.emit(self._selected_list_keys, ratings)

    def _emit_completion_adjustment(self, delta: int) -> None:
        key = self.selected_list_key()
        if key is not None and delta in (-1, 1):
            self.listCompletionAdjustmentRequested.emit(key, delta)

    def _emit_word(self, item: QListWidgetItem) -> None:
        word = item.data(Qt.UserRole)
        if word is not None:
            self.wordSelected.emit(word)
