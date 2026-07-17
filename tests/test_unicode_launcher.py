from __future__ import annotations

import sys
from pathlib import Path

import pytest


def test_embedded_runtime_is_resolved_relative_to_launcher(tmp_path: Path):
    from scripts.unicode_launcher import RUNTIME_NAME, embedded_runtime_path

    launcher_file = tmp_path / "bundle" / "unicode_launcher.py"
    expected = launcher_file.parent / "runtime" / RUNTIME_NAME

    assert RUNTIME_NAME.isascii()
    assert embedded_runtime_path(launcher_file) == expected


def test_launch_runtime_waits_for_a_real_ascii_child_and_returns_its_exit_code(
    tmp_path: Path,
):
    from scripts.unicode_launcher import launch_runtime

    marker = tmp_path / "child-finished.txt"
    exit_code = launch_runtime(
        Path(sys.executable),
        (
            "-c",
            "import pathlib, sys; pathlib.Path(sys.argv[1]).write_text('done'); sys.exit(7)",
            str(marker),
        ),
    )

    assert marker.read_text() == "done"
    assert exit_code == 7


def test_launch_runtime_rejects_a_missing_embedded_child(tmp_path: Path):
    from scripts.unicode_launcher import launch_runtime

    missing = tmp_path / "GRE3000OfflineRuntime.exe"
    with pytest.raises(FileNotFoundError, match="GRE3000OfflineRuntime"):
        launch_runtime(missing)


def test_production_main_forwards_real_arguments_and_inherits_callers_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import scripts.unicode_launcher as launcher

    marker = tmp_path / "runtime-observation.txt"
    runtime_code = (
        "import os, pathlib, sys; "
        "pathlib.Path(sys.argv[1]).write_text(os.getcwd() + '\\n' + '|'.join(sys.argv[2:]))"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(launcher, "embedded_runtime_path", lambda: Path(sys.executable))
    monkeypatch.setattr(
        sys,
        "argv",
        ["GRE-outer.exe", "-c", runtime_code, str(marker), "alpha", "\u4e2d\u6587"],
    )

    assert launcher.main() == 0
    observed_cwd, observed_arguments = marker.read_text().splitlines()
    assert Path(observed_cwd) == tmp_path
    assert observed_arguments == "alpha|\u4e2d\u6587"
