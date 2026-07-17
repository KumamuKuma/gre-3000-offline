from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import pytest


def _temporary_release_files(directory: Path) -> list[Path]:
    return [
        path
        for path in directory.iterdir()
        if ".candidate-" in path.name or ".backup-" in path.name
    ]


def _release_paths(
    tmp_path: Path,
) -> tuple[Path, Path, tuple[tuple[Path, Path], ...]]:
    candidates = tmp_path / "build"
    outputs = tmp_path / "outputs"
    candidates.mkdir()
    outputs.mkdir()
    sources = (
        candidates / "release.exe",
        candidates / "audit.html",
        candidates / "instructions.txt",
    )
    targets = (
        outputs / "release.exe",
        outputs / "audit.html",
        outputs / "instructions.txt",
    )
    for index, source in enumerate(sources):
        source.write_bytes(f"new-{index}".encode())
    return candidates, outputs, tuple(zip(sources, targets, strict=True))


def _temporary_files_in(*directories: Path) -> list[Path]:
    return [
        path
        for directory in directories
        for path in directory.iterdir()
        if any(marker in path.name for marker in (".candidate-", ".backup-"))
    ]


def _notes(error: BaseException) -> str:
    return "\n".join(getattr(error, "__notes__", ()))


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


def test_third_replacement_failure_restores_all_three_old_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from scripts import publish_release_set as publication

    candidates, outputs, pairs = _release_paths(tmp_path)
    for index, (_, target) in enumerate(pairs):
        target.write_bytes(f"old-{index}".encode())

    real_replace = os.replace

    def fail_on_third_candidate(source, destination):
        source_path = Path(source)
        destination_path = Path(destination)
        if destination_path == pairs[2][1] and ".candidate-" in source_path.name:
            raise OSError("injected third replacement failure")
        real_replace(source, destination)

    monkeypatch.setattr(publication.os, "replace", fail_on_third_candidate)

    with pytest.raises(OSError, match="injected third replacement failure"):
        publication.publish_release_set(pairs)

    for index, (_, target) in enumerate(pairs):
        assert target.read_bytes() == f"old-{index}".encode()
    assert _temporary_files_in(candidates, outputs) == []


@pytest.mark.parametrize("old_target_indexes", ((0, 2), ()))
def test_third_replacement_failure_restores_originally_missing_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    old_target_indexes: Iterable[int],
):
    from scripts import publish_release_set as publication

    candidates, outputs, pairs = _release_paths(tmp_path)
    old_target_indexes = tuple(old_target_indexes)
    for index in old_target_indexes:
        pairs[index][1].write_bytes(f"old-{index}".encode())

    real_replace = os.replace

    def fail_on_third_candidate(source, destination):
        source_path = Path(source)
        destination_path = Path(destination)
        if destination_path == pairs[2][1] and ".candidate-" in source_path.name:
            raise OSError("injected third replacement failure")
        real_replace(source, destination)

    monkeypatch.setattr(publication.os, "replace", fail_on_third_candidate)

    with pytest.raises(OSError, match="injected third replacement failure"):
        publication.publish_release_set(pairs)

    for index, (_, target) in enumerate(pairs):
        if index in old_target_indexes:
            assert target.read_bytes() == f"old-{index}".encode()
        else:
            assert not target.exists()
    assert _temporary_files_in(candidates, outputs) == []


