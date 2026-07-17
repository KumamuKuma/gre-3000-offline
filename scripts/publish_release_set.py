from __future__ import annotations

import argparse
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True, slots=True)
class ReleaseArtifact:
    source: Path
    target: Path
    candidate: Path
    backup: Path
    had_original: bool


class ReleaseRollbackError(RuntimeError):
    """Raised when publication fails and an old release cannot be restored."""


def _canonical(path: Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def _prepare_artifacts(
    pairs: Sequence[tuple[Path, Path]],
) -> tuple[ReleaseArtifact, ...]:
    if len(pairs) != 3:
        raise ValueError("release publication requires exactly three artifacts")

    sources = tuple(Path(source).resolve(strict=True) for source, _ in pairs)
    targets = tuple(Path(target).resolve(strict=False) for _, target in pairs)
    if len({_canonical(path) for path in sources}) != len(sources):
        raise ValueError("release candidate paths must be distinct")
    if len({_canonical(path) for path in targets}) != len(targets):
        raise ValueError("release output paths must be distinct")

    token = uuid.uuid4().hex
    artifacts: list[ReleaseArtifact] = []
    for source, target in zip(sources, targets, strict=True):
        if not source.is_file():
            raise ValueError(f"release candidate is not a file: {source}")
        if source.stat().st_size <= 0:
            raise ValueError(f"release candidate is empty: {source}")
        if _canonical(source) == _canonical(target):
            raise ValueError("release candidate and output paths must be different")
        if not target.parent.is_dir():
            raise FileNotFoundError(
                f"release output directory not found: {target.parent}"
            )
        if target.exists() and not target.is_file():
            raise ValueError(f"release output path is not a file: {target}")
        artifacts.append(
            ReleaseArtifact(
                source=source,
                target=target,
                candidate=target.with_name(f".{target.name}.candidate-{token}"),
                backup=target.with_name(f".{target.name}.backup-{token}"),
                had_original=target.exists(),
            )
        )
    return tuple(artifacts)


def _unlink_temporary_files(
    artifacts: Sequence[ReleaseArtifact], *, include_backups: bool
) -> None:
    for artifact in artifacts:
        artifact.candidate.unlink(missing_ok=True)
        if include_backups:
            artifact.backup.unlink(missing_ok=True)


def _restore_old_release(artifacts: Sequence[ReleaseArtifact]) -> None:
    failures: list[str] = []
    for artifact in reversed(artifacts):
        try:
            if artifact.had_original:
                os.replace(artifact.backup, artifact.target)
            else:
                artifact.target.unlink(missing_ok=True)
        except OSError as error:
            failures.append(f"{artifact.target}: {error}")
    if failures:
        raise ReleaseRollbackError(
            "release-set rollback failed; backups were retained: "
            + "; ".join(failures)
        )


def publish_release_set(pairs: Sequence[tuple[Path, Path]]) -> None:
    """Publish the verified EXE, audit, and instructions as one safe set."""

    artifacts = _prepare_artifacts(tuple(pairs))
    published: list[ReleaseArtifact] = []
    keep_backups = False
    try:
        for artifact in artifacts:
            shutil.copy2(artifact.source, artifact.candidate)
            if artifact.candidate.stat().st_size != artifact.source.stat().st_size:
                raise OSError(f"staged candidate size mismatch: {artifact.source}")
        for artifact in artifacts:
            if artifact.had_original:
                shutil.copy2(artifact.target, artifact.backup)
        for artifact in artifacts:
            os.replace(artifact.candidate, artifact.target)
            published.append(artifact)
    except BaseException as publish_error:
        try:
            _restore_old_release(published)
        except ReleaseRollbackError as rollback_error:
            keep_backups = True
            raise rollback_error from publish_error
        raise
    finally:
        _unlink_temporary_files(artifacts, include_backups=not keep_backups)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Transactionally publish the verified GRE release artifact set."
    )
    parser.add_argument(
        "--artifact",
        action="append",
        nargs=2,
        metavar=("CANDIDATE", "OUTPUT"),
        type=Path,
        required=True,
        help="Candidate and final output path; provide exactly three times.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    pairs = tuple((source, target) for source, target in arguments.artifact)
    publish_release_set(pairs)
    print("release_set_published artifacts=3 rollback_backups=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
