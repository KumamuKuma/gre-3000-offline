import sqlite3

import pytest

import gre_vocab_app.db.user as user_module
from gre_vocab_app.db.user import QueueState, UserRepository


def test_user_repository_persists_favorite_setting_progress_and_queue(tmp_path):
    path = tmp_path / "user.db"
    with UserRepository(path) as repository:
        repository.set_favorite(7, True)
        repository.set_favorite(2, True)
        repository.set_favorite(2, False)
        repository.save_setting("study_mode", "recall")
        repository.record_seen(7)
        repository.record_seen(7)
        repository.save_queue("random", [7, 2, 9], position=1, seed=44)

    with UserRepository(path) as repository:
        assert repository.is_favorite(7)
        assert not repository.is_favorite(2)
        assert repository.favorite_ids() == (7,)
        assert repository.load_setting("study_mode") == "recall"
        assert repository.load_setting("missing") is None
        assert repository.load_queue("random") == QueueState((7, 2, 9), 1, 44)
        assert repository.db.execute(
            "select seen_count from word_progress where word_id=7"
        ).fetchone()[0] == 2


def test_reset_position_and_clear_all_keep_schema_reusable(tmp_path):
    with UserRepository(tmp_path / "user.db") as repository:
        repository.set_favorite(1, True)
        repository.save_setting("browse_order", "random")
        repository.record_seen(1)
        repository.save_queue("random", [1, 2], position=1, seed=9)

        repository.reset_position("random")
        assert repository.load_queue("random").position == 0
        assert repository.load_queue("missing") == QueueState((), 0, 0)

        repository.clear_all()
        assert repository.favorite_ids() == ()
        assert repository.load_setting("browse_order") is None
        assert repository.load_queue("random") == QueueState((), 0, 0)
        assert repository.db.execute("select count(*) from word_progress").fetchone()[0] == 0

        repository.save_setting("study_mode", "reading")
        assert repository.load_setting("study_mode") == "reading"


def test_open_recovering_backs_up_corrupt_database_and_never_deletes_it(tmp_path):
    path = tmp_path / "user.db"
    original = b"this is not sqlite"
    path.write_bytes(original)

    result = UserRepository.open_recovering(path)
    try:
        assert result.recovered_from is not None
        assert result.recovered_from.exists()
        assert result.recovered_from.read_bytes() == original
        assert result.recovered_from.name.startswith("user.db.corrupt-")
        assert path.exists()
        result.repository.save_setting("study_mode", "reading")
        assert result.repository.load_setting("study_mode") == "reading"
    finally:
        result.repository.close()


def test_open_recovering_normal_missing_file_does_not_report_recovery(tmp_path):
    result = UserRepository.open_recovering(tmp_path / "user.db")
    try:
        assert result.recovered_from is None
    finally:
        result.repository.close()


def test_schema_version_is_set_and_initialization_is_idempotent(tmp_path):
    path = tmp_path / "user.db"
    with UserRepository(path) as repository:
        assert (
            repository.db.execute("pragma user_version").fetchone()[0]
            == user_module.USER_SCHEMA_VERSION
        )
    with UserRepository(path) as repository:
        tables = {
            row[0]
            for row in repository.db.execute(
                "select name from sqlite_master where type='table'"
            )
        }
        assert {"settings", "favorites", "word_progress", "session_queue"} <= tables


def test_unsupported_user_schema_is_not_mistaken_for_corruption(tmp_path):
    path = tmp_path / "user.db"
    with sqlite3.connect(path) as database:
        database.execute("pragma user_version=999")
    try:
        UserRepository.open_recovering(path)
    except ValueError as error:
        assert "version" in str(error).lower()
    else:
        raise AssertionError("unsupported schema version should fail")
    assert not list(tmp_path.glob("*.corrupt-*"))


