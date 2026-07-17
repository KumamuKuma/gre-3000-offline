from __future__ import annotations

import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True, slots=True)
class ArtifactSlot:
    target: Path
    candidate: Path
    backup: Path
    had_original: bool


def _canonical(path: Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def plan_artifact_publication(
    targets: Iterable[Path],
) -> tuple[ArtifactSlot, ...]:
    ordered = tuple(Path(target) for target in targets)
    canonical = [_canonical(path) for path in ordered]
    if len(set(canonical)) != len(canonical):
        raise ValueError("artifact output paths must be distinct")

    token = uuid.uuid4().hex
    slots: list[ArtifactSlot] = []
    for target in ordered:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not target.is_file():
            raise ValueError(f"artifact output path is not a file: {target}")
        slots.append(
            ArtifactSlot(
                target=target,
                candidate=target.with_name(
                    f".{target.name}.candidate-{token}"
                ),
                backup=target.with_name(f".{target.name}.backup-{token}"),
                had_original=target.exists(),
            )
        )
    return tuple(slots)


def cleanup_artifact_slots(slots: Sequence[ArtifactSlot]) -> None:
    for slot in slots:
        slot.candidate.unlink(missing_ok=True)
        slot.backup.unlink(missing_ok=True)


def _restore_published(slots: Sequence[ArtifactSlot]) -> None:
    failures: list[str] = []
    for slot in reversed(slots):
        try:
            if slot.had_original:
                os.replace(slot.backup, slot.target)
            else:
                slot.target.unlink(missing_ok=True)
        except OSError as error:
            failures.append(f"{slot.target}: {error}")
    if failures:
        raise RuntimeError(
            "artifact rollback failed: " + "; ".join(failures)
        )


def publish_artifact_slots(slots: Sequence[ArtifactSlot]) -> None:
    if any(not slot.candidate.is_file() for slot in slots):
        raise ValueError("artifact candidate set is incomplete")

    published: list[ArtifactSlot] = []
    try:
        for slot in slots:
            if slot.had_original:
                shutil.copy2(slot.target, slot.backup)
        for slot in slots:
            os.replace(slot.candidate, slot.target)
            published.append(slot)
    except BaseException as publish_error:
        try:
            _restore_published(published)
        except RuntimeError as rollback_error:
            raise rollback_error from publish_error
        raise
    finally:
        cleanup_artifact_slots(slots)
