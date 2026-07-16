from pathlib import Path

from gre_vocab_app import paths as paths_module
from gre_vocab_app.paths import AppPaths


def test_packaged_content_override_points_to_embedded_database(
    tmp_path: Path, monkeypatch
):
    bundled = tmp_path / "bundle" / "gre_vocab_app" / "data" / "words.db"
    bundled.parent.mkdir(parents=True)
    bundled.write_bytes(b"content")

    monkeypatch.delenv("GRE_WORDS_DB", raising=False)
    monkeypatch.setattr(paths_module, "PACKAGE_ROOT", bundled.parents[1])

    assert AppPaths.resolve(user_root=tmp_path / "user").content_db == bundled
