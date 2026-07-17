# Final fix wave A: trustworthy PDF content and strict audit

DONE

## Approved source

- PDF: `D:/桌面/LGU/GRE/张巍GRE镇考3000词-乱序（2026年）.pdf`
- SHA-256: `8270d259f3457711a16c9f7a7d79f2d95f89fa83228a1b89e656546882f303a0`
- Physical pages: `288`
- Approved physical word-row bands / records: `3292 / 3292`

## RED evidence captured before implementation

Focused tests were introduced before production edits and observed failing:

- Layout boundary fidelity: `test_extract_page_spans_preserves_boundary_whitespace` returned `"word"` instead of the PDF span text `" word "`.
- Visual-line grouping: `test_visual_lines_cluster_by_center_and_keep_same_line_span_boundaries` inserted a newline between same-line spans instead of preserving `"adj. sure 必然的"`.
- The first semantic-normalization tests failed because `normalize_row_with_diagnostics` and its de-wrap diagnostics did not exist; the real-PDF assertions then reproduced the `allegory`, soft-wrap, Chinese-wrap, and invalid-phonetic defects.
- Strict CLI mutation test: an unapproved one-row PDF completed with exit `2` after replacing the pre-existing trusted DB and audits.
- Strict empty-source test: a four-page empty PDF completed with exit `0` and `records=0`.
- Override tests reproduced acceptance of forbidden provenance/`quality_flags`, zero-match keys, duplicate JSON keys, no-issue reviews, and invalid post-override content.
- Audit test reproduced the absence of source-profile, full physical-coverage, section, continuity, de-wrap, override, semantic-scan, and strict-check evidence.
- Two follow-up RED tests caught overly broad semantic scanning: one unrelated `"that he"` substring falsely satisfied a `t`/`he` boundary, and a normal-space event inside the Chinese example block was initially ignored.

The failing assertions were retained as regressions; no production code was changed until the corresponding focused test had failed.

## Implementation

- Preserved raw PDF span boundary whitespace and grouped visual lines by center-Y tolerance plus X order.
- Replaced first-CJK splitting with per-line language segmentation. All English definition senses are aggregated into `definition_en`; Chinese senses are aggregated into `definition_zh`.
- De-wrapped fields from source span evidence: boundary whitespace yields one ASCII space; a Latin-to-Latin boundary with no source whitespace is a hard join. Chinese wrapped lines do not gain ASCII spaces, while Latin names within a Chinese example retain source spaces.
- Added reusable validation for missing/malformed phonetics and bilingual incompleteness. Source order 529 keeps the literal `ameliorate` phonetic and receives `reviewed:invalid_phonetic`; no pronunciation was invented.
- Added exact approved-source strict gates for hash, pages, row bands, empty/multi-anchor coverage, record count, source-order continuity, page range, section counts, override use, unresolved records, de-wrap profile, and semantic scans.
- Moved strict validation ahead of all DB/audit output writes.
- Hardened overrides: duplicate JSON keys fail; each key must match exactly one original row; only content fields are writable; provenance/raw fields and `quality_flags` are forbidden; review-only entries require a detected original issue; stale/no-op and invalid post-override changes fail; validation is recomputed; audit detail includes original issues and before/after content.
- Expanded JSON/HTML audit output with approved/actual source profile, physical coverage, sections, continuity, page range, de-wrap counts, override details, semantic checks, and strict checks, while preserving original flat fields for existing consumers.

## Visual PDF evidence

Rendered with the bundled Poppler runtime and inspected at high resolution:

- Page 5: `allegory` visibly contains a second English numbered sense in the definition cell; it belongs in `definition_en`. The Chinese content is `象征寓言`.
- Page 9: order 59 visibly wraps `depr` / `essing` with no boundary whitespace, proving the hard join `depressing`. The wrapped Chinese translation has no inserted ASCII space.
- Page 50: order 529's phonetic cell literally says `ameliorate`; this is preserved and reviewed as invalid. Order 532 visibly hard-wraps `equiv` / `alent` and `governm` / `ent`.
- Page 277: `puff up` and `sound bite` have Chinese-only definition cells in the source, supporting review-only `incomplete_definition` flags.
- Page 279: `hold sway` has a Chinese-only definition cell, supporting a review-only `incomplete_definition` flag.
- Page 283: `least bit` has a Chinese-only definition cell, supporting a review-only `incomplete_definition` flag.

## Verification

All commands used the project virtualenv interpreter, `PYTHONPATH=<worktree>/src`, isolated `TEMP`/`TMP`, and `GRE_SOURCE_PDF` for real-PDF tests.

Focused importer suite:

```text
python -m pytest tests/importer -q -p no:cacheprovider
........................................................................ [ 88%]
.........                                                                [100%]
81 passed in 8.69s
```

Full suite:

