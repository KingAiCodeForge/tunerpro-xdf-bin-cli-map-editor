# Bring-your-own checksum, logging, live-calibration and flasher adapters

**KingAI Pty Ltd / KingAiCodeForge | 25 October 2026 (ACDT)**  
**Status:** Public integration design and invitation for contributions. **No hardware, DLL, checksum repair, online calibration or flash adapter is enabled by this document.**

This roadmap is for experienced calibration engineers, reverse engineers, hardware-interface authors and software contributors who want to fork the MIT-licensed [KingAI CLI Map Editor](../README.md), review its contracts, or submit a focused pull request. The intended experience is: **a person states a goal in natural language, an agent reasons over permissioned logs and calibration data, and deterministic tools perform narrow, auditable file operations.** Device communication and ECU writes remain separate optional adapters, not a side effect of editing a BIN.

An XDF describes calibration data; an ADX may describe data acquisition; an XDL is a log container. **None by itself proves that a connected ECU supports live calibration writes.** An ECU's supported protocols, software, access level, emulation hardware and recovery procedure determine what is possible.

**Professional-use boundary:** Software interfaces are not substitutes for competence. Hardware ownership, an installed DLL or a successful connection does **not** demonstrate proficiency, authorize reflashing, establish correct ECU identity or make live tuning safe. Work on supported, legally accessed equipment with independent procedures for power stability, diagnostics, backup, recovery and validation. Nothing here is a vehicle-use or emissions-compliance certification.

## Present capabilities versus proposals

For a **device-by-device walkthrough**, see [FlashOnline, NVRAM, EPROM/EEPROM burners, OBD/bench flashing and how to build an adapter in a fork](FLASHONLINE_NVRAM_EPROM_AND_BYO_HARDWARE_GUIDE.md). That guide explicitly separates host BIN edits, hardware emulation, live datalogging, diagnostic programming and chip burning, and distinguishes baudrate-derived lower bounds from real flash-tool timings. The sample code is a mock, not an installed plugin API.