def test_schema_initialization_rolls_back_every_table_when_script_fails(
    tmp_path, monkeypatch
):
    path = tmp_path / "user.db"
    monkeypatch.setattr(
        user_module,
        "USER_SCHEMA",
        "create table partial_table(id integer); this is invalid sql;",
    )

    with pytest.raises(sqlite3.DatabaseError):
        UserRepository(path)

    with sqlite3.connect(path) as database:
        tables = database.execute(
            "select name from sqlite_master where type='table'"
        ).fetchall()
        assert tables == []
        assert database.execute("pragma user_version").fetchone()[0] == 0


def test_seen_count_and_favorites_support_home_and_favorites_views(tmp_path):
    with UserRepository(tmp_path / "user.db") as repository:
        repository.record_seen(7)
        repository.record_seen(7)
        repository.record_seen(2)
        repository.set_favorite(1, True)
        repository.set_favorite(2, True)

        assert repository.seen_word_count() == 2
        assert repository.favorite_ids() == (2, 1)


def test_open_recovering_does_not_move_a_locked_healthy_database(tmp_path):
    path = tmp_path / "user.db"
    with UserRepository(path) as repository:
        repository.save_setting("study_mode", "recall")

    lock = sqlite3.connect(path)
    lock.execute("begin exclusive")
    try:
        error_type = getattr(user_module, "UserDatabaseError", RuntimeError)
        with pytest.raises(error_type, match="temporarily|暂时|locked"):
            UserRepository.open_recovering(path)
    finally:
        lock.rollback()
        lock.close()

    assert path.exists()
    assert not list(tmp_path.glob("*.corrupt-*"))
    with UserRepository(path) as repository:
        assert repository.load_setting("study_mode") == "recall"


def test_physically_healthy_database_with_missing_column_is_rejected_not_backed_up(
    tmp_path,
):
    path = tmp_path / "user.db"
    with sqlite3.connect(path) as database:
        database.executescript(
            """
            create table settings(key text primary key);
            create table favorites(word_id integer primary key, created_at text not null);
            create table word_progress(
              word_id integer primary key,
              seen_count integer not null,
              last_seen_at text not null
            );
            create table session_queue(
              name text primary key,
              word_ids text not null,
              position integer not null,
              seed integer not null
            );
            pragma user_version=1;
            """
        )

    error_type = getattr(user_module, "UserSchemaError", ValueError)
    with pytest.raises(error_type, match="settings|column|列"):
        UserRepository.open_recovering(path)

    assert path.exists()
    assert not list(tmp_path.glob("*.corrupt-*"))


def test_user_schema_migrates_v1_to_current_without_losing_data(tmp_path):
    path = tmp_path / "user.db"
    with sqlite3.connect(path) as database:
        database.executescript(user_module.USER_SCHEMA)
        database.execute("pragma user_version=1")
        database.execute(
            "insert into settings(key, value) values('study_mode', 'recall')"
        )

    with UserRepository(path) as repository:
        assert repository.load_setting("study_mode") == "recall"
        assert repository.db.execute("pragma user_version").fetchone()[0] >= 2
        tables = {
            row[0]
            for row in repository.db.execute(
                "select name from sqlite_master where type='table'"
            )
        }
        assert "seen_events" in tables


def test_malformed_queue_is_reset_without_losing_other_user_data(tmp_path):
    path = tmp_path / "user.db"
    with UserRepository(path) as repository:
        repository.save_setting("study_mode", "recall")
        repository.set_favorite(7, True)
        repository.save_queue("source", [1, 2], position=1, seed=0)

    with sqlite3.connect(path) as database:
        database.execute(
            "update session_queue set word_ids='[1,1]', position=9 where name='source'"
        )

    with UserRepository(path) as repository:
        assert repository.load_queue("source") == QueueState((), 0, 0)
        assert repository.load_setting("study_mode") == "recall"
        assert repository.is_favorite(7)

    with sqlite3.connect(path) as database:
        assert database.execute(
            "select 1 from session_queue where name='source'"
        ).fetchone() is None


