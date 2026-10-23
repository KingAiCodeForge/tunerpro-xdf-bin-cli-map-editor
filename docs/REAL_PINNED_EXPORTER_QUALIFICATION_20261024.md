# Real pinned Exporter and installed Editor qualification — 24 October 2026

Scope: isolated review of transactional PR #10 at
`5ee15d3ca185c5b684e3baee48d0e033dc7db4ae`, not a release, native-editor
comparison, calibration recommendation or hardware qualification.

## Exact-source identity, not a version-label assumption

The Editor declares Exporter commit
`e7c0ae86534791620ea0b843810f4980d24081d5`. The `v3.7.5rc1` tag resolves to
`9012420bb46717bf195432a37632e10878887a7b`, a different commit carrying the
same package version. The first tag-based source check correctly stopped;
the exact declared VCS commit was then fetched and used. No dependency pin
or tag was changed to make qualification easier.

A fresh wheel built from the exact pinned Exporter has SHA256
`8d60f2912b909b727c783dc886745d8246cbcad9c8dc7cf7c83637f323149eb9`.
The baseline Editor wheel has SHA256
`b84d8b0f63b12053b879b99a42967d46cdde784de110fe4ea5a1bca9c8c7f2cc`.
Build timestamps can change wheel hashes; these identify tested artifacts,
not a claim of bit-reproducible packaging.

## Implemented qualification improvement

The existing offline runner now accepts optional `--exporter-source` pointing
to a clean Git checkout. It verifies the exact dependency commit, binds each
non-metadata wheel payload to that commit, rejects uncommitted/substituted
payloads, unsafe/noncanonical paths and `.pth` startup files, and records the
payload proof. Only Python CRLF/LF normalization is permitted; other payloads
must match bytes exactly. Distribution identity/required modules and an optional
wheel hash remain separate existing checks.

Without the optional source, the existing workflow is unchanged and the receipt
still reports source provenance unverified. With it, the claim is limited to
checked non-metadata payload provenance. This does not independently reproduce
all distribution metadata, build tooling, signatures or native semantics.

```console
python run_offline_editor_qualification.py --repo EDITOR_CHECKOUT --exporter-wheel TRUSTED_WHEEL.whl --exporter-source PINNED_EXPORTER_CHECKOUT --expected-wheel-sha256 EXPECTED_SHA256 --report-dir NEW_PRIVATE_RESULTS -- -p no:cacheprovider -rs
```

Eight first-stage provenance checks failed before the new optional capability
existed; six actual-parser linked/alias/race contracts already passed. The
missing capability was an explicit qualification limitation, not evidence of
eight broken calibration algorithms. Additional guards cover noncanonical paths
and runner refusal before report creation.

## Actually executed before this review's final commit

- Baseline full Editor suite against the real pinned wheel: **382 passed,
  17 skipped**, exit 0, Python 3.13.5 / pytest 9.0.1. Its offline receipt correctly
  did not infer source provenance from version/hash alone.
- Fresh isolated environment, both actual wheels installed with `--no-index
  --no-deps`; `python -I` verified both imports came from its site-packages,
  not either checkout.
- Five hash-matched test modules staged outside the source checkout and run
  against those installed packages: **72 passed**, exit 0. These include real
  linked-variable order effects, full expected-byte output, big-endian factor /
  signed little-endian table quantization, alias collision refusal, and real
  BIN/XDF/plan mutation rollback. Runtime editing code was not rewritten.

- Enhanced full source suite with source-backed wheel proof: **399 passed,
  17 skipped**, exit 0, 59.61 seconds. All eight actual Exporter Python payloads
  match the exact dependency commit. The seventeen skips are existing optional
  real-image/workspace tests whose expected fixture layout is absent in this
  isolated checkout, not proof those files are absent from the user's machine.
- The actual installed console entry point also completed a read-only preview,
  published exactly one 256-byte synthetic output with the three independently
  expected changed bytes, and refused a wrong source hash with expected exit 1.
  Preview/save exit 0; all expected bytes and unchanged source hashes verified.

The exact review commit and private command/log paths are in the local handoff.
Source/installed/baseline suites overlap and must not be added as unique coverage.
Synthetic images and negative races are not customer firmware or native parity.

## Remaining gates

Reconcile with current main and its newer documentation without losing either
implementation. Keep the preserved unified `cab017d1` / Exporter `3bd4f803`
arithmetic/interpolation/smoothing lineage distinct; it was not ported here.
Native TunerPro controlled edits, authorized exact-target replay, checksums,
hardware/recovery and calibration safety remain unqualified. No GUI, firmware
patch, PR merge, default-branch promotion or release occurred in this review.
