# Synthetic transport adapter contract R1 (not hardware)

**KingAI Pty Ltd | 25 October 2026 | Draft contribution**

**Status:** Source-checkout-only, stdlib Python reference. No device I/O, ECU image mutation, checksum repair, external tool/DLL loading, native flash handoff or installed package entry point. `probe-mock` *does not probe hardware*. `preview-upload` *does not upload* anything: the name demonstrates what a future request would look like before hardware capabilities exist. The separate CLI Map Editor on `main` does not discover or call this mock.

**ChatGPTz idea 💡:** Turn the proposed public bring-your-own adapter guide into an executable, deliberately non-hardware contract test. Inspired by the guarded Editor's exact-source SHA-256 admission and deterministic byte receipts, and by the mock contribution described in the guide's Step 3. This reference implementation is AI-generated and subject to maintainer review. No user/customer hardware data was used.

## Run from a source checkout

Python 3.10+; no installed Editor, pinned Exporter, device DLL, adapter, hardware, `pip install` or extra dependencies required.

```shell
python -m extensions.mock_transport_adapter probe-mock
python -m extensions.mock_transport_adapter preview-upload --bin synthetic.bin --expected-size 512 --expected-sha256 <64-digit-exact-SHA256>
python -m unittest -q test_mock_transport_adapter.py
python -O -m unittest -q test_mock_transport_adapter.py
```

Supply an **operator-owned synthetic fixture** (`synthetic.bin` above is an illustrative placeholder). Any `flash` or `erase` operation is an explicit structured refusal; unknown CLI commands fail before execution. Only JSON is emitted to stdout by supported commands. Process exit `0` means *synthetic contract operation succeeded*, never that an ECU was changed. Exit `2` means a bounded refusal. Python/argparse failures (e.g., an unknown command) use conventional nonzero exit status and may print human-oriented usage to stderr.

The result schema is `kingai.mock-transport-receipt.v1`, with a canonical JSON self-hash (`receipt_sha256`). A **self-hash is not a digital signature, secure audit log or third-party attestation**; it only allows detecting accidental/tampered body changes relative to a trusted receipt hash. The receipt deliberately contains no timestamp, path, customer identity, private firmware bytes or device serial. Repeated inputs produce byte-identical JSON.

## Decisions and proof boundaries

| Operation / condition | Output | No-claim boundary |
| --- | --- | --- |
| `probe-mock` | Static 8-bit synthetic descriptor, empty hardware/ECU allowlists | No real device selection/identification |
| Valid BIN-size + SHA-256 `preview-upload` | `SIMULATED / PREVIEW_ONLY`, hash/length evidence | No device connection, transfer, checksum or readback |
| Wrong BIN hash/size, invalid request, link input, detected file race | `REFUSED` with stable code | File admission only |
| Simulated disconnect, timeout, driver missing, duplicate device, unsupported target, inconclusive readback | `REFUSED` with stable code | Test scenarios, not device/driver test results |
| `flash` or `erase` | `REFUSED / HARDWARE_WRITE_DISABLED` | A real writer must be a different, separately qualified and human-approved component |

The adapter caps file-size declarations at 16 MiB, reads by bounded chunks and checks regular-file identity before/after hashing. The file race checks are best effort; they are **not an atomic snapshot** if an untrusted process can mutate the input concurrently. Real delivery adapters should consume an immutable, hash-verified staged copy under a separately reviewed storage trust model.

## Contributor acceptance / independence

Run both normal and optimised Python tests; they should agree (`-O` must not remove required checks). Examine `test_mock_transport_adapter.py` for negative scenarios, no-file-write evidence and deterministic JSON/self-hash checks. A future hardware adapter must be a **separate PR** with a compatible-but-stricter capability descriptor, independent golden vectors, licence/ABI review, full device identity, a real handshake and readback, explicit human authorization, physical power/recovery qualification, and refusal if any step is unproven. Do not silently widen this mock's synthetic allowlist or treat its `SIMULATED` status as permission to flash.

This contract is *not* yet a plugin for the editor. Deliberate decoupling prevents an external tool, a compromised model prompt or a malicious manifest from acquiring a hardware write path simply because it emits JSON.