def test_rollback_failure_chains_publication_error_and_retains_build_backups(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from scripts import publish_release_set as publication

    candidates, outputs, pairs = _release_paths(tmp_path)
    for index, (_, target) in enumerate(pairs):
        target.write_bytes(f"old-{index}".encode())

    real_replace = os.replace
    publication_failed = False

    def fail_publish_then_rollback(source, destination):
        nonlocal publication_failed
        source_path = Path(source)
        destination_path = Path(destination)
        if destination_path == pairs[2][1] and ".candidate-" in source_path.name:
            publication_failed = True
            raise OSError("injected publication failure")
        if publication_failed and destination_path == pairs[0][1]:
            raise OSError("injected rollback failure")
        real_replace(source, destination)

    monkeypatch.setattr(publication.os, "replace", fail_publish_then_rollback)

    with pytest.raises(publication.ReleaseRollbackError) as raised:
        publication.publish_release_set(pairs)

    assert isinstance(raised.value.__cause__, OSError)
    assert "injected publication failure" in str(raised.value.__cause__)
    assert "backups were retained" in str(raised.value)
    retained_backups = [
        path for path in candidates.iterdir() if ".backup-" in path.name
    ]
    assert len(retained_backups) == 3
    assert _temporary_release_files(outputs) == []


def test_cleanup_failure_does_not_mask_publication_error_and_adds_note(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from scripts import publish_release_set as publication

    candidates, outputs, pairs = _release_paths(tmp_path)
    for index, (_, target) in enumerate(pairs):
        target.write_bytes(f"old-{index}".encode())

    real_replace = os.replace
    real_unlink = Path.unlink

    def fail_on_third_candidate(source, destination):
        source_path = Path(source)
        destination_path = Path(destination)
        if destination_path == pairs[2][1] and ".candidate-" in source_path.name:
            raise OSError("injected publication failure")
        real_replace(source, destination)

    failed_cleanup = False

    def fail_one_backup_cleanup(path: Path, *args, **kwargs):
        nonlocal failed_cleanup
        if ".backup-" in path.name and not failed_cleanup:
            failed_cleanup = True
            raise PermissionError("injected backup cleanup failure")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(publication.os, "replace", fail_on_third_candidate)
    monkeypatch.setattr(Path, "unlink", fail_one_backup_cleanup)

    with pytest.raises(OSError, match="injected publication failure") as raised:
        publication.publish_release_set(pairs)

    assert "cleanup was incomplete" in _notes(raised.value)
    assert "injected backup cleanup failure" in _notes(raised.value)
    assert _temporary_release_files(outputs) == []
    assert len([path for path in candidates.iterdir() if ".backup-" in path.name]) == 1


def test_candidate_cleanup_failure_does_not_mask_rollback_error_or_pollute_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from scripts import publish_release_set as publication

    candidates, outputs, pairs = _release_paths(tmp_path)
    for index, (_, target) in enumerate(pairs):
        target.write_bytes(f"old-{index}".encode())

    real_replace = os.replace
    real_unlink = Path.unlink
    publication_failed = False

    def fail_publish_then_rollback(source, destination):
        nonlocal publication_failed
        source_path = Path(source)
        destination_path = Path(destination)
        if destination_path == pairs[2][1] and ".candidate-" in source_path.name:
            publication_failed = True
            raise OSError("injected publication failure")
        if publication_failed and destination_path == pairs[0][1]:
            raise OSError("injected rollback failure")
        real_replace(source, destination)

    failed_cleanup = False

    def fail_one_candidate_cleanup(path: Path, *args, **kwargs):
        nonlocal failed_cleanup
        if ".candidate-" in path.name and not failed_cleanup:
            failed_cleanup = True
            raise PermissionError("injected candidate cleanup failure")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(publication.os, "replace", fail_publish_then_rollback)
    monkeypatch.setattr(Path, "unlink", fail_one_candidate_cleanup)

    with pytest.raises(publication.ReleaseRollbackError) as raised:
        publication.publish_release_set(pairs)

    assert isinstance(raised.value.__cause__, OSError)
    assert "injected publication failure" in str(raised.value.__cause__)
    assert "cleanup was incomplete" in _notes(raised.value)
    assert "injected candidate cleanup failure" in _notes(raised.value)
    assert _temporary_release_files(outputs) == []
    assert any(".candidate-retained-" in path.name for path in candidates.iterdir())


def test_failed_candidate_quarantine_is_reported_without_masking_publish_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from scripts import publish_release_set as publication

    _, outputs, pairs = _release_paths(tmp_path)
    for index, (_, target) in enumerate(pairs):
        target.write_bytes(f"old-{index}".encode())

    real_replace = os.replace
    real_unlink = Path.unlink

    def fail_publish_and_quarantine(source, destination):
        source_path = Path(source)
        destination_path = Path(destination)
        if destination_path == pairs[2][1] and ".candidate-" in source_path.name:
            raise OSError("injected publication failure")
        if ".candidate-retained-" in destination_path.name:
            raise PermissionError("injected quarantine failure")
        real_replace(source, destination)

    failed_cleanup = False

    def fail_one_candidate_cleanup(path: Path, *args, **kwargs):
        nonlocal failed_cleanup
        if ".candidate-" in path.name and not failed_cleanup:
            failed_cleanup = True
            raise PermissionError("injected candidate cleanup failure")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(publication.os, "replace", fail_publish_and_quarantine)
    monkeypatch.setattr(Path, "unlink", fail_one_candidate_cleanup)

    with pytest.raises(OSError, match="injected publication failure") as raised:
        publication.publish_release_set(pairs)

    assert "injected candidate cleanup failure" in _notes(raised.value)
    assert "injected quarantine failure" in _notes(raised.value)
    assert len(_temporary_release_files(outputs)) == 1


def test_successful_publication_warns_when_build_backup_cleanup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from scripts import publish_release_set as publication

    candidates, outputs, pairs = _release_paths(tmp_path)
    for index, (_, target) in enumerate(pairs):
        target.write_bytes(f"old-{index}".encode())

    real_unlink = Path.unlink
    failed_cleanup = False

    def fail_one_backup_cleanup(path: Path, *args, **kwargs):
        nonlocal failed_cleanup
        if ".backup-" in path.name and not failed_cleanup:
            failed_cleanup = True
            raise PermissionError("injected backup cleanup failure")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_one_backup_cleanup)

    with pytest.warns(publication.ReleaseCleanupWarning) as captured:
        publication.publish_release_set(pairs)

    for index, (_, target) in enumerate(pairs):
        assert target.read_bytes() == f"new-{index}".encode()
    warning_text = str(captured[0].message)
    assert "published successfully" in warning_text
    assert "injected backup cleanup failure" in warning_text
    assert "delete retained files manually" in warning_text
    assert _temporary_release_files(outputs) == []
    assert len([path for path in candidates.iterdir() if ".backup-" in path.name]) == 1


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
