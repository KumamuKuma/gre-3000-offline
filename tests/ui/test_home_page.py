from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QDialogButtonBox, QLabel

from gre_vocab_app.domain import SourceList
from gre_vocab_app.ui.home_page import HomePage, ListScopeDialog, StarScopeDialog


LISTS = (
    SourceList("list1", "List 1", 105, 1, 105),
    SourceList("list2", "List 2", 105, 106, 210),
)


def test_home_search_stats_lists_and_star_counts_render(qtbot):
    page = HomePage()
    qtbot.addWidget(page)
    with qtbot.waitSignal(page.searchRequested) as signal:
        page.search_edit.setText("  abat ")
    assert signal.args == ["abat"]

    page.set_stats(total=3292, completed_rounds=4)
    assert page.total_value.text() == "3,292"
    assert page.rounds_value.text() == "4"
    assert not hasattr(page, "seen_value")
    assert "已浏览" not in {label.text() for label in page.findChildren(QLabel)}

    page.set_source_lists(LISTS, {"list1": 2}, selected_key="list1")
    page.set_star_counts({0: 70, 1: 20, 2: 10, 3: 5})
    assert page.list_scope_button.text() == "已选 1 个 List"
    assert page.rounds_value_label.text() == "2"
    assert page.decrease_rounds_button.isEnabled()
    assert page.star_scope_button.text() == "全部星级（105 词）"


def test_home_selects_list_and_emits_list_scoped_study(qtbot):
    page = HomePage()
    qtbot.addWidget(page)
    page.show()
    page.set_source_lists(LISTS, {})
    page.set_star_counts({0: 100, 1: 3, 2: 2, 3: 0})

    page.set_star_counts({0: 90, 1: 10, 2: 4, 3: 1})
    assert page.set_selected_lists(("list1", "list2"))
    assert page.set_selected_star_ratings((1, 2))
    assert page.list_scope_button.text() == "全部 2 个 List"
    assert "1 星、2 星" in page.star_scope_button.text()
    with qtbot.waitSignal(page.listStudyRequested) as requested:
        page.start_button.click()
    assert requested.args == [("list1", "list2"), (1, 2), False]

    assert page.set_selected_lists(("list2",))
    assert page.list_scope_button.text() == "已选 1 个 List"
    with qtbot.waitSignal(page.listStudyRequested) as narrowed:
        page.start_button.click()
    assert narrowed.args == [("list2",), (1, 2), False]

    assert page.set_selected_star_ratings((0, 1, 2, 3))
    with qtbot.waitSignal(page.listStudyRequested) as all_words:
        page.start_button.click()
    assert all_words.args == [("list2",), None, False]
    assert not hasattr(page, "source_button")
    assert not hasattr(page, "favorites_button")


def test_home_machine7_filter_combines_with_list_and_star_scope(qtbot):
    page = HomePage()
    qtbot.addWidget(page)
    page.show()
    page.set_source_lists(
        LISTS,
        {},
        selected_keys=("list1", "list2"),
        selected_star_ratings=(1, 2),
    )
    page.set_star_counts({0: 3, 1: 4, 2: 2, 3: 1})

    with qtbot.waitSignal(page.machine7FilterChanged) as changed:
        page.machine7_only_checkbox.click()
    assert changed.args == [True]
    assert page.machine7_only()

    # The controller supplies counts narrowed to machine7 membership.
    page.set_star_counts({0: 1, 1: 2, 2: 1, 3: 0})
    assert "3 词" in page.star_scope_button.text()
    assert "机经 7.0 共 4 词" in page.list_meta_label.text()
    with qtbot.waitSignal(page.listStudyRequested) as requested:
        page.start_button.click()
    assert requested.args == [("list1", "list2"), (1, 2), True]

    page.set_star_counts({0: 0, 1: 0, 2: 0, 3: 0})
    assert not page.start_button.isEnabled()


def test_home_allows_manual_list_completion_adjustment(qtbot):
    page = HomePage()
    qtbot.addWidget(page)
    page.show()
    page.set_source_lists(LISTS, {"list1": 1}, selected_key="list1")

    with qtbot.waitSignal(page.listCompletionAdjustmentRequested) as increased:
        page.increase_rounds_button.click()
    assert increased.args == ["list1", 1]

    with qtbot.waitSignal(page.listCompletionAdjustmentRequested) as decreased:
        page.decrease_rounds_button.click()
    assert decreased.args == ["list1", -1]

    page.set_list_completion_counts({"list1": 0})
    assert not page.decrease_rounds_button.isEnabled()


def test_multi_list_scope_dialog_supports_select_all_and_requires_one(qtbot):
    dialog = ListScopeDialog(LISTS, ("list1",))
    qtbot.addWidget(dialog)
    assert dialog.selected_keys() == ("list1",)
    assert not dialog.all_checkbox.isChecked()

    dialog.all_checkbox.click()
    assert dialog.selected_keys() == ("list1", "list2")
    assert dialog.all_checkbox.isChecked()

    dialog.all_checkbox.click()
    assert dialog.selected_keys() == ()
    ok_button = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert not ok_button.isEnabled()


def test_multi_star_scope_dialog_supports_combined_ratings(qtbot):
    dialog = StarScopeDialog((70, 20, 10, 5), (1, 2))
    qtbot.addWidget(dialog)
    assert dialog.selected_ratings() == (1, 2)
    assert not dialog.all_checkbox.isChecked()

    dialog.all_checkbox.click()
    assert dialog.selected_ratings() == (0, 1, 2, 3)
    dialog.checkboxes[0].click()
    assert dialog.selected_ratings() == (1, 2, 3)


def test_home_word_list_and_result_selection_emit_domain_values(qtbot, sample_word):
    page = HomePage()
    qtbot.addWidget(page)
    page.show()
    with qtbot.waitSignal(page.wordListRequested):
        page.word_list_button.click()
    with qtbot.waitSignal(page.longSentencesRequested):
        page.long_sentence_button.click()

    other = replace(sample_word, id=2, headword="unabated")
    page.set_results([sample_word, other])
    page.results.setCurrentRow(1)
    with qtbot.waitSignal(page.wordSelected) as selected:
        page.results.itemActivated.emit(page.results.item(1))
    assert selected.args == [other]

    page.search_edit.setText("missing")
    page.set_results([])
    assert page.no_results_label.isVisible()
    page.search_edit.clear()
    assert page.no_results_label.isHidden()


def test_home_page_focus_and_result_keyboard_navigation(qtbot, sample_word):
    page = HomePage()
    qtbot.addWidget(page)
    page.show()
    page.search_edit.setText("existing")
    page.focus_search()
    qtbot.waitUntil(page.search_edit.hasFocus)
    assert page.search_edit.text() == "existing"

    other = replace(sample_word, id=2, headword="unabated")
    page.set_results([sample_word, other])
    selected = QSignalSpy(page.wordSelected)
    page.results.setFocus()
    qtbot.keyClick(page.results, Qt.Key_Down)
    qtbot.keyClick(page.results, Qt.Key_Down)
    assert selected.count() == 0
    qtbot.keyClick(page.results, Qt.Key_Enter)
    qtbot.waitUntil(lambda: selected.count() == 1)
    assert selected.at(0) == [other]
