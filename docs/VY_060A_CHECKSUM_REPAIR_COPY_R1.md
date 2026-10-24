# VY $060A exact-target checksum repair-to-copy R1

**ChatGPTz idea 💡: AI-generated, research-review adapter.** Inspired by the existing trusted VY additive-16 verifier and PR #12's proposed checksum-plugin contribution path. It is not a general plugin loader, a tuner, a flasher or a physical safety qualification.

## New candidate implementation

The standalone `checksum_repair_copy.py` module uses the existing `raw_patch_checksum_profiles.py` trusted verifier. It does not accept arbitrary checksum code, vendor DLLs, ECU adapters, user-defined offsets or data mappings. The legacy editor CLI is unchanged.

It requires an operator-supplied whole-image SHA-256, 131,072 bytes, OSID `92118883` at `0x07FFC`, and preserved bypass marker `0xAA` at `0x04008`. The verifier's additive checksum calculation is:

```python
(sum(image[0x02000:0x04000]) + sum(image[0x04008:0x20000])) & 0xFFFF
```

The calculated value is stored as **big-endian** bytes at `0x04006–0x04007`. The only permitted differences are those two checksum bytes. The eight-byte gap `0x04000–0x04007` is excluded from the calculation, but the `0xAA` bypass marker at `0x04008` is included and must remain unchanged.

**Important:** `0xAA` is recognised as a checksum-bypass state. Repairing the stored value does not enable ECU checksum enforcement or make a BIN flash-ready.

## CLI

```console
# Preview only
python -m checksum_repair_copy --bin "VY_input.bin" --expected-sha256 FULL_SHA256

# Explicit new output directory; never overwrite original
python -m checksum_repair_copy --bin "VY_input.bin" --expected-sha256 FULL_SHA256 --output-dir "new_checksum_review"
```

The proposed installed-package entry point is `kingai-checksum-copy`. The adapter refuses unsupported profiles, invalid gate/OSID, incomplete files, input hash mismatch, already-valid no-op copy, existing directories and unexpected byte differences. It rereads its copy and emits a JSON receipt with before/after hashes, values, offsets and unresolved qualification.

The existing test suite also records a parent/checksum-control reference of `0x8E6F` versus `0x9E9F`; the new **synthetic** golden vector reproduces that pair without distributing the real Enhanced BIN.

## Verification status and boundaries

- Local candidate tested using a **source-matched test-only mirror** of the existing VY verifier API, based on public source blob `e27988da8b730455f3d7a3709871ae45627956e6`: **24 synthetic pytest tests passed** (exit 0).
- Four supplementary unittest checks passed under optimised Python. The remaining pytest tests use normal assertions and must not be counted as meaningful under `python -O`.
- The public GitHub repository's actual `raw_patch_checksum_profiles.py`, pinned private real firmware fixture and full editor-suite smoke test have **not** been executed together in this sandbox. They remain integration-owner gates; no user/customer BIN is included here.
- This separate PR is a proposed plugin increment, not a merge of documentation-only PR #11/#12. No J2534, serial, ALDL, K-line, CAN, XCP, hardware access, flashing or checksum-gate alteration.

Do not automatically call this after an arbitrary map edit: the input image SHA, exact OSID, actual checksum profile, XDF/BIN pairing and operator scope must be verified first. Neither a correctly stored additive checksum nor a successful static BIN diff establishes ECU, calibration or vehicle safety.
