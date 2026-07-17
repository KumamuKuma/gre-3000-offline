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


def test_release_script_stages_all_three_artifacts_then_publishes_as_a_set():
    script = (ROOT / "scripts" / "build_release.ps1").read_text(encoding="utf-8-sig")

    stage = script.index("$ReleaseCandidate")
    smoke = script.index('"native-smoke"')
    publish = script.index('"transactional release-set publication"')
    cleanup = script.index("Remove-Item -LiteralPath $ReleaseCandidate", publish)

    assert stage < smoke < publish < cleanup
    assert "Copy-Item -LiteralPath $LauncherExe -Destination $ReleaseCandidate" in script
    assert '"--audit-html", $StagedAuditHtml' in script
    assert '"--audit-html", $OutputAuditHtml' not in script
    instructions_stage = script.index(
        "Copy-Item -LiteralPath $InstructionsSource -Destination $StagedInstructions"
    )
    assert instructions_stage < smoke
    publication = script[publish:cleanup]
    assert '"--artifact", $ReleaseCandidate, $OutputExe' in publication
    assert '"--artifact", $StagedAuditHtml, $OutputAuditHtml' in publication
    assert '"--artifact", $StagedInstructions, $OutputInstructions' in publication
    assert '"--artifact", $StagedInstructions, $InstructionsSource' not in publication
    assert '"publish"' not in publication
    assert "Remove-Item -LiteralPath $OutputExe" not in script


def test_release_script_enforces_the_exact_three_file_output_allowlist():
    script = (ROOT / "scripts" / "build_release.ps1").read_text(encoding="utf-8-sig")

    assert "$ExpectedOutputNames = @(" in script
    assert '"GRE 3000 词离线版.exe"' in script
    assert '"使用说明.txt"' in script
    assert '"词库导入审计报告.html"' in script
    assert script.count("Assert-ReleaseOutputAllowlist") >= 3
    assert "Unexpected release output entries" in script


def test_release_script_verifies_the_current_strict_reviewed_count():
    script = (ROOT / "scripts" / "build_release.ps1").read_text(encoding="utf-8-sig")

    assert '"--expected-reviewed", "5"' in script
    assert '"--expected-reviewed", "4"' not in script
