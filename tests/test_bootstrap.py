import logging
import sqlite3
from logging.handlers import RotatingFileHandler

import pytest

from gre_vocab_app.bootstrap import ContentDatabaseError, bootstrap
from gre_vocab_app.importer.build import build_database
from gre_vocab_app.importer.normalize import WordDraft
from gre_vocab_app.paths import AppPaths


@pytest.fixture
def content_db(tmp_path):
    path = tmp_path / "words.db"
    build_database(
        [
            WordDraft(
                source_order=1,
                source_section="list1",
                source_page=5,
                headword="abate",
                phonetic="[əˈbeɪt]",
                definition_en="v. become less intense",
                definition_zh="减轻",
                synonyms="subside",
                example_en="The storm began to abate.",
                example_zh="暴风雨开始减弱。",
                raw_definition="v. become less intense 减轻",
                raw_example="The storm began to abate. 暴风雨开始减弱。",
                quality_flags=(),
            )
        ],
        path,
    )
    return path


def test_bootstrap_refuses_missing_content_database(tmp_path):
    paths = AppPaths.resolve(
        content_override=tmp_path / "missing.db", user_root=tmp_path / "user"
    )
    with pytest.raises(ContentDatabaseError, match="词库文件缺失"):
        bootstrap(paths)


def test_bootstrap_refuses_incompatible_content_database(content_db, tmp_path):
    with sqlite3.connect(content_db) as database:
        database.execute("update metadata set value='999' where key='schema_version'")
    paths = AppPaths.resolve(content_override=content_db, user_root=tmp_path / "user")

    with pytest.raises(ContentDatabaseError, match="词库版本不兼容"):
        bootstrap(paths)


def test_bootstrap_refuses_content_database_that_fails_integrity_check(
    content_db, tmp_path
):
    content_db.write_bytes(content_db.read_bytes()[:256])
    paths = AppPaths.resolve(content_override=content_db, user_root=tmp_path / "user")

    with pytest.raises(ContentDatabaseError, match="词库完整性检查失败"):
        bootstrap(paths)


def test_bootstrap_recovers_corrupt_user_database(content_db, tmp_path, qapp):
    paths = AppPaths.resolve(content_override=content_db, user_root=tmp_path)
    paths.user_db.write_bytes(b"not sqlite")

    result = bootstrap(paths)
    try:
        assert result.recovery_notice
        assert list(tmp_path.glob("user.db.corrupt-*"))
    finally:
        result.window.close()
        result.controller.content.close()
        result.controller.user.close()


def test_bootstrap_configures_one_megabyte_rotating_local_log(
    content_db, tmp_path, qapp
):
    paths = AppPaths.resolve(content_override=content_db, user_root=tmp_path / "user")

    result = bootstrap(paths)
    try:
        matching = [
            handler
            for handler in logging.getLogger().handlers
            if isinstance(handler, RotatingFileHandler)
            and handler.baseFilename == str(paths.log_file.resolve())
        ]
        assert paths.log_file.parent.is_dir()
        assert len(matching) == 1
        assert matching[0].maxBytes == 1024 * 1024
        assert matching[0].backupCount == 3
    finally:
        result.window.close()
        result.controller.content.close()
        result.controller.user.close()
