from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_atomic_publish_replaces_old_release_only_after_candidate_is_ready(
    tmp_path: Path,
):
    from scripts.windows_release_probe import publish_release_candidate

    candidate = tmp_path / "build" / "release-candidate.exe"
    output = tmp_path / "outputs" / "release.exe"
    candidate.parent.mkdir()
    output.parent.mkdir()
    candidate.write_bytes(b"verified-new-release")
    output.write_bytes(b"known-good-old-release")

    publish_release_candidate(candidate, output)

    assert output.read_bytes() == b"verified-new-release"
    assert not candidate.exists()


def test_release_script_smokes_build_candidate_before_atomic_publish_and_cleanup():
    script = (ROOT / "scripts" / "build_release.ps1").read_text(encoding="utf-8-sig")

    stage = script.index("$ReleaseCandidate")
    smoke = script.index('"native-smoke"')
    publish = script.index('"publish"')
    cleanup = script.index("Remove-Item -LiteralPath $ReleaseCandidate", publish)

    assert stage < smoke < publish < cleanup
    assert "Copy-Item -LiteralPath $LauncherExe -Destination $ReleaseCandidate" in script
    assert "Remove-Item -LiteralPath $OutputExe" not in script


def test_release_script_verifies_the_current_strict_reviewed_count():
    script = (ROOT / "scripts" / "build_release.ps1").read_text(encoding="utf-8-sig")

    assert '"--expected-reviewed", "5"' in script
    assert '"--expected-reviewed", "4"' not in script
