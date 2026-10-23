# Batch hardening and offline qualification — 22 October 2026

Branch: chatgpt/transactional-xdf-batch-20261022. Candidate on PR #10, not a release, flasher or ECU compatibility certification.

Later isolated review: [24 October real pinned-Exporter and installed-package
qualification](REAL_PINNED_EXPORTER_QUALIFICATION_20261024.md). Its optional
source-backed wheel proof and executed results supersede only the corresponding
unrun gates below; all 22 October results remain historical evidence.

## Functional changes

1. **Plan SHA-256 now identifies exactly the bytes parsed.** CSV and JSON plans are read once (32 MiB cap), hashed and parsed from the same snapshot. Previously, a replacement between the parse and hash reads could bind different plan contents to the published receipt. BIN, XDF and plan files are rehashed after staging; preview and publication both reject source mutations, and staging failures roll back in-memory bytes and logs.
2. **Table readback uses the pinned Exporter's canonical cell conversion.** The staged BIN is temporarily bound to the Exporter while its _cell_equation_selector, table_context and evaluate_math resolve the actual equation, axis context, linked variables and declared MATH/VAR. The previous BIN binding is always restored. The bytearray is used directly, preventing a whole-BIN bytes() copy for every cell. Dependency-free fake sessions keep a test-only fallback.
3. **MATH/VAR metadata reaches editor write paths.** Scalar, table and range forward conversions pass their declared math_element. A new synthetic integration suite exercises raw VAR aliases in individual and JSON batch writes, but this particular suite was not run locally because the pinned Exporter was unavailable.
4. **Flags refuse boolean masks** on single-object writes, consistent with read and batch validation.
5. **Offline runner:** run_offline_editor_qualification.py validates a trusted local 3.7.5rc1 Exporter wheel's declared package version, required modules and optional expected SHA-256, then executes the Editor pytest suite in a local Python subprocess using PYTHONPATH. It does not require GitHub Actions, network connectivity, or package installation. It writes a new private report directory. A wheel hash and version do not establish a Git source commit unless independently attested.

## Checks executed here

Python 3.13.5 and pytest 9.0.2. No GitHub Actions, customer data, ECUs or hardware:

~~~console
python -m pytest -q test_batch_plan_snapshot.py test_batch_readback.py test_offline_editor_qualification.py
........................................                                 [100%]
40 passed in 4.59s
python -m py_compile batch_plan_snapshot.py batch_readback.py run_offline_editor_qualification.py
# completed with no errors
~~~

The 40 passing tests cover exact byte snapshots, bounds, changed files, per-cell math/axis selectors, staged dependencies, restoring parser state on failure, 200 large-buffer reads without whole-image copying, synthetic wheel metadata rejection and local subprocess failure/success receipts. The wheel used in local tests was an intentionally synthetic test fixture, **not** the real pinned Exporter.

Local executed files matched the committed Git blobs:

| File | Git blob SHA-1 |
| --- | --- |
| batch_plan_snapshot.py | c64bf5340f1e9a016be0f589e3a8ef2e5519091c |
| test_batch_plan_snapshot.py | 806eae796a6025c7709fef6d9d392e38583bfbf0 |
| batch_readback.py | 777e58d600555642ac763d65b8b76246929f0586 |
| test_batch_readback.py | bf649da1fcf55e41dc03e8536dc41e24c8d296e6 |
| run_offline_editor_qualification.py | c60c1ffb2c43ee622752fd8c9d68e788580045b8 |
| test_offline_editor_qualification.py | 35c01e7324c9c037eb7ac7220fccb46441f46447 |

## Run the genuine suite with a trusted local wheel

Run from a real Editor source checkout with a new report folder outside the repository. The environment needs Python and pytest installed.

~~~console
python run_offline_editor_qualification.py --repo . --exporter-wheel /trusted/path/kingai_tunerpro_xdf-3.7.5rc1-py3-none-any.whl --report-dir /private/results/editor-qualification-01 --expected-wheel-sha256 VERIFIED_SHA256
~~~

To run selected tests first, append -- test_batch_plan_cli.py test_editor_declared_raw_alias.py. With no test selectors, the complete repository suite runs. Inspect the actual exit code plus pytest-output.txt and receipt.json; a receipt's mere existence does not indicate a pass.

## Unrun release gates

- Real pinned Exporter wheel source identity, genuine parser-dependent full suite and Editor installed-wheel smoke: not executed here.
- Native TunerPro XDF/BIN display and axes, permissioned exact OSID regression pairs: not executed here.
- ECU checksums/signatures, flashing, recovery, emissions, hardware and vehicle qualification: not evaluated.

The earlier coordinator receipt in docs/BATCH_TRANSACTION_VERIFICATION_20261022.md remains separate. Do not add the 40 new unit tests to its 58 previous passing tests and imply one integrated test execution.
