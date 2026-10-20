# Editor Guard Follow-Up - 20 October 2026

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

## Qualification

Windows Python 3.13 source execution completed **266 passed, 17 skipped**
after the implementation. The skips remain unavailable exact-image integration
inputs; they are not real-definition passes. Final installed-package and
portable-bundle receipts are recorded separately after artifact execution.

No private definitions, customer files, original firmware, native TunerPro
session, ECU connection, checksum repair or flashing was used. Existing
source/wheel qualification receipts predate this follow-up and are not proof
for the new code. This remains experimental offline software.
