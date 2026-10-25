import pytest
from gre_vocab_app.word_marks import adjust_count, validate_marks


def test_arbitrary_precision_add_subtract_and_zero_floor():
    assert adjust_count('0', -1) == '0'
    assert adjust_count('0', 1) == '1'
    assert adjust_count('1000', -1) == '999'
    assert adjust_count('999', 1) == '1000'
    assert adjust_count('9007199254740992', 1) == '9007199254740993'
    huge = '9' * 5000
    assert adjust_count(huge, 1) == '1' + '0' * 5000
    assert adjust_count('1' + '0' * 5000, -1) == huge


@pytest.mark.parametrize('value', [None, [], {'Word': '1'}, {'word': -1}, {'word': 1}, {'word': '01'}, {'word': '-1'}, {'word': '1\n'}, {'word': '１'}, {'word': '1.5'}])
def test_invalid_marks_never_enter_progress(value):
    with pytest.raises(ValueError):
        validate_marks(value)
