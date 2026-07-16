from pathlib import Path

from gre_vocab_app.paths import AppPaths


def test_app_paths_keep_content_read_only_and_user_data_separate(tmp_path: Path):
    content = tmp_path / "bundle" / "words.db"
    user_root = tmp_path / "profile"

    paths = AppPaths.resolve(content_override=content, user_root=user_root)

    assert paths.content_db == content
    assert paths.user_db == user_root / "user.db"
    assert paths.log_file == user_root / "logs" / "app.log"
