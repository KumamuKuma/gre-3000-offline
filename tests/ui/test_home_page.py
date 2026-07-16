from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence

from gre_vocab_app.ui.home_page import HomePage


def test_home_search_emits_trimmed_query_and_stats_render(qtbot):
    page = HomePage()
    qtbot.addWidget(page)

    with qtbot.waitSignal(page.searchRequested) as signal:
        page.search_edit.setText("  abat ")
    assert signal.args == ["abat"]

    page.set_stats(total=3056, seen=27, favorites=4)
    assert page.total_value.text() == "3,056"
    assert page.seen_value.text() == "27"
    assert page.favorites_value.text() == "4"


def test_home_action_buttons_and_result_selection_emit_domain_values(
    qtbot, sample_word
):
    page = HomePage()
    qtbot.addWidget(page)
    page.show()

    for button, signal in (
        (page.continue_button, page.continueRequested),
        (page.source_button, page.sourceRequested),
        (page.random_button, page.randomRequested),
        (page.favorites_button, page.favoriteRequested),
    ):
        with qtbot.waitSignal(signal):
            button.click()

    other = replace(sample_word, id=2, headword="unabated")
    page.set_results([sample_word, other])
    assert page.results.count() == 2
    assert sample_word.definition_zh in page.results.item(0).text()

    with qtbot.waitSignal(page.wordSelected) as selected:
        page.results.setCurrentRow(1)
    assert selected.args == [other]

    page.search_edit.setText("missing")
    page.set_results([])
    assert page.results.count() == 0
    assert page.no_results_label.isVisible()


def test_clearing_search_immediately_clears_stale_empty_state(qtbot):
    page = HomePage()
    qtbot.addWidget(page)
    page.show()
    page.search_edit.setText("missing")
    page.set_results([])
    assert page.no_results_label.isVisible()

    page.search_edit.clear()

    assert page.no_results_label.isHidden()
    assert page.results.count() == 0


def test_ctrl_f_focuses_home_search(qtbot):
    page = HomePage()
    qtbot.addWidget(page)
    page.show()
    page.setFocus()

    assert page.find_shortcut.key().matches(
        QKeySequence(QKeySequence.StandardKey.Find)
    ) == QKeySequence.ExactMatch
    page.find_shortcut.activated.emit()
    qtbot.waitUntil(page.search_edit.hasFocus)
