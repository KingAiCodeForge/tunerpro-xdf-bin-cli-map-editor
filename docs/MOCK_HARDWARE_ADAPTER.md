# Mock hardware-adapter contract (NO real ECU communication)

**Status:** software-only reference adapter. No live tuning, flash, ROM emulation, DLL loading, driver enumeration or physical device support is added. This is an independent code PR; do not confuse it with the unmerged batch-plan PR #10, checksum repair-to-copy PR #13 or the hardware roadmap PR #12.

The released CLI stays the sole entry point for both humans and agents. `mock_hardware_adapter.register_subcommands()` installs **two new read-only operations** on `kingai-map-editor` using the same declaration that powers its standalone mock smoke CLI. The mock never uploads or reads an ECU, even if a target ID is supplied. It uses Python stdlib only; no peripheral permissions are needed.

## Try it on a synthetic or operator-owned BIN

After installation from this PR's branch (`python -m pip install .`), run:

```console
kingai-map-editor adapter-probe
kingai-map-editor adapter-preview --bin synthetic.bin --expected-bin-sha256 <64-digit-SHA256> --expected-size <exact-byte-count> --target-id synthetic-ECU --receipt new-preview-receipt.json
```

The same parser is available for a dependency-free smoke test:

```console
python mock_hardware_adapter.py adapter-probe
python mock_hardware_adapter.py adapter-preview --bin synthetic.bin --expected-bin-sha256 <SHA256> --expected-size <SIZE> --target-id synthetic-ECU
```

Replace placeholders with real hash, size and an operator-provided label. A successful result contains `kingai.hardware-adapter-preview.v1`, source filename, SHA-256, exact length, a stable evidence digest, and **`hardware_write_executed: false`**. The `--target-id` label is *declared by the operator*, never independently read from an ECU. `device_readback` is `not_performed`, target compatibility and checksum state remain `not_assessed`. A checksum result, device identity or flash-readiness claim is **not** inferred.

The optional JSON receipt is written to a **new file only**; existing reports, input images and same-path aliases are refused. It is not a crash-atomic multi-file transaction; review any incomplete receipt after an abnormal process termination. By default the deterministic JSON receipt is printed on stdout and **no file is created**. Paths are not transmitted and only the input basename is included in JSON.

## What actually fails closed

- Missing or nonregular image, zero or excessive expected size (current demonstration cap: **64 MiB**), wrong exact length or wrong SHA-256.
- Malformed SHA-256, unsafe/ambiguous target label and unsupported adapter ID.
- Observable modification/replacement of the input image during read (before/after file metadata check); the mock verifies captured input, not that the same image is loaded in an ECU.
- Existing receipt destination, input/output alias, missing write permission or missing destination directory.
- Any attempt to select a real hardware writer; **only** `kingai.mock.read-only-image-v1` is registered. There are deliberately no writing methods in `ReadOnlyAdapter`.

SHA-256 is an identity/integrity binding relative to a trusted source, **not** an operator signature or physical target authentication. An evidence receipt is not permission to flash, program, burn, write NVRAM or update a ROM emulator.

### Windows path/descriptor timestamp compatibility — 26 October 2026

The local review reproduced valid unchanged synthetic inputs being refused on
Windows/Python 3.13.5 because `Path.stat()` and `os.fstat()` returned different
`st_ctime_ns` values. This matches the upstream
[CPython issue](https://github.com/python/cpython/issues/157671); the
[Python documentation](https://docs.python.org/3.13/library/os.html#os.stat_result.st_ctime_ns)
also marks Windows `st_ctime_ns` as deprecated with evolving semantics.

Admission now compares device, inode, size and modification time across the
path and descriptor APIs. Full metadata stamps, **including ctime**, must still
remain unchanged separately for path-before/path-after and descriptor-before/
descriptor-after. This avoids treating different timestamp meanings as a race
without dropping metadata-only mutation detection. Deterministic regressions
cover stable cross-API differences, each API's ctime drift, identity mismatches
and final-path replacement. These are best-effort checks, not an atomic snapshot
or permission to trust a concurrently writable image for hardware delivery.

## How someone forking this project should extend it

1. Fork/clone the MIT repository and work on a separate branch. Run the `pytest`/`unittest` checks on synthetic inputs first.
2. Implement the **read-only** `ReadOnlyAdapter` interface for a named adapter without reimplementing the Editor's XDF math, staging or receipts. Register only reviewed, explicit providers in source; the mock deliberately does **not** load arbitrary code or files based on model output.
3. Add versioned capabilities, exact hardware revision and host/driver ABI declarations, complete negative tests (missing DLL, wrong bitness, absent device, wrong OSID/image layout, timeouts, disconnect). Device identity can be reported as `unknown` until actually measured.
4. Real write-capable device tools need a *different*, explicitly permissioned interface and independent bench/recovery checks before activation. Do not bolt a flasher method onto the read-only mock or treat a valid preview receipt as authorization.
5. Submit the smallest independently testable PR with licence/provenance and a clear separation of `implemented`, `simulated`, `hardware tested` and `unverified` status. Vendor DLLs, proprietary firmware and customer data stay out of the public repository without distribution permission.

See the [full FlashOnline/NVRAM/EPROM fork guide](https://github.com/KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor/pull/12), and [CONTRIBUTING](https://github.com/KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor/blob/chatgpt/contributor-hardware-checksum-adapter-guide-20261025/CONTRIBUTING.md). Those remain separate proposed-documentation PRs until merged.

**ChatGPTz idea 💡:** the mock capability/receipt contract is AI-authored implementation inspired by the user's requested bring-your-own hardware system, PR #12's adapter roadmap, and the Editor's existing exact-source identity and fail-closed patterns. It is an implementation of a *safe simulated interface*, not a working physical interface.