def test_navigation_queue_and_seen_are_atomic_and_failed_write_retries(tmp_path):
    assert hasattr(UserRepository, "save_navigation")
    path = tmp_path / "user.db"
    with UserRepository(path) as repository:
        repository.save_queue("source", [1, 2], position=0, seed=0)
        repository.db.execute(
            """
            create trigger fail_seen before insert on word_progress
            begin
              select raise(abort, 'synthetic persistence failure');
            end
            """
        )

        result = repository.save_navigation(
            "source",
            [1, 2],
            position=1,
            seed=0,
            seen_word_id=2,
            event_id="navigation-2",
        )
        assert result is False
        assert repository.load_queue("source") == QueueState((1, 2), 1, 0)
        assert repository.seen_word_count() == 1

        with sqlite3.connect(path) as observer:
            assert observer.execute(
                "select position from session_queue where name='source'"
            ).fetchone()[0] == 0
            assert observer.execute("select count(*) from word_progress").fetchone()[0] == 0

        repository.db.execute("drop trigger fail_seen")
        assert repository.save_setting("study_mode", "reading") is True

    with UserRepository(path) as repository:
        assert repository.load_queue("source") == QueueState((1, 2), 1, 0)
        assert repository.db.execute(
            "select seen_count from word_progress where word_id=2"
        ).fetchone()[0] == 1
        assert repository.save_navigation(
            "source",
            [1, 2],
            position=1,
            seed=0,
            seen_word_id=2,
            event_id="navigation-2",
        ) is True
        assert repository.db.execute(
            "select seen_count from word_progress where word_id=2"
        ).fetchone()[0] == 1


def test_user_schema_rejects_wrong_column_types_and_constraints(tmp_path):
    path = tmp_path / "user.db"
    with UserRepository(path):
        pass
    with sqlite3.connect(path) as database:
        database.executescript(
            """
            alter table settings rename to settings_old;
            create table settings(
              key text primary key,
              value integer
            );
            drop table settings_old;
            """
        )

    with pytest.raises(user_module.UserSchemaError, match="settings|shape|结构"):
        UserRepository.open_recovering(path)
    assert not list(tmp_path.glob("*.corrupt-*"))


def test_queue_with_null_name_is_deleted_by_row_identity(tmp_path):
    path = tmp_path / "user.db"
    with UserRepository(path):
        pass
    with sqlite3.connect(path) as database:
        database.execute(
            "insert into session_queue(name, word_ids, position, seed) "
            "values(NULL, '[1]', 0, 0)"
        )

    with UserRepository(path) as repository:
        assert repository.load_queue("source") == QueueState((), 0, 0)

    with sqlite3.connect(path) as database:
        assert database.execute("select count(*) from session_queue").fetchone()[0] == 0


def test_successful_flush_clears_a_previous_persistence_issue(tmp_path):
    path = tmp_path / "user.db"
    repository = UserRepository(path)
    lock = sqlite3.connect(path)
    lock.execute("begin exclusive")
    try:
        assert repository.save_setting("study_mode", "recall") is False
        assert repository.has_pending_writes
    finally:
        lock.rollback()
        lock.close()

    assert repository.flush_pending() is True
    assert repository.take_persistence_issue() is None
    repository.close()


def test_close_refuses_to_drop_pending_writes_and_can_retry_after_unlock(tmp_path):
    path = tmp_path / "user.db"
    repository = UserRepository(path)
    lock = sqlite3.connect(path)
    lock.execute("begin exclusive")
    try:
        assert repository.save_setting("study_mode", "recall") is False
        assert repository.close() is False
        assert repository.has_pending_writes
    finally:
        lock.rollback()
        lock.close()

    assert repository.close() is True
    with UserRepository(path) as reopened:
        assert reopened.load_setting("study_mode") == "recall"
