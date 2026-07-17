# Task 11 report: hardened packaged Windows offline release

## Outcome

The release remains one user-facing file, `outputs/GRE 3000 词离线版.exe`,
with an exact `GRE 3000 词离线版` main-window title and no console window.
Both the final launcher and the actual GUI child are x64 Windows-GUI PE files.
The smoke test now closes the real Qt window with `WM_CLOSE`, waits for every
process in the launcher/runtime chain, requires exit code 0 from each process,
and fails if any process lingers.

The final file embeds an ASCII-named Qt runtime inside a stdlib-only Nuitka
onefile launcher. This is necessary because both Nuitka and PyInstaller Qt
onefile diagnostics crashed at `QMainWindow.show()` when the outer executable
itself had a Chinese filename, while byte-identical ASCII-named builds ran
normally. The launcher resolves its embedded child relative to `__file__`,
waits for it, returns its exact exit code, and never copies it to a persistent
directory. Onefile temporary files are removed after a normal exit.

## TDD and probe hardening

New focused tests cover real Windows behavior rather than mocks:

- PE COFF Machine and subsystem parsing against `python.exe` and `pythonw.exe`.
- `FreeConsole`/`AttachConsole(actual_pid)` detection against a hidden real
  console process and a real GUI-subsystem process.
- waiting for two real zero-exit processes, rejecting a timeout, and rejecting
  a nonzero exit.
- Toolhelp32 process-tree discovery against a real child process, including the
  command-line output consumed by the PowerShell release script.
- Unicode launcher path resolution, real child waiting/exit-code propagation,
  and missing-runtime failure.

The Toolhelp process-tree test was first observed RED with
`ImportError: cannot import name 'process_tree_ids'`; after implementation the
focused suite passed:

```text
9 passed in 2.36s
```

Toolhelp32 replaced `Get-CimInstance Win32_Process`, which was denied by the
managed Windows environment. It also avoids depending on process names: the
release smoke identifies the exact titled window, verifies that its owner PID
is in the launcher's real descendant tree, and probes that owner directly.

## Packaging architecture and dependencies

- Python 3.12.13
- PySide6 / Qt / shiboken6 6.11.1
- Nuitka 4.1.3
- Microsoft Visual Studio 2022 MSVC

`pyside6-deploy` builds `build/release/GRE3000OfflineRuntime.exe` with QtSql,
the required Qt plugins, the generated SQLite content database, application
icon, GUI subsystem, and onefile mode. A second stdlib-only Nuitka build embeds
that runtime at `runtime/GRE3000OfflineRuntime.exe` and produces the final
Unicode-safe launcher. Both layers are checked for COFF Machine `0x8664` and
PE subsystem `2` before native smoke starts.

The release script preserves its reviewed UTF-8 spec around
`pyside6-deploy`, which otherwise rewrites discovered modules and Python paths.
It carries a UTF-8 BOM for Windows PowerShell 5.1 and keeps Nuitka/temp caches
inside `work/`.

## Verification evidence

The complete release pipeline reached and passed all pre-smoke stages using the
source PDF:

```text
98 passed
physical_row_bands=3292 empty_row_bands=0 multi_anchor_row_bands=0
records=3292 unresolved=0 reviewed=4
release_data_check record_count=3292 unresolved=0 reviewed=4 duplicates=0 integrity=ok
inner PE: machine=0x8664 subsystem=2
final PE: machine=0x8664 subsystem=2
```

That invocation stopped only when its then-CIM process enumeration was denied.
After replacing CIM with the tested Toolhelp probe, the already-produced exact
release artifact passed the complete native smoke without another expensive
rebuild:

```text
pe_metadata .../runtime/GRE3000OfflineRuntime.exe machine=0x8664 subsystem=2
console_probe pid=39684 has_console=false winerror=6
console_probe pid=34740 has_console=false winerror=6
normal_exit wm_close=true processes=34740:0,37408:0,39128:0,39684:0 all_exited=true
NATIVE_SMOKE_OK title='GRE 3000 词离线版' gui_pid=39684 launcher_pid=34740 chain=34740,37408,39128,39684 exit=0
```

Final post-change checks:

```text
focused: 9 passed
full pytest without GRE_SOURCE_PDF: 85 passed, 14 skipped in 6.74s
python -m compileall -q src scripts main.py: pass
PowerShell parser: pass
git diff --check: pass
```

The 14 local skips are PDF-layout tests gated on `GRE_SOURCE_PDF`; the release
pipeline configured the supplied PDF and ran those tests successfully before
the strict import shown above.

Final release artifact:

- Path: `outputs/GRE 3000 词离线版.exe`
- SHA-256: `bf2501103ec9d50a80c9c358df512a2d6fce54840c80f8f65072b08e96bb3b4c`
- Size: `34,003,968` bytes
- Final launcher: x64 (`0x8664`), Windows GUI subsystem (`2`), no console
- Actual Qt GUI child: x64 (`0x8664`), Windows GUI subsystem (`2`), no console
- Close result: exact titled window received `WM_CLOSE`; all four observed
  chain processes exited 0 within the timeout

## Boundaries

- The personal EXE is unsigned, so Windows SmartScreen may warn on first run.
- The packaged-path regression remained green because the desired
  `PACKAGE_ROOT / "data" / "words.db"` behavior already existed; no artificial
  production change was introduced.
- Task 10 vocabulary content, parser rules, overrides, and MainWindow geometry
  were not changed.
- Generated database/build files, EXEs, profiles, reports, and caches remain
  ignored.
- research-git capture was skipped because this repository is manual-only and
  the user did not request capture.
