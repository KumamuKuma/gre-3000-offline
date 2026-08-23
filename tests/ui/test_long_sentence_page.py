from PySide6.QtCore import Qt

from gre_vocab_app.services.long_sentences import LongSentence
from gre_vocab_app.ui.long_sentence_page import LongSentencePage


SENTENCES = (
    LongSentence(1, 69, "Although it was difficult, we continued.", (12,)),
    LongSentence(2, 71, "The next sentence follows.", (13, 14)),
)


def test_long_sentence_page_renders_one_sentence_and_safe_boundaries(qtbot):
    page = LongSentencePage()
    qtbot.addWidget(page)
    page.set_sentences(SENTENCES)

    assert page.position_label.text() == "1 / 2"
    assert page.sentence_label.text() == SENTENCES[0].text
    assert "原书第 69 句" in page.source_label.text()
    assert not page.previous_button.isEnabled()
    assert page.next_button.isEnabled()

    page.previous()
    assert page.current_sentence() == SENTENCES[0]
    page.next_button.click()
    assert page.position_label.text() == "2 / 2"
    assert page.sentence_label.text() == SENTENCES[1].text
    assert "原书第 71 句" in page.source_label.text()
    assert "13、14" in page.source_label.text()
    assert not page.next_button.isEnabled()
    page.next()
    assert page.current_sentence() == SENTENCES[1]


def test_long_sentence_words_lookup_and_arrows_work_from_selectable_label(qtbot):
    page = LongSentencePage()
    qtbot.addWidget(page)
    page.set_sentences(SENTENCES)
    page.show()
    page.sentence_label.setFocus()

    with qtbot.waitSignal(page.lookupRequested) as lookup:
        page.sentence_label._activate_link("lookup:Although")
    assert lookup.args == ["Although"]

    qtbot.keyClick(page.sentence_label, Qt.Key_Right)
    assert page.current_sentence() == SENTENCES[1]
    qtbot.keyClick(page.sentence_label, Qt.Key_Left)
    assert page.current_sentence() == SENTENCES[0]


def test_long_sentence_page_empty_error_and_back_are_friendly(qtbot):
    page = LongSentencePage()
    qtbot.addWidget(page)
    page.set_error("长难句内容暂时无法读取，请确认应用文件完整后重新打开。")

    assert page.position_label.text() == "0 / 0"
    assert "暂时无法读取" in page.empty_state.text()
    assert page.reader.isHidden()
    assert not page.previous_button.isEnabled()
    assert not page.next_button.isEnabled()
    with qtbot.waitSignal(page.backRequested):
        page.back_button.click()