| Component | Status in public repository | What it does / cannot yet do |
| --- | --- | --- |
| XDF/BIN read, preflight, guarded single edits, diff | On `main`, fixture-scoped | Reads and edits **copies** of files. Not online editing. |
| Transactional multi-edit JSON plan `kingai.xdf-batch-plan.v1` | [Draft PR #10](https://github.com/KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor/pull/10), unmerged | BIN/XDF SHA-256-bound batch candidate; no released batch capability. |
| Datalog → agent → proposed plan, ADX/CSV/XDL import | [PR #11](https://github.com/KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor/pull/11) roadmap; not implemented | Future evidence ingestion. PR #10 does **not** bind datalog hashes; proposed sidecar would. |
| Registered, trusted checksum **verification** | Already in `raw_patch_checksum_profiles.py`, for strict raw-patch manifests | Read-only checksum checking, **not** generalized checksum repair. |
| Checksum repair adapters; third-party DLL host bridge | Proposed | No `repair-checksum` CLI command or generic DLL loader is implemented. |
| Live telemetry, online RAM/emulator writes, ECU flashing | Proposed separately | No current reader, live calibration writer or flasher in this repo. |

### Public checksum reference material already present

The repository has **code with synthetic regression tests**, rather than only an idea:

- BMW MS42 `0110C6` CRC16 read-only verification: `raw_patch_checksum_profiles.py`, `test_raw_patch_checksum_profiles.py`.
- BMW MS43 `430069` CRC16-only and full five-checksum verification contracts: `raw_patch_checksum_profiles.py`, `test_ms43_raw_patch_checksum_profile.py`. CRC-only does not cover the additive layers.
- Holden VY `$060A` / `92118883` additive-16, **checksum-bypass-state-aware** verification: `raw_patch_checksum_profiles.py`, `test_vy_raw_patch_checksum_profile.py`. **Never silently alter the gate byte or assert a disabled checksum is active.**

These are exact-target examples of *verification*. They are **not** working generic repair plugins and do not establish compatibility across an ECU family. Their synthetic tests do not replace independent native tool, real image and hardware qualification. Future contributed adapters can use the same profile-first, golden-fixture approach and may be developed using the maintainer's lawfully sourced research corpus without publishing the corpus itself.

## One editor, separate adapter families

### A. Checksums: verify first, then repair a *copy*

**Proposed contract**: identify an exact target, inspect named checksum ranges and stored values, `verify(input)` without writes, optionally `repair_copy(input, destination)` using a registered versioned algorithm, then `verify(output)` and publish a byte-level receipt. Do not overwrite input. Validate original OSID/layout, image length, checksum descriptors, seeds, byte order, excluded ranges and all dependency ordering. For layered checksums, a single apparent match is not sufficient.

A repair receipt should include algorithm/profile version, original and output full SHA-256, covered and stored ranges, original and computed values, corrected offsets, and verification outcomes. Separately compare and account for *all* new bytes. Any missing layer, unsupported image layout, unexpected code edit or independent checksum disagreement must fail closed.

**Bring your own**: a reviewed pure Python implementation, a licence-compatible separately built native library, or a local vendor-supplied tool. A **TunerPro checksum DLL is not automatically a standalone callable checksum library.** It may expect TunerPro's plugin ABI, lifecycle, XDF-selected configuration and 32-bit Windows environment. Do not assume that `ctypes.CDLL(path)` plus guessing an export will reproduce TunerPro. Implement a documented host-compatible bridge only when the actual ABI, licence and test vectors are known; otherwise let TunerPro or the owner's existing tool run the plugin in its supported environment and inspect the independently saved result.

For third-party native helpers, prefer an allowlisted **separate local worker process** with a documented interface and matching 32-/64-bit architecture. Confirm ABI/exports and version; sandboxing may limit software faults but cannot remove the consequences of bad output. Never load an arbitrary DLL or execute a plugin URL from a model-generated edit plan. The operator obtains/install libraries themselves; no unlicensed DLLs are redistributed.

### B. Live *data acquisition*: read-only hardware first

Supported adapter patterns to investigate, independently of target ECU write support:

| Pattern | Intended use | Not implied |
| --- | --- | --- |
| TunerPro RT + device-specific acquisition/emulation plugin | Use a vendor-supported ADX and plugin for data acquisition and, on specific supported systems, emulation. Export files for analysis first. | A plugin built for the **TunerPro host** will necessarily work when loaded directly by KingAI. |
| SAE J2534 PassThru **vendor DLL** | Windows transport through an installed compatible VCI; enumerate device, protocol and read-only capabilities using the manufacturer's API and drivers. | J2534 transport identifies maps, implements proprietary ECU programming, or supports real-time RAM calibration. |
| USB serial / ALDL / K-line adapters | Platform-specific logging through proven transports and decoders with immutable datalog capture. | A compatible physical port proves protocol/ECU/write compatibility. |
| CAN / CAN-FD with established vendor API | Read-only diagnostics and timestamped acquisition where permitted. | An arbitrary CAN interface enables ECU calibration writes. |
| XCP with a supported interface and authorized target | Measurement and, where **explicitly supported by the ECU**, calibration-oriented operations with correct target metadata. | Every XCP interface or A2L gives an unlocked online writable ECU. |

**Read-only acceptance gate**: exact hardware/driver versions, permission to access target, bounded connection timeouts, stable timestamps, ADX/channel conversion parity where relevant, unit and sensor provenance, disconnect/reconnect test, replay against recorded synthetic traffic, capability reporting and a no-write-by-default test. A log's vehicle state is not equivalent to an ECU image checksum or calibration selector.

### C. True live calibration and emulation: opt-in and target-specific

Three different experiences must not share a misleading “Live Tuning” switch:

1. **Live monitoring:** read and visualize data while the engine is running. **Read-only**.
2. **Live emulation / calibration RAM changes:** write temporary data only when a proven ECU/emulator/protocol explicitly supports it; validate actual values and state. A suitable emulator may use a specialized host plugin.
3. **Offline edit and reflash:** save a new BIN, repair/verify checksums separately, explicitly flash with compatible tooling, then re-log. This is an iterative *offline* tuning loop, even when each run is quick.

Only the first should be investigated as a generic acquisition abstraction. The others require named, independently tested hardware and ECU-specific adapters, operator-supervised conditions, safe-stop behaviour, verified readback and recovery arrangements. **No unrestricted agent-commanded ECU writes.**

### D. Flashers: explicit hand-off to a qualified external tool

A future flasher adapter should **not** assume that an editable BIN is a flashable BIN. Keep hardware flashing outside the default Editor process. Prefer a reviewed local tool-specific adapter over trying to create a universal flasher inside this repository.

Suggested process, not an existing command:

`edited BIN + full-byte receipt` → `registered checksum repair or explicit not-applicable result` → `independent checksum verify` → `exact ECU/software/size/preflight eligibility check` → `hardware/driver/recovery and stable-power precheck` → `explicit operator-directed flasher step` → `tool-specific verify/readback/report` → `re-log with new BIN/session identity`.

For tools using external executables, support only approved commands and **argument arrays**, not shell interpolation, arbitrary code in a manifest or model-supplied scripts. Keep credentials outside reports. Detect executable identity and version, refuse ambiguous device selection, and preserve the complete tool outcome. A timeout or dropped connection must never be described as a successful write. The operator must retain an ECU-specific recovery path if the flash fails.

## Proposed adapter contract, not a shipped API

The editor should request declared capabilities rather than infer them from a filename, transport name or USB device presence. A future stable API could conceptually expose:

```text
identify_adapter() -> id, version, vendor, licence, ABI, binary_hash
probe_target(read_only=True) -> transport, observed_identity, capabilities
verify_image(input_hash, profile_id) -> verified_ranges, result, evidence
repair_image_copy(input_hash, profile_id, output_path) -> new_hash, changed_bytes, evidence
capture_log(session_id) -> immutable_log_path, timestamps, channel_metadata
prepare_hardware_operation(target, intended_capability) -> pass | refuse + reason
execute_supervised_operation(approved_artifact, explicit_target) -> recorded_outcome
independent_readback_or_verify() -> matching | mismatching | unsupported | inconclusive
abort_or_safe_stop() -> outcome
```

There is **no implementation, exposed command or supported schema** behind these names. The actual plugin API should use typed validated data, version negotiation and a distinct worker for foreign executable code. Capabilities should be independently tagged, e.g. `read_telemetry`, `online_emulation`, `calibration_ram_write`, `offline_flash`, `checksum_verify` and `checksum_repair`. No capability should imply another.

**ChatGPTz idea 💡 — read-only adapter certification pack.** Inspired by the existing immutable exact-hash fixture gates and checksum tests: contributors should first ship a *simulator/mock transport* and a replay fixture for the advertised adapter, including correct and failing handshakes and timeouts. Only once this is independently reproducible should the maintainers consider exposing a real hardware path. A standardized public-safe capability receipt (driver + protocol + device class + no-write tests + observed target identity) would let users compare adapters without uploading proprietary logs.

## Acceptance checks per contributed adapter

1. **Provenance and licence:** identify original creator, source URL or private provenance, licence/permission evidence, permitted redistribution, dependency versions and any upstream attribution; do not equate publicly accessible code with permissive licensing. For independently reverse-engineered interoperability, document the evidence and do not copy proprietary binaries, secrets or third-party code without redistribution rights. MIT applies to KingAI-owned code **only**.
2. **Exact target selection:** supported software/hardware IDs, images and versions. Refuse unsupported or missing identities and unverified cross-OSID reuse.
3. **Determinism:** checked data types/units, bounded inputs, stable filenames, hashes, atomic-or-exclusive new-file publication and auditable changed-byte receipts where relevant.
4. **Negative tests:** missing/corrupt DLL, incompatible ABI/bitness, absent hardware, unsupported ECU, checksum mismatch, truncated image, bad or stale log source, lost connection, timeout, file race, partial write and unexpected output.
5. **Independent parity:** compare any checksum result with independently understood reference vectors and native tool outputs; verify acquisition samples against an established decoder; for flashing require recorded recovery and actual hardware qualification.
6. **Default rights:** offline and read-only operations by default. No internet plugin download, automatic adapter activation or ECU writes triggered just by importing a file or an AI prompt.
7. **Public fixture hygiene:** synthetic, owned or explicitly licensed data only; redact VINs/customer identifiers, ECU secrets, private calibration images, API tokens and machine paths. Hash-only evidence can support private-corpus checks without exposing content.

## Suggested narrowly scoped contributions

- **Good first contribution:** add a synthetic fixture and failing/valid checksum test for one existing profile; improve Windows-vs-Linux plugin/driver documentation; improve read-only adapter diagnostic messages.
- **Checksum contributor:** propose one exact-OSID verify/repair-copy pair with known ranges, ordered dependencies, golden vectors and full-diff tests. A verified public algorithm can be reused with attribution, subject to licence.
- **Hardware contributor:** start with a mock J2534 or serial/ALDL transport that provides capability discovery, read-only replay and disconnect tests. Bind no flasher.
- **TunerPro plugin contributor:** document a legally obtained plugin API/ABI and show read-only native-host parity before proposing direct DLL bridging; an alternative supported native-host export route is welcome.
- **Flasher author:** submit a proposal or simulator-only adapter demonstrating explicit operator handoff, evidence preservation and failure handling. Any real write-capable integration requires an additional review and qualification track.

See [CONTRIBUTING.md](../CONTRIBUTING.md) for PR scope, reproducible issue reports and collaboration. Focused PRs, design critiques, field reports and test vectors are welcome. The editor is MIT-licensed and can be forked; plugin authors retain rights to their own separately licensed work.

## Technical references (not endorsements or bundled dependencies)

- [Official TunerPro plugin catalogue](https://www.tunerpro.net/downloadPlugins.html): examples of different data acquisition, emulation and other host plugins.
- [TunerPro RT acquisition/emulation setup for a supported ReFlex target](https://support.motivmotorsport.com/index.php/TunerPro_RT_Setup): an example of ADX and hardware-specific online behaviour, **not** universal support.
- [GM checksum plugins (Apache-2.0 project)](https://github.com/joukoy/gm-checksum-plugins): externally licensed example; inspect each component and licence before code reuse. **Not shipped here**.
- [SAE J2534 adapter vendor documentation](https://opusivs.com/support/oem-customer-support/program-sae-j2534/discovery-of-the-dll/): registry-based Windows DLL discovery, a transport abstraction rather than an ECU programming strategy.
- [ISO 22900-2 D-PDU API standard description](https://www.iso.org/obp/ui#iso:std:iso:22900:-2:ed-3:v1:en): alternative VCI interface model.
- [PEAK-System PCAN-XCP API](https://www.peak-system.com/products/software/development-packages/pcan-xcp-api/): an example of a vendor-specific calibration/measurement protocol API and its prerequisites.
- [TunerPro-compatible checksum DLL installation/selection](https://www.mtx-automotive.com/product/tunerpro-plugins?lang=en): demonstrates host-specific checksum configuration; **not** a guarantee of a standalone callable ABI.

Treat all vendor APIs and licences as version-specific. References above explain integration patterns; no third-party DLL or tool is silently bundled, called or endorsed.
