from PySide6.QtTest import QSignalSpy
from gre_vocab_app.domain import StudyMode
from gre_vocab_app.ui.word_detail import WordDetail
from gre_vocab_app.ui.study_page import StudyPage


def test_mark_controls_visible_and_share_count_in_every_mode(qtbot, sample_word):
    detail = WordDetail()
    qtbot.addWidget(detail)
    detail.show()
    detail.word_marks.load_count = lambda word: '9007199254740993'
    for mode in StudyMode:
        detail.set_word(sample_word, mode=mode)
        assert detail.word_marks.isVisible()
        assert '9007199254740993' in detail.word_marks.label.text()
        with qtbot.waitSignal(detail.word_marks.adjustmentRequested) as signal:
            detail.word_marks.decrease.click()
        assert signal.args == [sample_word.headword, -1]
        with qtbot.waitSignal(detail.word_marks.adjustmentRequested) as signal:
            detail.word_marks.increase.click()
        assert signal.args == [sample_word.headword, 1]
    detail.word_marks.load_count = lambda word: '0'
    detail.word_marks.refresh()
    assert not detail.word_marks.decrease.isEnabled()
