# Transactional batch XDF editing — local verification receipt

Date: 2026-10-22. Branch: chatgpt/transactional-xdf-batch-20261022.

## Exact provenance

- Started from main commit: 0dda2b9894219a778a296e74ca5c963c35e048e8
- The feature is unreleased. The package remains identified as 1.2.0rc2 in source; no new release or compatibility claim is being made.
- Newly executed batch coordinator blob (Git object): 28fc92bd2a416775d531e0a1e4c559fcf12d47ce
- Locally executed dependency-free test blob: a33ba2969559ad7bc4f9927f433c95fdcb4a9f79
- The two blob hashes were checked locally with git hash-object and matched the GitHub connector's returned Git blob IDs.

## Executed here, not GitHub Actions

Environment: Python 3.13.5, pytest 9.0.2. A local work directory held the coordinator and dependency-free fake-session tests.

~~~console
python -m pytest -q test_transactional_batch_unit.py
..........                                                               [100%]
10 passed in 0.06s

python -m py_compile transactional_batch.py test_transactional_batch_unit.py test_batch_transactions.py
# completed successfully
~~~

The ten local tests cover: multi-item successful publication through an isolated fake save; read-only preview; per-cell ranges; conflict rejection; disjoint shared-byte flag masks; conversion dependencies across a scalar/table; late-operation rollback; identity-hash refusal; malformed CSV; missing save permission; changed-but-undeclared flag bits; and complete JSON byte receipts. These tests validate the coordinator against synthetic fake sessions, not native TunerPro or a real ECU image.

## Committed, but not executed locally

- test_batch_transactions.py exercises the real CLI, typed session and pinned Exporter with synthetic XML/BIN pairs, including exact expected bytes, dry-run preservation, duplicate cells, a late invalid target, wrong hashes, disjoint flags and JSON output. It is committed for subsequent installed-package execution.
- The full repository suite, pinned Exporter dependency installation, isolated installed wheel smoke, native TunerPro parity and real XDF/BIN replay were **not executed** in this environment.
- The container had no usable DNS access to github.com, and the pinned tunerpro_xdf package was not installed locally. GitHub Actions were not relied upon. The GitHub connector was used to fetch source and commit changes.
- No private or customer BIN/XDF data was committed.

## Limits and next release gate

- CSV batch writes are limited to the typed table, scalar and flag write paths already implemented by the Editor; raw integer mode cannot bypass unsupported storage/geometry/maths.
- Ambiguous duplicate titles, overlapping byte or bit targets and final-image dependency changes cause the entire staged batch to fail.
- A successful XDF parse, input hash match, decoded value or BIN write does **not** prove that the calibration is active for that OSID or safe to flash. ECU checksums, signatures and hardware validation remain separate.
- Before releasing a new Editor prerelease: execute the whole test suite with the exact pinned Exporter; smoke-test an installed wheel and standalone CLI; replay permissioned real XDF/BIN pairs against native TunerPro; inspect hashes, output audit and changed-byte coverage; verify checksum handling for any intended real use.

This receipt intentionally distinguishes executed coordinator tests from unexecuted integration tests. It is not a completion certificate for ECU compatibility.


## Follow-up: multi-target qualification improvements on 22 October 2026

This is a **supplement** to the initial 10-test receipt, not a replacement for its historical provenance.

### Commits and functional changes

- Added per-operation expected_old_raw preconditions (CSV key: expected_raw), plan SHA-256 receipts and load/staging-time plan mutation detection.
- Corrected multi-bit flag clearing validation: all selected mask bits must be cleared; a false boolean result alone is insufficient.
- Added optional XDF uniqueid and XDF storage-address selection for duplicate table/scalar titles. The pinned Exporter does not expose flag uniqueids; flag address selection is supported.
- Added hash-pinned kingai.xdf-batch-plan.v1 JSON operations, requiring both exact source hashes, sharing the CSV validator and rejecting duplicate JSON keys, nonfinite numbers, extra keys, invalid types and mismatched source identities.
- Exposed CLI --plan-json, additional list-maps IDs and machine-readable batch errors. The old --csv workflow remains available.
- Added synthetic real-Exporter end-to-end CLI tests as a **committed but not locally executed** candidate.

### Locally executed and repeatable

The following tests executed in the local Python container, not in GitHub Actions:

~~~console
python -m pytest -q test_transactional_batch_unit.py test_batch_hardening.py test_batch_selector.py test_batch_json_plan.py
.................................................                        [100%]
49 passed in 0.12s

python -m py_compile transactional_batch.py test_transactional_batch_unit.py test_batch_hardening.py test_batch_selector.py test_batch_json_plan.py
# completed with no compilation errors
~~~

Runtime: Python 3.13.5; pytest 9.0.2. Tests use synthetic bytes and in-memory fake sessions with mocked publication, not firmware or a native ECU parser. Test cases include mixed table/scalar/flag edits, disjoint and overlapping bit masks, expected old raw values, invalid or ambiguous title resolution, exact uniqueid/address matching, JSON source hashes, bad schemas, duplicate keys and plan mutation races.

Committed coordinator Git blob SHA: 7bed00ff639d3d8c4a41686f66861778f1fe7867. This was checked against the locally executed module via git hash-object.

The container could not resolve github.com and does not have the pinned tunerpro_xdf Exporter dependency installed; test_batch_transactions.py and test_batch_plan_cli.py, whole-package tests, installed-wheel smoke, native TunerPro parity, and real exact-image replay remain **not executed here**. The tests committed to the PR do not constitute successful end-to-end validation by themselves. No private BIN/XDF or customer logs were used.

### Release decision

This branch remains an **unreleased draft**. The available evidence proves the standalone batch coordinator against its synthetic test doubles, not native TunerPro compatibility. Before merging/releasing, run the repository suite and isolated installed-wheel smoke on an environment with the exact pinned Exporter, then replay authorized real definition/image pairs. The scripts here did not flash, checksum-repair, or validate an ECU.


## Final local follow-up: same-address flags

A subsequent isolated regression batch added exact 8-bit flag_mask selectors for two parsed flags with identical title and XDF storage address but different masks. Selection is constrained by title, optional address and optional flag_mask; ambiguous matches remain errors. The CSV and JSON plan grammars accept flag_mask only for flag records and reject zero, negative, noninteger and over-width masks. The test cases also confirm two disjoint flags can be changed in a single staged operation.

~~~console
python -m pytest -q test_transactional_batch_unit.py test_batch_hardening.py test_batch_selector.py test_batch_json_plan.py test_batch_flag_mask.py
.........................................................                [100%]
57 passed in 0.14s
~~~

Python 3.13.5, pytest 9.0.2. This is a dependency-free synthetic coordinator result, not a complete installed-package result. The locally tested and committed transactional_batch.py module Git blob SHA is 8f419d1d0a3054a08e0250fecf644e50c4ecaa17. The committed test_batch_flag_mask.py Git blob SHA matches the executed local test file: 374bf48ccfd5b3118a389762a3a2f6bf198e8057.

The integration, checksum, native-display and hardware qualification gaps described above remain unchanged.
