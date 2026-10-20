# Editor integration and qualification — 20 October 2026

Version: **1.2.0rc1**, experimental. This combines public source only. Native TunerPro, real-definition corpus replay, hardware and flashing remain unqualified. A skipped fixture is missing evidence.

## Provenance and preservation

Integration starts at public main `c1de66ecc31b814925bf3a3f1346b07eecf997b3`. All original remote branches and main were retained. An original-ref manifest and a complete verified Git bundle were created outside the repository before editing. Bundle SHA-256: `4b15d7e9808ea42376c02a7e34c4ea02195c5f88ddb27814bc4c57887f4ee47b`.

| Original branch | Exact original tip | Unique work and integration decision | Regression evidence |
| --- | --- | --- | --- |
| main | `c1de66ecc31b814925bf3a3f1346b07eecf997b3` | Keep current README, full bounded diff/report tests, raw-patch contracts and public ignore rules | Existing full suite retained |
| chatgpt/exact-pair-fixture-validation-20261006 | `206ba4ffd9f9b1187262fa1d89688dc1b489539a` | Merge fixture identity gate and guarded export, API plan and synthetic tests; retain newer README, add current fixture documentation | Exact-pair tests; malformed JSON-root and boolean-size cases added |
| chatgpt/reciprocal-inverse-cli-v120-20261014 | `a60eaa56147f885e16f5dc7d21ac6b666b1db630` | Merge proven narrow K/X engineering-write path and tests; replace old dependency proposal with exact qualified exporter pin | Scalar/table exact-byte reciprocal tests and unsupported-form refusal |
| codex/editor-save-integrity-20261015-5ea52889 | `b9825175c2dcc73ebfd24e09e427dfb21fd68f05` | Merge staged/fsynced audited save and invalid-mask gates; retain historical verification receipt as historical evidence only | Interrupted write/flush/fsync/close/publication/collision regressions |
| codex/local-diff-sync-20261007 | `d46c16201566e0ee9e3848b0da2620cc47fcfe1d` | Already merged in main; all report/mask tests retained | Full suite |
| docs/readme-accuracy-refresh-20261016 | `35530ad9e2cd9803334320a346d8d8359a0c1c76` | Same tree as main (prior squash); merge history retained and version-specific text updated | Manual command/doc comparison |
| review/mit-exporter-agent-quickstart-20261017 | `585d839bb21ccd3af0beeee95375149f12a24500` | Merge AGENTS onboarding; retain newer public README and update pin only after compatibility checks | Installed-package check required for final dependency |

Every original branch tip is an ancestor of this integration. No branch was deleted, rebased or force-pushed. Merge conflicts retained main-only changes and reconciled version/pin metadata. The old `verification-save-integrity-20261015.json` records an older Windows run and dependency; it is not the result for this release.

## Per-script and module audit ledger

The runtime audit inspected actual source, command paths, errors and writes. The executed suite is limited evidence for the represented synthetic cases, not qualification of every code path or an ECU family.

| File | Inspected or changed | Executed evidence and remaining limit |
| --- | --- | --- |
| `cli_map_editor.py` | Inspected parsing/session/load, inverse selection, integer staging, bounds, diff, fixture and output paths. Merged exact-pair, narrow K/X and coordinated save changes. Fixed malformed fixture roots, boolean sizes and duplicate import. CLI paths come from arguments; no personal hardcoded runtime path, network call or subprocess found. | Synthetic source suite, real CLI processes from unrelated directories with spaces, scalar/table/flag exact byte writes, source preservation, missing inputs, identity and refusal cases. No native/real ECU proof; hard crash cannot be a multi-file transaction. |
| `tunerpro_exporter_for_cli_editor_version.py` | Inspected installed dependency wrapper and actionable missing-import error. No sibling checkout import. | Shared exporter contract suite and missing-dependency isolated Python process. Exact final dependency receipt below. |
| `raw_patch_manifest.py` | Inspected strict JSON schema/key checks, hash/image gates, immutable ranges, bounded staging, verifier registry, exclusive publication and handled-failure rollback. No manifest code execution. | Portable raw-patch tests; optional real inputs unavailable. Receipt paths intentionally identify local inputs; redact/review before sharing. |
| `raw_patch_checksum_profiles.py` | Inspected exact profile contracts, lengths/identities, record parsing, deterministic read-only verification. No checksum repair or path dependency. | Synthetic MS42/MS43/VY profile tests. Private exact-image replay unavailable; no generic platform claim. |
| `porting_templates.py` | Inspected entire comments-only historical file; added prominent archival designation because `port` is disabled and old SAFE/verified wording is not current evidence. | No executable transformation exists; excluded from enabled feature claims. Original notes preserved. |
| `.github/workflows/editor-tests.yml` | Inspected package installation and away-from-source test steps; replaced hardcoded 1.1.0 wheel lookup with checked single-wheel selection. | Local equivalent run required below. Hosted Windows/Linux Python 3.10/3.13 results are separate evidence. |

Test modules are reviewed as synthetic regression evidence, not public data qualification. Their per-module ledger is completed alongside final execution below.

## Ignore, privacy and promotion review

- Reviewed repository `.gitignore`, tracked-file list and local `.git/info/exclude`. The latter contains only stock Git comments. This fresh public clone contained no ignored reusable source candidate to clean or promote.
- Deduplicated repeated research-runner exclusions. Kept the named search/debug runners and hardcoded local test runner excluded because their actual source is unavailable for review; do not infer they are portable.
- Added case-insensitive BIN/XDF exclusions and `.kingai-save-*.incomplete/` protection. Kept secrets, environment files, local configs, archives, build/test outputs and private notes excluded.
- No tracked BIN/XDF, executable/archive, database or obvious credential was found in this public source audit. No private repository or local dirty clone was used.
- Snapshot diagnostic JSON and raw-patch receipts intentionally contain local input paths. Only reviewed/redacted generated reports belong in public release assets. No private fixture, firmware or customer output is bundled.

## Reproducible checks

Use a fresh Python 3.10+ environment, build/install the exact pinned exporter, and install test/build tools. Do not use an older editable exporter from another checkout.

```console
python -m pytest -q -ra --basetemp="../editor source temp/final"
python -m build
python -m pip install --no-deps dist/kingai_tunerpro_map_editor-1.2.0rc1-py3-none-any.whl
```

For installed validation, copy only `test_*.py` into a new directory outside both checkouts, clear `PYTHONPATH`, then run:

```console
python -I -m pytest --import-mode=importlib -q -ra --basetemp="../installed test temp/final"
kingai-map-editor --help
python -m pip check
```

Record actual Python/platform, dependency SHA, wheel hashes, import locations, exact counts and skip reasons. The portability regressions execute real CLI processes in unrelated directories with spaces and check missing inputs/dependency messages, unchanged originals, exact edited bytes and audit outputs.

## Executed results and remaining qualification

Preliminary source execution on Windows, Python 3.13: **223 passed, 17 skipped** against this task's explicit exporter source path. Focused fixture and new CLI portability execution: **15 passed**. These were actual local executions, not GitHub runner results. Final exact-pin source/wheel/portable results are recorded after the exporter is frozen.

The 17 preliminary skips are unavailable privately held exact-image MS42/MS43/VY and raw-patch integration fixtures. They are not passing corpus results. The known MS42 linked-axis, MS43 duplicate-ID, MS45 virtual/Z-less and VY malformed-equation cases also require permissioned exact-input replay and native comparison before stable compatibility claims. No native GUI, controller, vehicle, live trading or hardware operation was performed.
