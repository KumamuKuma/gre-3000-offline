from gre_vocab_app.ui.lookup_label import LookupLabel, lookup_html


def test_lookup_html_preserves_punctuation_and_wraps_english_tokens():
    rendered = lookup_html("Work hard, don’t panic.")

    assert 'href="lookup:Work"' in rendered
    assert 'href="lookup:don%E2%80%99t"' in rendered
    assert ">hard</a>," in rendered
    assert "color:#101828" in rendered
    assert "color:#4338ca" not in rendered


def test_lookup_label_emits_decoded_word(qtbot):
    label = LookupLabel()
    qtbot.addWidget(label)
    with qtbot.waitSignal(label.lookupRequested) as signal:
        label._activate_link("lookup:don%27t")

    assert signal.args == ["don't"]
