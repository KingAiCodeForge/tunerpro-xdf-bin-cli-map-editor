# Editor Guard Follow-Up - 20 October 2026

Version: **1.2.0rc2**. Public PR #7 independently merged the broader integration
and published v1.2.0rc1 while this guard follow-up was in progress. That new
main was merged here without deleting or rewriting either history. Its BMW
documentation corrections, two tests and CI fixture staging are retained.
No v1.2.0rc1 release asset is replaced by this follow-up.

This continues preserved integration candidate
`383befae5d77bcd354c4bef880cda4692600c8cd`, not a rebuild from an older
checkout. The dependency remains exact Exporter source
`e7c0ae86534791620ea0b843810f4980d24081d5` (3.7.5rc1).
Both earlier public editor PR histories remain retained in the candidate.
All fixtures in this follow-up are generated XML and bytes, not firmware.

## Changes

1. A table range is checked against its completed staged image. An address
   variable referencing a later cell can change an earlier engineering value;
   per-cell checks alone do not catch that. A two-row `X+if(A==0;Y;0)` fixture
   reproduced records of 10/10 with final values of 17/10. The CLI now refuses
   the operation before saving. Exceptions and interruption restore the
   range's bytes and appended audit state without undoing prior session work.
2. Inverse validation retains the adjacent-value collapse guard and also
   refuses a candidate when an in-bounds neighbor decodes closer to the
   requested value. `(X+1e16)-1e16+0.1*X` at request 2.8 reproduced raw 3 /
   value 4.3 although raw 2 gives 2.2. This is not a general numerical inverse,
   global nearest-value proof, or qualification of arbitrary nonlinear math.
3. Fractional raw requests are rejected explicitly. This is a documented
   input-policy tightening: -0.4, 2.5 and 255.4 are not rounded to 0, 2 and 255.
   Integral float CLI inputs and supported integer boundaries still work.

`test_editor_review_guards.py` exercises full-parser CLI refusal, session
rollback with prior edits, interrupted/empty/out-of-bounds ranges, precision
below six audit decimals, successful audited save, unstable equations,
positive/negative affine half-step ties and integral/fractional raw input.
The initial red run reproduced the CLI/numerical/input-policy gaps; tests
requiring the newly introduced range API failed until it was implemented.

## Initial Qualification Before PR #7 Reconciliation

Runtime/test source commit:
`c4a5119c7c721bc0c26eecb1d4df9d2bd8b44c48`. This documentation receipt is
committed afterward; it does not alter the qualified runtime modules.

| Execution | Measured result |
| --- | --- |
| Windows / Python 3.13.5 source | 266 passed, 17 skipped; 35.16 s |
| Windows / Python 3.13.5 fresh installed wheels, tests copied away from source, `-I` / importlib mode | 266 passed, 17 skipped; 37.47 s |
| Ubuntu 24.04 / WSL / Python 3.12.3, fresh installed identical wheels, tests copied away from source, `-I` / importlib mode | 265 passed, 18 skipped; 19.28 s |
| Seven Editor plus eight Exporter runtime modules | Exact Git blob = wheel = Windows installed bytes; identical wheel hashes and wheel = installed module bytes rechecked on Linux |
| Windows offline bundle, extracted path with spaces and unrelated working directory | Fresh install, `pip check`, installed help passed; repeated install refused the existing environment |
| Windows clean online dependency resolution from Editor wheel | Fetched exact declared Exporter Git commit, built/installed dependency, `pip check` and installed help passed |

The 17 common skips remain unavailable exact-image integration inputs, not
real-definition passes. WSL's missing `ensurepip` adds one explicit environment
skip. Linux qualification used a fresh stdlib venv with a separately downloaded
pip wheel as bootstrap; no system packages were installed. This does not prove
that the standard offline installer works on a host without venv/ensurepip.
No macOS or Python 3.10 execution is claimed. Hosted CI remains a separate gate.

Initial qualified local artifacts before reconciliation with PR #7. These
are preserved historical outputs, not the published v1.2.0rc1 release assets
or the new v1.2.0rc2 artifacts:

| Artifact | SHA-256 |
| --- | --- |
| `kingai_tunerpro_map_editor-1.2.0rc1-py3-none-any.whl` | `0b00f72385cea3357f6331accbce7b1d8cde2147808756a35a556f5350d77e09` |
| `kingai_tunerpro_map_editor-1.2.0rc1.tar.gz` | `8b166d68c7acd8a2e18e59c3d6173687067ad528a1b1718613ada180c616bd25` |
| `kingai_tunerpro_xdf-3.7.5rc1-py3-none-any.whl` | `10d695ab3e9b46773286f44267f01e285e8a9e4dada5fe1c1a31b79d3e238c3c` |
| `kingai-editor-1.2.0rc1-offline.zip` | `738f3ef1be66742d70d382b84be66762c3374226971abd24b3766eba000fed02` |

The first artifact attempt was rejected for CRLF conversion relative to Git
blobs, despite matching logical source. Its files were preserved separately.
The passing artifacts came from an archive created with invocation-local
`core.autocrlf=false` and `core.eol=lf`; no persistent Git setting was changed.
The initial Linux ensurepip setup failure was recorded, not counted as
a passing test run.

## Final 1.2.0rc2 Qualification

Combined runtime/test source commit:
`76a893cd495f7f5ab98f7c672ca723139a720377`. This includes merged public main
`6b8e2be7aa07af8b20e1f2588d12a16619112deb` and preserves all PR #7 changes.
The final documentation receipt is committed afterward; runtime is unchanged.

- Windows Python 3.13.5 source: **268 passed, 17 skipped** (34.42 s).
- Windows fresh installed rc2 wheels, isolated/importlib tests away from
  source: **268 passed, 17 skipped** (36.81 s).
- Ubuntu 24.04 / WSL Python 3.12.3 fresh installed identical rc2 wheels:
  **267 passed, 18 skipped** (14.53 s on the persisted-receipt replay).
- All 15 runtime modules again match committed Git blobs, wheels and Windows
  installed bytes; Linux wheel/installed equality and identical wheel hashes
  were independently rechecked. Linux receipt was saved to the shared drive.
- The actual rc2 offline bundle installed to a fresh Windows path with spaces
  from an unrelated working directory; pip check and installed help passed,
  and repeating installation refused the existing environment.
- A fresh rc2 online install resolved the unchanged exact Exporter Git pin
  using the previously built dependency wheel cache; pip check and help passed.

| Final rc2 artifact | SHA-256 |
| --- | --- |
| `kingai_tunerpro_map_editor-1.2.0rc2-py3-none-any.whl` | `3ac377a1b2464729c0b4a17c464872977d67f247fab334339c884dae797746df` |
| `kingai_tunerpro_map_editor-1.2.0rc2.tar.gz` | `c4dde9d7c7a7e0826a9437f1cf49c19612315adabe34ec4751ea282c66eb71f3` |
| `kingai-editor-1.2.0rc2-offline.zip` | `a8ba7067478de36f0ba163b15853da39a7024e421af0ce8050bfd22cfeea66fe` |

These are locally built/tested artifacts, not a claim of a new GitHub Release.
PR #8's hosted matrix failed before running steps: GitHub reported an account
billing lock. No billing setting or branch protection was bypassed. The same
missing-input, ensurepip, native TunerPro, Python 3.10/macOS and physical holds
above remain open; no existing release asset was replaced.

No private definitions, customer files, original firmware, native TunerPro
session, ECU connection, checksum repair or flashing was used. Existing
source/wheel qualification receipts predate this follow-up and are not proof
for the new code. This remains experimental offline software.
