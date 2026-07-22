from dataclasses import replace
from time import perf_counter

import pytest
from PySide6.QtCore import Qt

from gre_vocab_app.ui.word_list_page import WordListPage, WordListRow


def test_word_list_rows_validate_zero_through_three_stars(sample_word):
    assert WordListRow(sample_word, rating=0).word is sample_word
    for value in (-1, 4, True, 1.5):
        with pytest.raises(ValueError):
            WordListRow(sample_word, rating=value)


def test_word_list_sorts_displays_list_and_filters_locally(qtbot, sample_word):
    page = WordListPage()
    qtbot.addWidget(page)
    later = replace(
        sample_word,
        id=2,
        source_order=108,
        source_section="list2",
        headword="abate",
        definition_zh="减弱",
    )
    page.set_words(
        (WordListRow(later, 3, in_machine7=True), WordListRow(sample_word, 1))
    )
    assert page.words_table.rowCount() == 2
    assert page.words_table.item(0, 1).text() == "List 1"
    assert page.words_table.item(1, 1).text() == "List 2"
    assert page.words_table.item(1, 3).text() == "重点"
    assert page.words_table.item(1, 5).text() == "3 星"

    page.search_edit.setText("list2")
    assert page.words_table.isRowHidden(0)
    assert not page.words_table.isRowHidden(1)
    page.search_edit.setText("减弱")
    assert not page.words_table.isRowHidden(1)
    page.search_edit.setText("机经7.0")
    assert page.words_table.isRowHidden(0)
    assert not page.words_table.isRowHidden(1)


def test_word_list_actions_emit_open_and_zero_to_three_star_cycle(qtbot, sample_word):
    page = WordListPage()
    qtbot.addWidget(page)
    page.show()
    page.set_words((WordListRow(sample_word, 3),))
    page.words_table.setCurrentCell(0, 0)

    with qtbot.waitSignal(page.wordSelected) as opened:
        page.open_button.click()
    assert opened.args == [sample_word]
    with qtbot.waitSignal(page.starRatingRequested) as star:
        page.star_button.click()
    assert star.args == [sample_word.id, 0]
    assert not hasattr(page, "increment_button")
    assert not hasattr(page, "decrement_button")


def test_word_list_empty_filter_and_incremental_update(qtbot, sample_word):
    page = WordListPage()
    qtbot.addWidget(page)
    page.show()
    other = replace(sample_word, id=2, source_order=2, headword="other")
    page.set_words((WordListRow(sample_word, 0), WordListRow(other, 2)))
    page.words_table.setCurrentCell(0, 0)

    assert page.update_rating(sample_word.id, 3)
    assert page.words_table.item(0, 5).text() == "3 星"
    assert page.words_table.currentRow() == 0
    assert not page.update_rating(999, 1)

    page.search_edit.setText("missing")
    assert page.empty_state.isVisible()
    assert not page.open_button.isEnabled()
    assert not page.star_button.isEnabled()


def test_word_list_double_click_opens_selected_word(qtbot, sample_word):
    page = WordListPage()
    qtbot.addWidget(page)
    page.show()
    page.set_words((WordListRow(sample_word, 0),))
    with qtbot.waitSignal(page.wordSelected) as selected:
        item = page.words_table.item(0, 0)
        page.words_table.itemActivated.emit(item)
    assert selected.args == [sample_word]


def test_large_visible_word_list_rebuild_and_single_rating_update_are_bounded(
    qtbot, sample_word
):
    page = WordListPage()
    qtbot.addWidget(page)
    page.show()
    rows = tuple(
        WordListRow(
            replace(
                sample_word,
                id=word_id,
                source_order=word_id,
                source_section=f"list{min(30, (word_id - 1) // 105 + 1)}",
                headword=f"word-{word_id}",
            ),
            0,
        )
        for word_id in range(1, 3293)
    )
    started = perf_counter()
    page.set_words(rows)
    rebuild = perf_counter() - started
    qtbot.wait(1)
    started = perf_counter()
    assert page.update_rating(1600, 3)
    update = perf_counter() - started
    assert page.words_table.item(1599, 5).text() == "3 星"
    assert rebuild < 3.0
    assert update < 0.5
    page.words_table.setFocus(Qt.OtherFocusReason)
