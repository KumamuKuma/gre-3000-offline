import logging

import pytest

import gre_vocab_app.__main__ as main_module
from gre_vocab_app.db.content import ContentDatabaseError
from gre_vocab_app.db.user import UserDatabaseError


@pytest.mark.parametrize(
    "error",
    (
        ContentDatabaseError("synthetic content failure"),
        UserDatabaseError("synthetic user failure"),
        RuntimeError("synthetic bootstrap failure"),
    ),
)
def test_main_logs_bootstrap_failure_shows_chinese_message_and_returns_nonzero(
    qapp, monkeypatch, caplog, error
):
    def fail_bootstrap(_paths):
        raise error

    shown = []

    class MessageBoxProbe:
        @staticmethod
        def critical(parent, title, message):
            shown.append((parent, title, message))

    monkeypatch.setattr(main_module, "bootstrap", fail_bootstrap)
    monkeypatch.setattr(main_module, "QMessageBox", MessageBoxProbe, raising=False)

    with caplog.at_level(logging.ERROR):
        result = main_module.main([])

    assert result != 0
    assert len(shown) == 1
    assert shown[0][1] == "应用启动失败"
    assert "无法启动" in shown[0][2]
    assert str(error) in caplog.text
