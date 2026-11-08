from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
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
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gre_vocab_app.domain import SourceList, WordEntry
from .controls import SelectionChip, ToggleSwitch


class ListScopeDialog(QDialog):
    """Scrollable chip picker for a multi-List study scope."""

    def __init__(
        self,
        source_lists: Sequence[SourceList],
        selected_keys: Sequence[str],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("选择学习 List")
        self.setMinimumSize(500, 520)
        self.resize(560, 590)
        self._source_lists = tuple(source_lists)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)
        title = QLabel("选择要一起学习的 List")
        title.setObjectName("pageTitle")
        hint = QLabel("可任意多选；学习时会把所选 List 按原书顺序合并。")
        hint.setObjectName("sectionHint")
        hint.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(hint)

        self.all_checkbox = ToggleSwitch("全部 List")
        self.all_checkbox.setObjectName("scopeAllCheckbox")
        root.addWidget(self.all_checkbox)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(0, 4, 10, 4)
        grid.setSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setAlignment(Qt.AlignTop)
        self.list_buttons: dict[str, SelectionChip] = {}
        selected = set(selected_keys)
        for index, source_list in enumerate(self._source_lists):
            button = SelectionChip(
                f"{source_list.label} · {source_list.word_count} 词"
            )
            button.setChecked(source_list.key in selected)
            button.toggled.connect(self._sync_state)
            self.list_buttons[source_list.key] = button
            grid.addWidget(button, index // 2, index % 2)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        self.selection_label = QLabel()
        self.selection_label.setObjectName("muted")
        root.addWidget(self.selection_label)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.Ok).setText("应用选择")
        self.buttons.button(QDialogButtonBox.Cancel).setText("取消")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self.all_checkbox.toggled.connect(self._set_all)
        self._sync_state()

    def selected_keys(self) -> tuple[str, ...]:
        return tuple(
            key for key, button in self.list_buttons.items() if button.isChecked()
        )

    def _set_all(self, checked: bool) -> None:
        for button in self.list_buttons.values():
            with QSignalBlocker(button):
                button.setChecked(checked)
        self._sync_state()

    def _sync_state(self, *_args: object) -> None:
        selected_count = len(self.selected_keys())
        total = len(self.list_buttons)
        with QSignalBlocker(self.all_checkbox):
            self.all_checkbox.setChecked(total > 0 and selected_count == total)
        self.selection_label.setText(
            f"已选择 {selected_count} / {total} 个 List"
        )
        ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setEnabled(selected_count > 0)


