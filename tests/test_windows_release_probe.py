from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows release probe")

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "scripts" / "windows_release_probe.py"
PYTHONW = Path(sys.executable).with_name("pythonw.exe")
IMAGE_FILE_MACHINE_AMD64 = 0x8664
IMAGE_SUBSYSTEM_WINDOWS_GUI = 2
IMAGE_SUBSYSTEM_WINDOWS_CUI = 3


def _hidden_new_console_startup() -> subprocess.STARTUPINFO:
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    return startup


def _terminate(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def test_pe_metadata_reads_real_x64_console_and_gui_binaries():
    from scripts.windows_release_probe import read_pe_metadata

    console = read_pe_metadata(Path(sys.executable))
    assert console.machine == IMAGE_FILE_MACHINE_AMD64
    assert console.subsystem == IMAGE_SUBSYSTEM_WINDOWS_CUI

    assert PYTHONW.is_file()
    gui = read_pe_metadata(PYTHONW)
    assert gui.machine == IMAGE_FILE_MACHINE_AMD64
    assert gui.subsystem == IMAGE_SUBSYSTEM_WINDOWS_GUI


def test_console_probe_detects_hidden_console_and_no_console_controls():
    console_process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        startupinfo=_hidden_new_console_startup(),
    )
    gui_process = subprocess.Popen(
        [str(PYTHONW), "-c", "import time; time.sleep(30)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(0.25)
        console_probe = subprocess.run(
            [sys.executable, str(PROBE), "console", "--pid", str(console_process.pid)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert console_probe.returncode == 10
        assert "has_console=true" in console_probe.stdout

        gui_probe = subprocess.run(
            [sys.executable, str(PROBE), "console", "--pid", str(gui_process.pid)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert gui_probe.returncode == 0
        assert "has_console=false" in gui_probe.stdout
        assert "winerror=6" in gui_probe.stdout
    finally:
        _terminate(gui_process)
        _terminate(console_process)


def test_console_probe_cli_survives_an_uncaptured_real_console():
    gui_process = subprocess.Popen(
        [str(PYTHONW), "-c", "import time; time.sleep(30)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        probe = subprocess.Popen(
            [sys.executable, str(PROBE), "console", "--pid", str(gui_process.pid)],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            startupinfo=_hidden_new_console_startup(),
        )
        assert probe.wait(timeout=10) == 0
    finally:
        _terminate(gui_process)


def test_job_tracks_a_delayed_real_descendant_created_after_initial_observation(
    tmp_path: Path,
):
    from scripts.windows_release_probe import JobSupervisor

    marker = tmp_path / "delayed-child.pid"
    child_code = (
        "import os, pathlib, sys, time; "
        "pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); "
        "time.sleep(0.75)"
    )
    parent_code = (
        "import subprocess, sys, time; "
        "time.sleep(0.25); "
        "child=subprocess.Popen([sys.executable, '-c', sys.argv[2], sys.argv[1]]); "
        "child.wait()"
    )
    with JobSupervisor.start(
        [sys.executable, "-c", parent_code, str(marker), child_code]
    ) as job:
        assert job.active_process_count() == 1
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.025)
        child_pid = int(marker.read_text())
        assert job.contains_process(child_pid)
        assert job.wait_for_empty(timeout_seconds=5) == 0


def test_job_close_kills_a_lingering_descendant_born_after_the_root_exits(
    tmp_path: Path,
):
    from scripts.windows_release_probe import JobSupervisor, wait_for_process_exit

    marker = tmp_path / "lingering-child.pid"
    child_code = (
        "import os, pathlib, sys, time; "
        "pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); "
        "time.sleep(30)"
    )
    parent_code = (
        "import subprocess, sys, time; "
        "time.sleep(0.25); "
        "subprocess.Popen([sys.executable, '-c', sys.argv[2], sys.argv[1]])"
    )
    job = JobSupervisor.start(
        [sys.executable, "-c", parent_code, str(marker), child_code]
    )
    try:
        assert job.wait_for_root(timeout_seconds=5) == 0
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.025)
        child_pid = int(marker.read_text())
        assert job.contains_process(child_pid)
        assert job.active_process_count() >= 1
        child_handle = job.open_process_handle(child_pid)
        try:
            job.close()
            assert wait_for_process_exit(child_handle, timeout_seconds=5) != 259
        finally:
            job.close_process_handle(child_handle)
    finally:
        job.close()


def test_native_smoke_owns_a_real_gui_process_until_normal_window_close(tmp_path: Path):
    from scripts.windows_release_probe import run_native_smoke

    title = "GRE release probe window"
    gui_code = (
        "import ctypes; "
        f"ctypes.windll.user32.MessageBoxW(None, 'probe', {title!r}, 0)"
    )

    result = run_native_smoke(
        PYTHONW,
        expected_title=title,
        timeout_seconds=10,
        arguments=("-c", gui_code),
    )

    assert result.root_exit_code == 0
    assert result.active_processes_after_close == 0
    assert result.root_process_id > 0
    assert result.gui_process_id > 0
    assert result.total_processes >= 1
