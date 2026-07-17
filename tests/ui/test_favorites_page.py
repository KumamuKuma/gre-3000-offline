from dataclasses import replace

from gre_vocab_app.ui.favorites_page import FavoritesPage


def test_favorites_empty_state_search_and_words(qtbot, sample_word):
    page = FavoritesPage()
    qtbot.addWidget(page)
    page.show()

    page.set_words([])
    assert page.empty_state.isVisible()
    assert page.words_list.isHidden()

    with qtbot.waitSignal(page.searchRequested) as signal:
        page.search_edit.setText("  inevit ")
    assert signal.args == ["inevit"]

    page.set_words([sample_word])
    assert page.empty_state.isHidden()
    assert page.words_list.isVisible()
    assert page.words_list.count() == 1


def test_favorites_open_and_remove_emit_selected_word(qtbot, sample_word):
    page = FavoritesPage()
    qtbot.addWidget(page)
    page.show()
    other = replace(sample_word, id=2, headword="abate")
    page.set_words([sample_word, other])
    page.words_list.setCurrentRow(1)

    with qtbot.waitSignal(page.wordSelected) as opened:
        page.open_button.click()
    assert opened.args == [other]

    with qtbot.waitSignal(page.favoriteRemoved) as removed:
        page.remove_button.click()
    assert removed.args == [2]
