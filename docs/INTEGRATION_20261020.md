# Editor integration and qualification — 20 October 2026

Version: **1.2.0rc1**, experimental, pinned to Exporter **3.7.5rc1** commit `e7c0ae86534791620ea0b843810f4980d24081d5`. This combines public source only. Native TunerPro, real-definition corpus replay, hardware and flashing remain unqualified. A skipped fixture is missing evidence.

## Provenance and preservation

Integration starts at public main `c1de66ecc31b814925bf3a3f1346b07eecf997b3`. All original remote branches and main were retained. An original-ref manifest and a complete verified Git bundle were created outside the repository before editing. Bundle SHA-256: `4b15d7e9808ea42376c02a7e34c4ea02195c5f88ddb27814bc4c57887f4ee47b`. The preserved per-ref source manifest records every file/mode/blob, SHA-256 `e7bc3a3020ea55938d603846bb0c0a772d5253f78cabb37ebecdfefd6d9dc311`.

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
| `build_portable_bundle.py` | New audited stdlib builder. Reads only two explicit pure-Python wheels, checks names/versions, declared MIT metadata and exact exporter dependency commit, emits deterministic ZIP members and SHA-256 manifest with exclusive creation. | Synthetic bundle/reproducibility/existing-output/mismatched-pin/licence tests; final real-wheel artifact evidence accompanies release. No Python interpreter or standalone executable is bundled. Caller-supplied commit provenance still requires source/wheel comparison. |
| `portable_install.py` | New audited offline installer. Validates bounded relative wheel filenames, installer/wheel SHA-256, Python requirement and commit format before reserving a new venv. Refuses existing paths; installs only selected local wheels using `--no-index --no-deps`, then `pip check`. `PIP_CONFIG_FILE=os.devnull` disables global/site configuration that could redirect installation; Python `-I` and pip `--isolated` remain enabled. Retains incomplete installations and reports missing venv/ensurepip support. | Missing/corrupted wheels, corrupted installer, existing environment, config isolation and path-with-spaces subprocess cases. Checksums detect corruption, not publisher identity. |
| `.github/workflows/editor-tests.yml` | Inspected package installation and away-from-source test steps; replaced hardcoded 1.1.0 wheel lookup with checked single-wheel selection. | Local equivalent run required below. Hosted Windows/Linux Python 3.10/3.13 results are separate evidence. |

All test modules were individually inspected. They are synthetic regression evidence, not public data qualification.

| Test module | Inspected code and executed scope | Remaining limit |
| --- | --- | --- |
| `test_category_membership.py` | In-memory direct/one-based category XML and wrapper import | Native category sampling absent; category-zero crowding belongs to exporter suite |
| `test_editor_exporter_contract.py` | Generated signed/affine/reciprocal fixtures with independent offsets/bytes, quantization and fail-closed writes | No real definition or column-major write qualification |
| `test_editor_portability.py` | Real CLI subprocesses from unrelated directory with spaces, exact scalar/table/flag bytes, logs/diff, exact-pair validation/export/refusal, unchanged inputs, missing-input/dependency errors | Requires installed-suite isolation; no native standalone executable |
| `test_editor_release_safety.py` | Synthetic ambiguity, disabled commands, required autosave/output, scopes, collisions, aliases, snapshots and invalid conversions | Handled failures and synthetic paths; no hostile races or crash proof |
| `test_exact_pair_fixture_cli.py` | Generated identity manifests, target and JSON type errors, hash mismatch before preflight and guarded delegation | Several delegates mocked; real CLI snapshot path separately exercised |
| `test_flag_writes.py` | Generated 8-bit masks, sibling-bit preservation, invalid masks/states and log identity | Narrow mask contract |
| `test_interrupted_save.py` | Injected open/write/short-write/flush/close/fsync/publication failures, ownership/collision rollback, BIN-last ordering, retained evidence and CLI failure | No abrupt process/power-loss transaction proof or every filesystem |
| `test_overlapping_axis_stride.py` | Synthetic independently expected overlapping 16-bit axis values and misaligned stride refusal | Reads only; unsupported writes remain refused |
| `test_raw_patch_manifest.py` | Strict synthetic roundtrip, hashes/identity/allowlist/immutability, malformed keys, exclusive outputs, evidence and trusted callbacks; bounded CLI timeout added | Instruction semantics and ECU compatibility absent |
| `test_raw_patch_cli.py` | Synthetic forward/reverse verify/apply receipts and bounded subprocess; optional exact-hash DS2 replay | Optional real input depends on absent sibling workspace and skips |
| `test_raw_patch_checksum_profiles.py` | Independent bitwise CRC arithmetic, synthetic corruption/descriptor/OSID/contract gates; optional pinned parent/DS2 replay | Some synthetic range metadata derives from production contract; real replay absent |
| `test_ms43_raw_patch_checksum_profile.py` | Independent synthetic CRC/additive arithmetic, three/five-layer corruption/seed/metadata/OSID/order gates; optional pinned images | Native profile/range proof absent; already-public short patch assertions are not firmware fixtures |
| `test_vy_raw_patch_checksum_profile.py` | Synthetic additive checksum/excluded ranges, corruption/size/OSID/contract gates; optional pinned parent/control | Independent real/native compatibility proof absent |
| `test_xdf_aware_diff.py` | Generated overlap/unmapped/masked-bit attribution, report hashes, unequal tails, aliases and existing targets | No broad real-definition attribution corpus |
| `test_portable_bundle.py` | Generates tiny standards-compliant wheels; exercises reproducible/exclusive bundles, exact dependency pin/licence, missing/corrupted wheels and installer before venv creation, global-config isolation, existing-venv preservation, actionable missing-venv error with retained evidence and actual isolated offline installation under paths with spaces | Synthetic fixture wheels test distribution mechanics; successful-venv case explicitly skips when Python has no ensurepip, recording that installation is not qualified there. Final real-wheel artifact evidence accompanies release |

`MANIFEST.in` was inspected and extended: source distributions retain `test_*.py`, public Markdown/agent/audit documentation and reference mapping CSVs. `pyproject.toml` packages the original five modules plus the two offline-distribution helpers, with exact exporter dependency. Disabled porting does not consume mappings from the wheel. No hidden parser, native binary or data dependency was introduced.

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

Final source execution on Windows, Python 3.13 against the exact frozen exporter commit completed **235 passed, 17 skipped** in 53.29 seconds. This includes all nine offline-bundle cases, real CLI calls from a directory with spaces, guarded fixture snapshot/mismatch refusal, and preserved input hashes. The dependency source tree had no diff from the pinned commit. Canonical source, installed-wheel and real portable-asset results/hashes are supplied in the release qualification receipt after artifact execution. These are local execution results, not hosted Windows/Linux/Python-matrix results.

The 17 preliminary skips are unavailable privately held exact-image MS42/MS43/VY and raw-patch integration fixtures. They are not passing corpus results. The known MS42 linked-axis, MS43 duplicate-ID, MS45 virtual/Z-less and VY malformed-equation cases also require permissioned exact-input replay and native comparison before stable compatibility claims. No native GUI, controller, vehicle, live trading or hardware operation was performed.
