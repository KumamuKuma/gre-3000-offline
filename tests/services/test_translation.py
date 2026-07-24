from __future__ import annotations

import json

import pytest

from gre_vocab_app.services.translation import translate_english_to_chinese


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps(
            {"responseData": {"translatedText": "努力工作 &amp; 学习"}}
        ).encode()


def test_online_translation_encodes_text_and_decodes_result():
    requests = []

    def opener(request, *, timeout):
        requests.append((request.full_url, timeout))
        return _Response()

    result = translate_english_to_chinese(
        "work hard & learn",
        opener=opener,
    )

    assert result == "努力工作 & 学习"
    assert "langpair=en%7Czh-CN" in requests[0][0]
    assert "work+hard+%26+learn" in requests[0][0]
    assert requests[0][1] == 12


def test_online_translation_rejects_oversized_selection():
    with pytest.raises(ValueError, match="500"):
        translate_english_to_chinese("x" * 501)
