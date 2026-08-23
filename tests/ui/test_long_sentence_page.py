from PySide6.QtCore import QPoint, Qt

from gre_vocab_app.services.long_sentences import LongSentence, LongSentenceNote
from gre_vocab_app.ui.long_sentence_page import LongSentencePage


SENTENCES = (
    LongSentence(
        1,
        69,
        "Although it was difficult, we continued.",
        (12,),
        (
            LongSentenceNote("难度", "GRE"),
            LongSentenceNote("难句类型", "倒装与嵌套从句"),
            LongSentenceNote("译文", "尽管过程很困难，我们仍然继续了。"),
            LongSentenceNote("解释", "The clause beginning with Although yields."),
        ),
    ),
    LongSentence(
        2,
        71,
        "The next sentence follows.",
        (13, 14),
        (LongSentenceNote("译文", "下一句随之而来。"),),
    ),
)


def test_long_sentence_page_renders_one_sentence_and_safe_boundaries(qtbot):
    page = LongSentencePage()
    qtbot.addWidget(page)
    page.set_sentences(SENTENCES)

    assert page.position_label.text() == "1 / 2"
    assert page.sentence_label.text() == SENTENCES[0].text
    assert "原书第 69 句" in page.source_label.text()
    assert [label.text() for label in page.note_label_badges] == [
        "难度",
        "难句类型",
        "译文",
        "解释",
    ]
    assert [label.text() for label in page.note_labels] == [
        note.text for note in SENTENCES[0].notes
    ]
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


def test_long_sentence_words_lookup_and_arrows_work_from_selectable_labels(qtbot):
    page = LongSentencePage()
    qtbot.addWidget(page)
    page.set_sentences(SENTENCES)
    page.show()
    page.sentence_label.setFocus()

    with qtbot.waitSignal(page.lookupRequested) as lookup:
        page.sentence_label._activate_link("lookup:Although")
    assert lookup.args == ["Although"]

    with qtbot.waitSignal(page.lookupRequested) as note_lookup:
        page.note_labels[3]._activate_link("lookup:clause")
    assert note_lookup.args == ["clause"]

    with qtbot.waitSignal(page.selectionTranslationRequested) as translation:
        page.note_labels[3].selectionTranslationRequested.emit(
            "The clause beginning with Although"
        )
    assert translation.args == ["The clause beginning with Although"]

    page.note_labels[3].setFocus()
    qtbot.keyClick(page.note_labels[3], Qt.Key_Right)
    assert page.current_sentence() == SENTENCES[1]
    page.note_labels[0].setFocus()
    qtbot.keyClick(page.note_labels[0], Qt.Key_Left)
    assert page.current_sentence() == SENTENCES[0]


def test_long_sentence_page_scrolls_long_notes_and_resets_on_navigation(qtbot):
    long_note = (
        "这是用于验证超长中文注释不会被裁切的说明，"
        "其中的 English words 仍然可以查询。"
    ) * 180
    sentences = (
        LongSentence(
            1,
            1,
            "A first sentence.",
            (1,),
            (LongSentenceNote("解释", long_note),),
        ),
        LongSentence(
            2,
            2,
            "A second sentence.",
            (2,),
            (LongSentenceNote("译文", "第二句。"),),
        ),
    )
    page = LongSentencePage()
    qtbot.addWidget(page)
    page.resize(560, 420)
    page.set_sentences(sentences)
    page.show()

    scroll_bar = page.reader.verticalScrollBar()
    qtbot.waitUntil(lambda: scroll_bar.maximum() > 0)
    scroll_bar.setValue(scroll_bar.maximum())
    assert scroll_bar.value() > 0
    long_label = page.note_labels[-1]
    qtbot.waitUntil(
        lambda: long_label.mapTo(
            page.reader.viewport(), QPoint(0, long_label.height())
        ).y()
        <= page.reader.viewport().height()
    )
    rendered_bottom = long_label.mapTo(
        page.reader.viewport(), QPoint(0, long_label.height())
    ).y()
    assert 0 < rendered_bottom <= page.reader.viewport().height()
    assert long_label.height() + 1 >= long_label.heightForWidth(long_label.width())

    page.next()
    qtbot.waitUntil(lambda: scroll_bar.value() == scroll_bar.minimum())
    assert page.current_sentence() == sentences[1]


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
