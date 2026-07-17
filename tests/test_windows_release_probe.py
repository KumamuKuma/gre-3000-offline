from __future__ import annotations

import os
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


def test_process_tree_ids_finds_a_real_child_and_cli_reports_same_tree():
    from scripts.windows_release_probe import process_tree_ids

    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        process_ids = process_tree_ids(os.getpid())
        assert os.getpid() in process_ids
        assert child.pid in process_ids

        cli_probe = subprocess.run(
            [
                sys.executable,
                str(PROBE),
                "process-tree",
                "--pid",
                str(os.getpid()),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert cli_probe.returncode == 0
        assert cli_probe.stdout.startswith(f"process_tree root={os.getpid()} pids=")
        cli_process_ids = {
            int(value)
            for value in cli_probe.stdout.rstrip().rsplit("pids=", 1)[1].split(",")
        }
        assert {os.getpid(), child.pid} <= cli_process_ids
    finally:
        _terminate(child)


def test_wait_for_clean_process_exit_accepts_two_real_zero_exit_processes():
    from scripts.windows_release_probe import wait_for_clean_process_exit

    processes = [
        subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(0.5)"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(2)
    ]
    try:
        exit_codes = wait_for_clean_process_exit(
            [process.pid for process in processes], timeout_seconds=5
        )
        assert exit_codes == {process.pid: 0 for process in processes}
    finally:
        for process in processes:
            _terminate(process)


def test_wait_for_clean_process_exit_rejects_a_lingering_real_process():
    from scripts.windows_release_probe import wait_for_clean_process_exit

    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        with pytest.raises(TimeoutError, match=rf"\b{process.pid}\b"):
            wait_for_clean_process_exit([process.pid], timeout_seconds=0.05)
    finally:
        _terminate(process)


def test_wait_for_clean_process_exit_rejects_nonzero_exit():
    from scripts.windows_release_probe import ProcessExitError, wait_for_clean_process_exit

    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys, time; time.sleep(0.25); sys.exit(7)",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        with pytest.raises(ProcessExitError, match=rf"{process.pid}.*code 7"):
            wait_for_clean_process_exit([process.pid], timeout_seconds=5)
    finally:
        _terminate(process)