```text
QT_QPA_PLATFORM=offscreen python -m pytest -q -p no:cacheprovider
........................................................................ [ 54%]
...........................................................              [100%]
131 passed in 11.53s
```

Fresh strict real import:

```text
python -m gre_vocab_app.importer.build \
  --pdf "$GRE_SOURCE_PDF" \
  --output work/strict-build/words.db \
  --audit-json work/strict-build/audit.json \
  --audit-html work/strict-build/audit.html \
  --overrides src/gre_vocab_app/importer/overrides.json \
  --strict
physical_row_bands=3292 empty_row_bands=0 multi_anchor_row_bands=0
records=3292 unresolved=0 reviewed=5
```

Independent SQLite/audit assertions:

```text
integrity=ok records=3292 orders=1..3292 pages=5..288
duplicate_headword_groups=0 unresolved=0
failed_strict=[]
```

Section counts are exact: `list1` through `list29` each contain `105`, `list30` contains `44`, `supplement-1` contains `102`, and `supplement-2` contains `101`.

Reviewed records are exactly:

- `529 ameliorate`: `reviewed:invalid_phonetic`
- `3159 puff up`: `reviewed:incomplete_definition`
- `3164 sound bite`: `reviewed:incomplete_definition`
- `3182 hold sway`: `reviewed:incomplete_definition`
- `3231 least bit`: `reviewed:incomplete_definition`

Audited de-wrap profile:

| Field | Normal-space joins | Hard joins | Records with hard joins |
|---|---:|---:|---:|
| definition | 3993 | 0 | 0 |
| example | 3416 | 241 | 212 |
| synonyms | 2 | 255 | 237 |

Semantic scans all pass with count zero:

- `english_fields_contain_cjk`
- `definition_zh_contains_english_sense`
- `hard_wrap_residue`
- `normal_wrap_overjoin`

Final static gates:

```text
python -m compileall -q src tests
# exit 0

git diff --check
# exit 0
```

## Follow-up review fixes

The follow-up Important 2-6 review was handled in a second strict TDD wave.
Release expected-reviewed wiring remained outside this importer-only change.

RED evidence:

- Second/third artifact publication failure tests returned success because only
  the database used `os.replace`; JSON and HTML were written directly.
- Candidate audit-write and HTML-directory-conflict tests showed the new DB had
  already replaced the trusted DB when the later audit operation failed.
- Overrides for `missing_phonetic` could change `headword`, and an unknown
  `split_token` issue could change `definition_en`; neither raised an error.
- Chinese-block Latin-to-digit/punctuation tests either lost source boundary
  spaces or emitted no de-wrap diagnostic in all four cases.
- Nine semantic cases were missed: `vt.`, `vi.`, `pron.`, `conj.`, `det.`,
  `aux.`, `interj.`, a multiword unlabelled sense, and a single-word unlabelled
  sense.
- Centers at 10/14/16 chained into one visual line even though the total range
  exceeded the four-point tolerance.
- Long orthographic placeholders `[ameliorate]` and `/ameliorate/` were accepted
  as phonetics.

Implemented behavior:

- DB, JSON, and HTML are generated and validated at sibling candidate paths.
  Existing targets are copied to sibling backups before fixed-order publication.
  Any candidate write, path conflict, or second/third replacement failure restores
  the complete prior artifact set and removes candidates/backups.
- Override content changes are limited to the union of `_issue_fields` for all
  original issues. Unknown issues are review-only.
- Chinese example blocks preserve or join Latin-to-digit/punctuation boundaries
  from source whitespace and emit normal/hard diagnostics.
- Semantic scanning covers the expanded POS set and conservative all-lowercase
  unlabelled English senses, while excluding Toyota, New York, DNA, and eBay.
- Visual-line clustering uses the first span center as its fixed anchor.
- Long, wrapped, purely orthographic headword placeholders are conservatively
  invalid; short transparent `[meld]` remains valid and unresolved-free.

Fresh follow-up verification:

```text
python -m pytest tests/importer -q -p no:cacheprovider
110 passed in 6.81s

QT_QPA_PLATFORM=offscreen python -m pytest -q -p no:cacheprovider
160 passed in 8.44s

python -m gre_vocab_app.importer.build ... --strict
physical_row_bands=3292 empty_row_bands=0 multi_anchor_row_bands=0
records=3292 unresolved=0 reviewed=5
publication_leftovers=0
```

Independent checks remained exact: SQLite integrity `ok`, source orders
`1..3292`, pages `5..288`, approved section counts unchanged, the approved
de-wrap profile unchanged, all four semantic counts zero, no strict failures,
and `[meld]` retained with `quality_flags=[]`. `compileall` and
`git diff --check` exited zero; `tmp`, test temp, candidates, and backups were
removed.

## Remaining concerns

No unresolved importer ambiguity remains. The five reviewed records deliberately preserve visible source defects or source incompleteness. Source wording and typos are otherwise preserved rather than silently rewritten.
