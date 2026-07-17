import logging
import sqlite3

import pytest

import gre_vocab_app.__main__ as main_module
from gre_vocab_app.db.content import ContentDatabaseError
from gre_vocab_app.db.user import UserDatabaseError
from gre_vocab_app.importer.build import build_database
from gre_vocab_app.importer.normalize import WordDraft
from gre_vocab_app.paths import AppPaths


def _draft(word: str, order: int) -> WordDraft:
    return WordDraft(
        source_order=order,
        source_section="list1",
        source_page=5,
        headword=word,
        phonetic="[x]",
        definition_en="adj. sample",
        definition_zh="示例",
        synonyms="",
        example_en="",
        example_zh="",
        raw_definition="adj. sample 示例",
        raw_example="",
        quality_flags=(),
    )


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


def test_main_rejects_invalid_nonfirst_content_row_before_creating_user_db(
    qapp, tmp_path, monkeypatch, caplog
):
    content_path = tmp_path / "words.db"
    build_database([_draft("abate", 1), _draft("bad", 2)], content_path)
    with sqlite3.connect(content_path) as database:
        database.execute("update words set headword='' where source_order=2")

    paths = AppPaths(
        content_path,
        tmp_path / "user-data" / "user.db",
        tmp_path / "user-data" / "logs" / "app.log",
    )
    monkeypatch.setattr(
        main_module.AppPaths,
        "resolve",
        classmethod(lambda cls: paths),
    )
    shown = []

    class MessageBoxProbe:
        @staticmethod
        def critical(parent, title, message):
            shown.append((parent, title, message))

    monkeypatch.setattr(main_module, "QMessageBox", MessageBoxProbe)
    captured = []
    real_bootstrap = main_module.bootstrap

    def capture_bootstrap(app_paths):
        result = real_bootstrap(app_paths)
        captured.append(result)
        return result

    monkeypatch.setattr(main_module, "bootstrap", capture_bootstrap)
    try:
        with caplog.at_level(logging.ERROR):
            result = main_module.main([])
    finally:
        if captured:
            captured[0].window.close()
            captured[0].controller.shutdown()

    assert result == 20
    assert shown and shown[0][1] == "应用启动失败"
    assert "headword" in caplog.text
    assert not paths.user_db.exists()


def test_main_reports_log_initialization_failure_truthfully(
    qapp, tmp_path, monkeypatch
):
    paths = AppPaths(
        tmp_path / "words.db",
        tmp_path / "user" / "user.db",
        tmp_path / "blocked" / "app.log",
    )
    error = PermissionError("synthetic log directory denial")
    monkeypatch.setattr(
        main_module.AppPaths,
        "resolve",
        classmethod(lambda cls: paths),
    )
    monkeypatch.setattr(
        main_module,
        "bootstrap",
        lambda _paths: (_ for _ in ()).throw(error),
    )
    shown = []

    class MessageBoxProbe:
        @staticmethod
        def critical(parent, title, message):
            shown.append((parent, title, message))

    monkeypatch.setattr(main_module, "QMessageBox", MessageBoxProbe)

    assert main_module.main([]) == 20
    assert len(shown) == 1
    assert shown[0][1] == "应用启动失败"
    assert "PermissionError" in shown[0][2]
    assert str(error) in shown[0][2]
    assert str(paths.log_file) in shown[0][2]
    assert "若可写" in shown[0][2]
    assert "已写入" not in shown[0][2]
