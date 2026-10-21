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