class StarScopeDialog(QDialog):
    """Chip picker for one or more star ratings."""

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
        title.setObjectName("pageTitle")
        hint = QLabel("可以同时选择多个星级，例如同时学习 1 星和 2 星单词。")
        hint.setObjectName("sectionHint")
        hint.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(hint)

        self.all_checkbox = ToggleSwitch("全部星级")
        root.addWidget(self.all_checkbox)
        selected = {int(value) for value in selected_ratings}
        self.checkboxes: list[SelectionChip] = []
        values = tuple(int(value) for value in counts)
        for rating in range(4):
            label = (
                f"0 星（未评级，{values[rating]:,} 词）"
                if rating == 0
                else f"{rating} 星（{values[rating]:,} 词）"
            )
            checkbox = SelectionChip(label)
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
        self.buttons.button(QDialogButtonBox.Ok).setText("应用选择")
        self.buttons.button(QDialogButtonBox.Cancel).setText("取消")
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
    listStudyRequested = Signal(object, object, bool)
    listScopeChanged = Signal(object)
    starFiltersChanged = Signal(object)
    machine7FilterChanged = Signal(bool)
    markSortChanged = Signal(bool)
    listCompletionAdjustmentRequested = Signal(str, int)
    wordListRequested = Signal()
    longSentencesRequested = Signal()
    wordSelected = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("appSurface")
        self._lists: dict[str, SourceList] = {}
        self._completion_counts: dict[str, int] = {}
        self._star_counts = (0, 0, 0, 0)
        self._selected_list_keys: tuple[str, ...] = ()
        self._selected_star_ratings: tuple[int, ...] = (0, 1, 2, 3)
        self._machine7_only = False

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 16, 28, 16)
        root.setSpacing(12)

        self.search_container = QWidget()
        search_row = QHBoxLayout(self.search_container)
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.addStretch(1)
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("largeSearch")
        self.search_edit.setPlaceholderText("输入英文单词    Ctrl + F")
        self.search_edit.setAccessibleName("搜索英文单词")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMinimumWidth(240)
        self.search_edit.setMaximumWidth(360)
        self.search_edit.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self.search_edit)
        root.addWidget(self.search_container)

        self.home_scroll = QScrollArea()
        self.home_scroll.setWidgetResizable(True)
        self.home_scroll.setFrameShape(QFrame.NoFrame)
        self.home_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        viewport_content = QWidget()
        centered_layout = QVBoxLayout(viewport_content)
        centered_layout.setContentsMargins(0, 0, 0, 0)
        centered_layout.setAlignment(Qt.AlignCenter)
        self.dashboard = QWidget()
        self.dashboard.setMinimumWidth(680)
        self.dashboard.setMaximumWidth(740)
        self.dashboard.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        dashboard_layout = QVBoxLayout(self.dashboard)
        dashboard_layout.setContentsMargins(0, 0, 0, 0)
        dashboard_layout.setSpacing(16)

        self.banner = hero = QFrame(objectName="heroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(0, 0, 0, 0)
        hero_layout.setSpacing(6)
        title = QLabel("GRE 3000")
        title.setObjectName("heroTitle")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("词汇训练 · 原书词序")
        subtitle.setObjectName("heroSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        metrics = QHBoxLayout()
        metrics.setSpacing(16)
        metrics.addStretch(1)
        self.total_value = self._hero_metric(metrics, "完整词库")
        divider = QLabel("│")
        divider.setObjectName("muted")
        metrics.addWidget(divider)
        self.rounds_value = self._hero_metric(metrics, "完成轮次")
        metrics.addStretch(1)
        hero_layout.addLayout(metrics)
        dashboard_layout.addWidget(hero)

        study_card = QFrame(objectName="studyCard")
        study_layout = QVBoxLayout(study_card)
        study_layout.setContentsMargins(24, 18, 24, 18)
        study_layout.setSpacing(16)
        study_title = QLabel("学习计划")
        study_title.setObjectName("homeStudyTitle")
        study_layout.addWidget(study_title)
        scope_grid = QGridLayout()
        scope_grid.setHorizontalSpacing(12)
        scope_grid.setColumnStretch(1, 1)
        scope_grid.setColumnStretch(3, 1)
        for column, caption in ((0, "学习 List"), (2, "星级筛选")):
            label = QLabel(caption)
            label.setObjectName("fieldLabel")
            scope_grid.addWidget(label, 0, column)
        self.list_scope_button = self._action("选择学习 List")
        self.list_scope_button.setObjectName("outlineButton")
        self.list_scope_button.setAccessibleName("多选学习 List")
        self.list_scope_button.clicked.connect(self._choose_lists)
        scope_grid.addWidget(self.list_scope_button, 0, 1)
        self.star_scope_button = self._action("选择学习星级")
        self.star_scope_button.setObjectName("outlineButton")
        self.star_scope_button.setAccessibleName("多选学习星级")
        self.star_scope_button.clicked.connect(self._choose_stars)
        scope_grid.addWidget(self.star_scope_button, 0, 3)
        study_layout.addLayout(scope_grid)

        filters = QHBoxLayout()
        filters.setSpacing(14)
        self.machine7_only_checkbox = ToggleSwitch("仅机经 7.0 重点词", pill=True)
        self.machine7_only_checkbox.setObjectName("machine7FilterCheckbox")
        self.machine7_only_checkbox.setAccessibleName("仅学习机经 7.0 重点词")
        self.machine7_only_checkbox.setToolTip("在所选 List 和星级范围内，只保留机经 7.0 重点词")
        self.machine7_only_checkbox.toggled.connect(self._machine7_filter_toggled)
        filters.addWidget(self.machine7_only_checkbox, 1)
        self.mark_sort_checkbox = ToggleSwitch("按累计标记倒序", pill=True)
        self.mark_sort_checkbox.setToolTip("次数相同保留原书词序；学习中增减标记不会移动当前词")
        self.mark_sort_checkbox.toggled.connect(self.markSortChanged.emit)
        filters.addWidget(self.mark_sort_checkbox, 1)
        study_layout.addLayout(filters)

        progress_row = QHBoxLayout()
        progress_row.setSpacing(12)
        self.list_meta_label = QLabel("请选择 List")
        self.list_meta_label.setObjectName("muted")
        self.list_meta_label.setWordWrap(True)
        progress_row.addWidget(self.list_meta_label, 1)
        progress_label = QLabel("所选 List 已背")
        progress_label.setObjectName("fieldLabel")
        progress_row.addWidget(progress_label)
        stepper = QFrame(objectName="roundStepper")
        stepper_layout = QHBoxLayout(stepper)
        stepper_layout.setContentsMargins(0, 0, 0, 0)
        stepper_layout.setSpacing(0)
        self.decrease_rounds_button = QPushButton("−")
        self.decrease_rounds_button.setObjectName("stepperDecrease")
        self.decrease_rounds_button.setFixedSize(38, 34)
        self.decrease_rounds_button.setAccessibleName("所选 List 已背次数减一")
        self.decrease_rounds_button.setToolTip("手动修正：已背次数减一")
        self.decrease_rounds_button.clicked.connect(lambda: self._emit_completion_adjustment(-1))
        stepper_layout.addWidget(self.decrease_rounds_button)
        self.rounds_value_label = QLabel("0")
        self.rounds_value_label.setObjectName("roundStepperValue")
        self.rounds_value_label.setMinimumWidth(34)
        self.rounds_value_label.setAlignment(Qt.AlignCenter)
        stepper_layout.addWidget(self.rounds_value_label)
        self.increase_rounds_button = QPushButton("+")
        self.increase_rounds_button.setObjectName("stepperIncrease")
        self.increase_rounds_button.setFixedSize(38, 34)
        self.increase_rounds_button.setAccessibleName("所选 List 已背次数加一")
        self.increase_rounds_button.setToolTip("手动记录：已背次数加一")
        self.increase_rounds_button.clicked.connect(lambda: self._emit_completion_adjustment(1))
        stepper_layout.addWidget(self.increase_rounds_button)
        progress_row.addWidget(stepper)
        study_layout.addLayout(progress_row)
        self.start_button = self._action("开始 / 继续学习", primary=True)
        self.start_button.setProperty("homeAction", True)
        self.start_button.setMinimumHeight(48)
        self.start_button.clicked.connect(self._emit_list_study)
        study_layout.addWidget(self.start_button)
        dashboard_layout.addWidget(study_card)

        links = QHBoxLayout()
        links.setSpacing(18)
        links.addStretch(1)
        self.word_list_button = QPushButton("浏览完整词表")
        self.word_list_button.setObjectName("textButton")
        self.word_list_button.clicked.connect(self.wordListRequested.emit)
        self.long_sentence_button = QPushButton("杨鹏阅读长难句")
        self.long_sentence_button.setObjectName("textButton")
        self.long_sentence_button.setAccessibleName("打开杨鹏阅读长难句")
        self.long_sentence_button.clicked.connect(self.longSentencesRequested.emit)
        links.addWidget(self.word_list_button)
        link_divider = QLabel("│")
        link_divider.setObjectName("muted")
        links.addWidget(link_divider)
        links.addWidget(self.long_sentence_button)
        links.addStretch(1)
        dashboard_layout.addLayout(links)
        centered_layout.addWidget(self.dashboard, 0, Qt.AlignHCenter)
        self.home_scroll.setWidget(viewport_content)
        root.addWidget(self.home_scroll, 1)
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
        button.setMinimumHeight(39)
        if primary:
            button.setObjectName("primaryButton")
        return button

    @staticmethod
    def _hero_metric(layout: QHBoxLayout, label_text: str) -> QLabel:
        card = QFrame(objectName="heroMetric")
        row = QHBoxLayout(card)
        row.setContentsMargins(0, 6, 0, 0)
        row.setSpacing(8)
        label = QLabel(label_text)
        label.setObjectName("heroMetricLabel")
        value = QLabel("0")
        value.setObjectName("homeInlineValue")
        row.addWidget(label)
        row.addWidget(value)
        layout.addWidget(card)
        return value

    def take_search_edit(self) -> QLineEdit:
        """Move the standalone search into the main window's navigation bar."""
        self.search_container.layout().removeWidget(self.search_edit)
        self.search_container.hide()
        return self.search_edit

    def set_stats(self, total: int, completed_rounds: int) -> None:
        self.total_value.setText(f"{total:,}")
        self.rounds_value.setText(f"{completed_rounds:,}")

    def set_mark_sort(self, enabled: bool) -> None:
        with QSignalBlocker(self.mark_sort_checkbox):
            self.mark_sort_checkbox.setChecked(enabled)

    def set_source_lists(
        self,
        source_lists: Sequence[SourceList],
        completion_counts: Mapping[str, int],
        *,
        selected_key: str | None = None,
        selected_star_keys: Sequence[str] | None = None,
        selected_keys: Sequence[str] | None = None,
        selected_star_ratings: Sequence[int] | None = None,
        machine7_only: bool | None = None,
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
        if machine7_only is not None:
            self.set_machine7_only(machine7_only)
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
        self._update_list_meta()
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

    def machine7_only(self) -> bool:
        return self._machine7_only

    def set_machine7_only(self, enabled: bool) -> None:
        self._machine7_only = bool(enabled)
        with QSignalBlocker(self.machine7_only_checkbox):
            self.machine7_only_checkbox.setChecked(self._machine7_only)
        self._update_list_meta()
        self._update_scope_controls()
        self._update_start_state()

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
        self.home_scroll.setVisible(not query)
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

    def _machine7_filter_toggled(self, checked: bool) -> None:
        self._machine7_only = bool(checked)
        self._update_list_meta()
        self._update_scope_controls()
        self._update_start_state()
        self.machine7FilterChanged.emit(self._machine7_only)

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
                if self._machine7_only:
                    self.list_meta_label.setText(
                        f"已合并 {len(selected)} 个 List · "
                        f"机经 7.0 共 {sum(self._star_counts):,} 词"
                    )
                else:
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
        suffix = (
            f" · 机经 7.0 共 {sum(self._star_counts):,} 词"
            if self._machine7_only
            else ""
        )
        self.list_meta_label.setText(
            f"原书第 {source_list.first_order}–{source_list.last_order} 词{suffix}"
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
        self.listStudyRequested.emit(
            self._selected_list_keys,
            ratings,
            self._machine7_only,
        )

    def _emit_completion_adjustment(self, delta: int) -> None:
        key = self.selected_list_key()
        if key is not None and delta in (-1, 1):
            self.listCompletionAdjustmentRequested.emit(key, delta)

    def _emit_word(self, item: QListWidgetItem) -> None:
        word = item.data(Qt.UserRole)
        if word is not None:
            self.wordSelected.emit(word)
