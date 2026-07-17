from __future__ import annotations

import os
from pathlib import Path

import pytest


def _temporary_release_files(directory: Path) -> list[Path]:
    return [
        path
        for path in directory.iterdir()
        if ".candidate-" in path.name or ".backup-" in path.name
    ]


def test_publish_release_set_replaces_all_three_release_artifacts_together(
    tmp_path: Path,
):
    from scripts.publish_release_set import publish_release_set

    candidates = tmp_path / "build"
    outputs = tmp_path / "outputs"
    candidates.mkdir()
    outputs.mkdir()
    candidate_exe = candidates / "release.exe"
    candidate_audit = candidates / "audit.html"
    candidate_instructions = candidates / "instructions.txt"
    output_exe = outputs / "release.exe"
    output_audit = outputs / "audit.html"
    output_instructions = outputs / "instructions.txt"
    candidate_exe.write_bytes(b"new-exe")
    candidate_audit.write_text("new-audit", encoding="utf-8")
    candidate_instructions.write_text("new-instructions", encoding="utf-8")
    output_exe.write_bytes(b"old-exe")
    output_audit.write_text("old-audit", encoding="utf-8")
    output_instructions.write_text("old-instructions", encoding="utf-8")

    publish_release_set(
        (
            (candidate_exe, output_exe),
            (candidate_audit, output_audit),
            (candidate_instructions, output_instructions),
        )
    )

    assert output_exe.read_bytes() == b"new-exe"
    assert output_audit.read_text(encoding="utf-8") == "new-audit"
    assert output_instructions.read_text(encoding="utf-8") == "new-instructions"
    assert candidate_exe.read_bytes() == b"new-exe"
    assert candidate_audit.read_text(encoding="utf-8") == "new-audit"
    assert candidate_instructions.read_text(encoding="utf-8") == "new-instructions"
    assert _temporary_release_files(outputs) == []


def test_second_replacement_failure_restores_all_three_old_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from scripts import publish_release_set as publication

    candidates = tmp_path / "build"
    outputs = tmp_path / "outputs"
    candidates.mkdir()
    outputs.mkdir()
    candidate_exe = candidates / "release.exe"
    candidate_audit = candidates / "audit.html"
    candidate_instructions = candidates / "instructions.txt"
    output_exe = outputs / "release.exe"
    output_audit = outputs / "audit.html"
    output_instructions = outputs / "instructions.txt"
    candidate_exe.write_bytes(b"new-exe")
    candidate_audit.write_text("new-audit", encoding="utf-8")
    candidate_instructions.write_text("new-instructions", encoding="utf-8")
    output_exe.write_bytes(b"old-exe")
    output_audit.write_text("old-audit", encoding="utf-8")
    output_instructions.write_text("old-instructions", encoding="utf-8")

    real_replace = os.replace

    def fail_on_audit_candidate(source, destination):
        source_path = Path(source)
        destination_path = Path(destination)
        if (
            destination_path == output_audit
            and ".candidate-" in source_path.name
        ):
            raise OSError("injected second replacement failure")
        real_replace(source, destination)

    monkeypatch.setattr(publication.os, "replace", fail_on_audit_candidate)

    with pytest.raises(OSError, match="injected second replacement failure"):
        publication.publish_release_set(
            (
                (candidate_exe, output_exe),
                (candidate_audit, output_audit),
                (candidate_instructions, output_instructions),
            )
        )

    assert output_exe.read_bytes() == b"old-exe"
    assert output_audit.read_text(encoding="utf-8") == "old-audit"
    assert output_instructions.read_text(encoding="utf-8") == "old-instructions"
    assert candidate_exe.read_bytes() == b"new-exe"
    assert candidate_audit.read_text(encoding="utf-8") == "new-audit"
    assert candidate_instructions.read_text(encoding="utf-8") == "new-instructions"
    assert _temporary_release_files(outputs) == []


def test_command_line_publishes_the_complete_three_artifact_set(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    from scripts.publish_release_set import main

    candidates = tmp_path / "build"
    outputs = tmp_path / "outputs"
    candidates.mkdir()
    outputs.mkdir()
    candidate_exe = candidates / "release.exe"
    candidate_audit = candidates / "audit.html"
    candidate_instructions = candidates / "instructions.txt"
    output_exe = outputs / "release.exe"
    output_audit = outputs / "audit.html"
    output_instructions = outputs / "instructions.txt"
    candidate_exe.write_bytes(b"new-exe")
    candidate_audit.write_text("new-audit", encoding="utf-8")
    candidate_instructions.write_text("new-instructions", encoding="utf-8")

    exit_code = main(
        [
            "--artifact",
            str(candidate_exe),
            str(output_exe),
            "--artifact",
            str(candidate_audit),
            str(output_audit),
            "--artifact",
            str(candidate_instructions),
            str(output_instructions),
        ]
    )

    assert exit_code == 0
    assert output_exe.read_bytes() == b"new-exe"
    assert output_audit.read_text(encoding="utf-8") == "new-audit"
    assert output_instructions.read_text(encoding="utf-8") == "new-instructions"
    assert "release_set_published artifacts=3" in capsys.readouterr().out


def test_publish_release_set_rejects_an_incomplete_single_artifact_set(
    tmp_path: Path,
):
    from scripts.publish_release_set import publish_release_set

    candidate = tmp_path / "candidate.exe"
    output = tmp_path / "output.exe"
    candidate.write_bytes(b"candidate")

    with pytest.raises(ValueError, match="exactly three artifacts"):
        publish_release_set(((candidate, output),))

    assert not output.exists()
