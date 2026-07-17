# Task 11 report: Job-supervised Windows release verification

## Outcome

The Windows release pipeline still produces one user-facing file,
`outputs/GRE 3000 词离线版.exe`. The Unicode-named outer executable embeds the
ASCII-named Qt runtime `GRE3000OfflineRuntime.exe`; application arguments are
forwarded to the runtime and the runtime inherits the caller's working directory.

Native acceptance no longer relies on a Toolhelp process snapshot. The probe now:

1. creates the final Unicode-named build candidate with `CreateProcessW` and
   `CREATE_SUSPENDED`;
2. assigns the suspended root to a private Windows Job Object configured with
   `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`;
3. resumes the root only after assignment, so all later descendants remain in the
   supervised job;
4. locates the visible exact-title window and proves its owner handle belongs to
   that job;
5. checks x64/Windows-GUI PE metadata and absence of a console for the outer root
   and real titled GUI owner;
6. revalidates the held process handle and HWND ownership before sending one
   `WM_CLOSE`;
7. waits on the already-held GUI owner handle and requires its exit code 0;
8. then requires root exit code 0 and Job Object `ActiveProcesses == 0`.

On any failure, closing the Job Object terminates every still-associated
descendant, including children created after an earlier observation. The success
path does not post to an old HWND again and does not kill by a bare PID.

## TDD evidence

The corrective tests were first observed failing for the intended reasons:

```text
6 failed, 9 passed
console CLI in an uncaptured CREATE_NEW_CONSOLE returned 120
JobSupervisor and atomic publication did not exist
launcher main did not forward arguments or preserve caller cwd
build script had no protected build candidate
```

The focused suite is now green:

```text
15 passed
```

It includes real Windows integration coverage for:

- a console probe invoked without `capture_output` in a real
  `CREATE_NEW_CONSOLE` process;
- Job Object tracking of a delayed child created after the initial root-only
  observation;
- Job close terminating a real lingering descendant after the root has exited;
- a real GUI-subsystem process with an exact-title Win32 window, normal
  `WM_CLOSE`, root exit 0, and final active-process count 0;
- an independent exact-title GUI owner exiting 7 while its waiting root exits 0,
  which must fail specifically on the GUI exit code;
- independent GUI/root exit codes 0, which must both be reported and accepted;
- launcher production `main()` forwarding real arguments and preserving the
  caller's current directory;
- atomic replacement of an existing release by a verified candidate;
- release-script ordering: stage under `build`, verify and smoke the candidate,
  publish atomically, and clean a failed candidate without deleting the old
  output; and
- the release verifier's strict reviewed-row expectation is the current value 5,
  rather than the stale value 4.

The console check now runs `FreeConsole`/`AttachConsole` only inside a disposable
worker whose stdout is a pipe. The long-lived CLI remains attached to its own
interactive console, so Python can flush stdout normally instead of exiting 120.

## Protected publication pipeline

The final launcher is copied first to
`build/release-candidate/GRE 3000 词离线版.exe`. PE verification and the
Job-supervised native smoke run against that exact final basename. Only after
both succeed does `os.replace` atomically publish the candidate to `outputs` on
the same volume. The build script never removes the existing official EXE before
verification, and its outer `finally` removes an unpublished candidate.

This corrective task intentionally did not repeat the expensive full Qt build,
because importer and application fixes are being integrated separately and the
final pipeline will rebuild from those merged sources. The already-built exact
release artifact was copied to a disposable build candidate and passed the new
probe:

```text
pe_metadata ... machine=0x8664 subsystem=2
native_smoke title='GRE 3000 词离线版' root_pid=23892 gui_pid=30932
job_total_processes=4 job_active_processes=0 machine=0x8664 subsystem=2
no_console=true wm_close=true gui_exit=0 root_exit=0
```

This run proves the new supervisor covers the outer launcher plus descendants
created by the onefile/runtime chain; it is regression evidence, not a claim that
the pre-integration artifact is the final deliverable.

Final corrective checks:

```text
full pytest without GRE_SOURCE_PDF: 91 passed, 14 skipped in 7.66s
python -m compileall -q scripts tests: pass
PowerShell parser: pass
git diff --check: pass
```

The 14 skips are the existing source-PDF layout tests gated on
`GRE_SOURCE_PDF`; final integration will run those against the supplied PDF
before rebuilding the deliverable.

## Boundaries

- Vocabulary importer, database, UI, controller, and speech business code were
  not changed by this corrective task.
- The personal EXE remains unsigned, so Windows SmartScreen may warn on first
  run.
- Generated databases, EXEs, profiles, reports, and caches remain ignored.
- research-git capture was skipped because the repository is manual-only and the
  user did not request it.
