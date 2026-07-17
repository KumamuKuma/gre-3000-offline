# App reliability final-fix report

## Outcome

- Hardened content/user database validation, migration, recovery, and retryable persistence.
- Made study navigation queue + seen progress atomic and idempotent.
- Added startup error UX, safe window geometry persistence, global Ctrl+F, recall reveal/input fixes, Unicode search, and explicit TTS fallback/unavailable states.
- Kept importer, release/build scripts, deployment spec, and output artifacts untouched.

## TDD evidence

Focused RED runs first demonstrated the requested failures: locked healthy DB recovery attempted replacement; malformed schemas/queues were accepted; queue and seen updates split; invalid content contracts opened; startup errors escaped; composed/accented search failed; keyboard/recall/geometry behavior was absent; and TTS did not expose three availability states.

Focused GREEN results:

- user repository + study persistence: `21 passed`
- content/bootstrap/entry: `19 passed`
- Unicode synthetic + generated 3292-word database: `2 passed`
- UI interaction + geometry: `13 passed`
- controller: `7 passed`
- TTS: `21 passed`
- final boundary regressions: `3 passed`

## Final gates

Environment used the sibling worktree virtualenv, this worktree's `src` on `PYTHONPATH`, isolated `TEMP`/`TMP`, and pytest `-p no:cacheprovider`.

- Full suite with `GRE_SOURCE_PDF=D:\桌面\LGU\GRE\张巍GRE镇考3000词-乱序（2026年）.pdf`: `124 passed, 1 skipped in 9.88s`.
- The sole skip was the optional `GRE_GENERATED_DB` integration because no retained generated DB file was available during the final run; the equivalent real 3292-word Unicode integration had passed earlier.
- Native Windows Qt smoke: startup, show, close, geometry write, repository reopen, and geometry equality all passed.
- `python -m compileall -q src tests`: passed.
- `git diff --check`: passed (only Git's informational LF-to-CRLF warnings).

## User DB migration and recovery

- Schema version is now 2, with an explicit v1-to-v2 migration adding `seen_events` without losing existing settings/progress.
- Physical corruption is backed up and recreated only after corruption-specific SQLite signals or failed integrity checks.
- Busy/locked and structurally incompatible but physically healthy databases surface actionable errors and are not renamed.
- User-facing mutations update in-memory state immediately, retain failed writes in order, expose a Chinese persistence warning, and retry on the next mutation.

## Residual concerns

- Final full-suite execution could not re-run the optional retained-generated-DB test because that external artifact was absent; PDF-backed integration and prior 3292-word DB coverage both passed.
- TTS voice inventory remains platform dependent; the UI now distinguishes English voice, default-voice fallback, and unavailable backend states.

## Independent-review follow-up

- Close now uses an event handshake: geometry and every pending mutation must flush before acceptance; a modal Retry/Cancel/explicit-discard choice keeps the window alive while writes remain. Repository `close()` also refuses to drop pending writes, and `aboutToQuit` uses an exception-containing controller shutdown.
- Successful flushes clear stale persistence issues.
- Content startup maps every row before creating the search index; NULL, wrong-type, and empty-headword failures in non-first rows close the connection and fail entry startup before user-data creation.
- Geometry restoration requires at least a 120-by-24-pixel operable title-bar region, rejects removed-screen/one-pixel remnants, and clamps oversized or partial rectangles to the selected screen.
- Follow-up focused suite: `17 passed in 1.93s`.
- Follow-up full suite with the real source PDF: `137 passed, 1 skipped in 9.23s`; the sole skip remains the optional absent `GRE_GENERATED_DB` artifact.
