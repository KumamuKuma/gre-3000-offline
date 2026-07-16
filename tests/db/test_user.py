import sqlite3

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
        assert repository.db.execute("pragma user_version").fetchone()[0] == 1
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

