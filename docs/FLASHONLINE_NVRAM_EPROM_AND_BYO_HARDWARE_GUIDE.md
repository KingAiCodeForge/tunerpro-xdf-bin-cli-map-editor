# FlashOnline, EPROM/NVRAM, EEPROM, in-car flashing and bring-your-own hardware integrations

**KingAI Pty Ltd / KingAiCodeForge · 25 October 2026 (ACDT)**  
**Audience:** experienced tuners, ECU developers, hardware/plugin authors, reviewers and people cloning or forking the MIT-licensed [KingAI CLI Map Editor](../README.md).  
**Document status:** technical integration guide, vendor-grounded examples, **not a working hardware plugin, flash command or timing benchmark**.

**Important release boundary:** Editor \`main\` version 1.2.0rc2 reads/inspects XDF+BIN and supports a narrow set of guarded edits to **new files**. It is not an ECU flasher or live tuner. [Batch PR #10](https://github.com/KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor/pull/10) remains a separate **unmerged draft**. The proposed adapters, semantic handles, signed plans, user-interface registry and external hardware commands in this document **do not exist in the released program**. No undocumented CLI arguments, device DLLs, proprietary binaries or firmware are supplied here. Consult [hardware and checksum roadmap](HARDWARE_CHECKSUM_FLASH_PLUGIN_ROADMAP.md) and [CONTRIBUTING](../CONTRIBUTING.md).

The Editor should become broadly extensible through **one deterministic file-edit and receipt path** and separately permissioned hardware interfaces. An XDF, BIN, datalog and a connected USB interface alone do **not** prove that the ECU can be programmed or that its calibration can be changed with the engine running.

## 1. Which kind of tuning or write are we talking about?

| Operation | Physical target and method | Is it live tuning? | Distinct checks and risks |
| --- | --- | --- | --- |
| Local BIN/XDF change | Host PC writes **new** file; no hardware involved | **No** | Exact source/definition/OSID, conversion, raw storage, full byte diff |
| Live datalogging | ALDL/K-line/CAN/J2534/etc. read telemetry only | **No** (live *observation*) | Correct channels, timestamp alignment, no write capability implied |
| ROM/flash **emulation** | Dedicated emulator occupies chip interface and presents a host-loaded image; some support updates while ECU runs | **Yes, when this exact hardware and ECU are qualified** | Bus width/voltage/socket, bank selection, runtime update atomicity, coherence, rollback |
| NVRAM-based calibration | ECU/aftermarket board stores calibration in nonvolatile RAM, perhaps with an online update protocol | **Sometimes** | Physical board, memory map, write protection, ECU running state and data persistence |
| In-car diagnostic flashing | OBD/diagnostic-session reprogramming over serial/K-line/CAN/CAN-FD/DoIP/etc. | **No**, normally a programming session | Exact ECU and image, bootloader protocol, erase/program/verify, power, recovery |
| Bench or boot-mode flashing | ECU on a bench, via manufacturer/programmer diagnostics, boot/BDM/JTAG/SWD where lawfully supported | **No** | Pinouts and regulated power, flash geometry, exact protocol, recovery |
| External EEPROM/EPROM/flash burner | ECU memory chip removed/socketed or legally accessible with a qualified programmer | **No** | Chip ID, erase/program voltage, package/pinout, orientation, readback, soldering |
| External flasher/app handoff | Editor prepares file; existing independently qualified tool handles programming | **No**, unless that separate tool controls a verified live emulator | Tool-specific status is not universal verified ECU readback |

**Avoid shorthand that conflates memory types.** UV-erasable EPROM (e.g. windowed 27C256), one-time-programmable EPROM, electrically erasable EEPROM, NOR flash and battery-backed/NV SRAM have different programming, erase and retention rules. A chip *burner* usually programs a device while an *emulator* temporarily substitutes for that device. A serial EEPROM storing adaptations is not necessarily the main program/calibration flash.

## 2. FlashOnline is an emulator, not an OBD flasher

[CobraRTP FlashOnline R4](https://cobrartp.com/en/product/flashonline/) is marketed by its manufacturer as a **28Fxxx/29Fxxx flash-memory emulator**. It is not a generic J2534 box, not software that flashes arbitrary ECUs over the OBD socket, and not a checksum calculator.

Per the manufacturer's published product notes, FlashOnline R4 targets supported **28F200, 28F400, 29F200, 29F400 and 29F800 memory in SOP-44 form**, with listed ECU/CPU examples including Siemens MS42/MS43. The exact ECU board **must be inspected for actual compatible memory and hardware**, regardless of ECU family names in marketing lists. These lists are *vendor-stated candidates*, not KingAI compatibility tests or approvals.

**Manufacturer-described workflow** (not a KingAI implementation):

1. Inspect exact board, flash chip and physical socket/adapter, ECU software and full-image size; arrange compatible emulator installation by a qualified person.
2. Load the complete **correct firmware image** into the emulator first. For example, the manufacturer's FAQ uses a 29F400 **512 KiB** image. A 32 KiB calibration-only window cannot simply be used as the initial full-chip image.
3. Subsequent host calibration changes may be uploaded through supported **TunerPro RT** emulation or the vendor's **CobraRTP Utility**; that utility describes an **Autoupload** file-change workflow. The emulator supports *the vendor-supported update mechanism*; it does not identify or authorize the correct map.
4. Keep **checksum and signature handling separate**: the manufacturer explicitly says FlashOnline does **not** calculate the ECU checksum. A host image update cannot be treated as a completed checksum repair.
5. Some ECU operations require an ECU ignition/restart cycle, and the manufacturer's FAQ states writes **from the ECU side into the emulator memory** (including relevant adaptations) are not supported. Don't infer full persistent ECU flash behavior from a successful emulator upload.
6. After development, reinstalling/programming a physical flash chip or a separately supported OBD flash is **another workflow** with its own exact-file, tool, write, checksum, verification and recovery gates.

**KingAI proposed first integration:** do **not** invent a FlashOnline USB protocol or reverse engineer a vendor DLL as a prerequisite. Start with the Editor writing a uniquely named, audited BIN, then an **explicit operator-directed handoff** into the vendor's supported utility, using a dedicated staging file only if vendor file-watch semantics are verified. A file watcher could read a partially copied file, reuse a stale image or upload a wrong bank; exercise stable naming, image/hash checks, synchronization and readback in a safe mock before attempting hardware.

**MotronicRT is a different product.** [CobraRTP MotronicRT R6](https://cobrartp.com/en/product/motronicrt/) emulates primarily older **27C128/27C256/27C512 EPROM** families plus specific 28F512 adapters. Its published hardware modes and fitment must not be copied into a FlashOnline R4 profile; don't assume an EPROM adapter supports 16-bit SOP-44 flash.

**Source:** [FlashOnline R4 product and FAQ](https://cobrartp.com/en/product/flashonline/), [CobraRTP downloads and manuals](https://cobrartp.com/en/downloads/), [MotronicRT R6 product](https://cobrartp.com/en/product/motronicrt/).

## 3. Other useful emulator, NVRAM and flashing patterns

### 3.1 Moates Ostrich 2.0 and EmUtility

The [Moates Ostrich 2.0](https://shop.moates.net/pages/ostrich-2-0) is an **8-bit** memory emulator supporting 24/28/32-pin ROM uses up to 4 Mbit (512 KiB), **not** a general 16-bit 28Fxxx emulator. Moates documents a 921,600 bit/s host connection and says most emulator upload/download/verify operations complete in **under two seconds**; this is a vendor product claim, *not* a speed measurement on a given ECU.

[EmUtility](https://shop.moates.net/pages/emutility-standalone-emulator-control) can use BIN/HEX files from editors and supports named Moates devices such as Ostrich 1/2 and APU1/RoadRunner. That provides a plausible **standalone vendor-tool bridge** without pretending the Editor has native hardware access. The exact emulator contents, start offset, bank layout and target chip remain critical.

### 3.2 NVRAM: persistence and live updates are independent

NVRAM may be an aftermarket calibration board, a battery-backed RAM emulator, a nonvolatile SRAM device or a manufacturer-specific architecture. It does not inherently mean the ECU or host offers live per-cell writes. A contributing adapter should prove the exact board revision, voltage, memory size/banks, write granularity, runtime synchronization, host link, readback, reset/power retention and valid update state. A live RAM write may *not* persist to the ECU's original flash; conversely a persistent NVRAM write might still require a paused ECU or reset.

Retain distinct capabilities: \`read_emulator_image\`, \`upload_emulator_image\`, \`write_calibration_ram\`, \`write_nvram\`, \`read_persistent_state\`. Never conflate confirmed host transmission with what is stored inside the device or acted upon by the ECU.

### 3.3 Bench flashing and burners

A *bench flasher* may still talk the same diagnostic programming protocol used in-vehicle, just with a stable external power supply and an ECU harness. A *boot-mode* tool may use a different, processor-specific interface. Neither is automatically faster. Some paths support calibration-only writes, some require a full erase/rewrite, and some may require the ECU to be opened.

A *chip burner/programmer* works on the chip, sometimes requiring removal/sockets/adapters and device-specific erase/program voltages. A 27C256 **UV-erasable EPROM** and a 24LC256 **electrically erasable EEPROM** do not share a generic write command; an OTP EPROM is not reusable after programming. In-circuit programming can be affected by ECU circuitry that drives the same pins. Back up, independently compare readback, respect chip geometry and handle invasive rework separately from BIN editing.

### 3.4 OBD/in-car flash is a programming operation, not continuous live calibration

A file tool should create a new image, prove its identity and checksum status, and hand off to an independently qualified flash utility. A J2534 interface provides **transport/API access**, not the vehicle-specific flash algorithm: the [SAE J2534-1 scope](https://saemobilus.sae.org/standards/j2534-1_5_00-recommended-practice-pass-thru-vehicle-programming) explicitly expects manufacturer reprogramming software. ECU program/erase/restart and readback are different from updating a table in host RAM.

## 4. How long does it take? Transfer theory versus the actual procedure

**There is no honest universal flash time.** File preparation may be fast, a supported memory emulator may update in seconds, and an OEM in-car programming session can take **minutes to tens of minutes**. **A ten-minute full write is entirely plausible**, especially for large images over slower links or tools with erase/verify/handshake overhead.

For a serial link with \`8N1\` framing, a minimum payload transmission time (not an end-to-end flash estimate) is:

\`T_payload_seconds = image_bytes * 10 / baud_bits_per_second\`

Each 8-bit data byte costs 10 line bits with start/stop. An \`8E1\` link uses **11 bits per byte** (start, 8 data, parity, stop). Protocol headers, echo, retries, security access, erase time, storage-program timings, checksum verification, readback, ignition cycles and software handshakes all add time.

**Idealized full-image serial payload only** (zero overhead, continuous link):

| Image size | 9,600 baud, 8N1 | 115,200 baud, 8N1 | 921,600 baud, 8N1 |
| --- | ---: | ---: | ---: |
| 32 KiB | 34.1 s | 2.8 s | 0.4 s |
| 128 KiB | 2 min 16.5 s | 11.4 s | 1.4 s |
| 512 KiB | 9 min 6.1 s | 45.5 s | 5.7 s |
| 1 MiB | 18 min 12.3 s | 1 min 31.0 s | 11.4 s |

At **9,600 baud / 8E1**, a **512 KiB** image already requires approximately **10 min 0.7 s** of theoretical payload time. An actual ECU flash over K-line/serial can take longer and may have much lower useful payload throughput. Equally, the 921,600-baud column is **not an Ostrich flash-time guarantee**: it is a hypothetical continuous serial link with a given framing, not an ECU/programmer benchmark.

CAN and CAN-FD bitrates **cannot be substituted directly** into that UART equation. Frame arbitration, addressing, segmentation, block acknowledgments, flash erase/program cycles, CPU pauses and tool behavior can dominate. USB speed or a vendor DLL's speed does not independently determine ECU internal programming throughput.

**Useful external anchors (not universal KingAI promises):**

- Toyota's **2016 Techstream ECU Flash Reprogramming Procedure** (T-SB-0134-16, page 17) says approximately **3–30 minutes per calibration file**, with CAN-equipped vehicles in that procedure often **2–7 minutes**. [OEM bulletin PDF](https://static.nhtsa.gov/odi/tsbs/2016/MC-10149217-9999.pdf).
- Moates documents **under two seconds for most Ostrich 2.0 ROM emulator operations**. [Moates source](https://shop.moates.net/pages/ostrich-2-0). That is **host-to-emulator** behavior, not an ECU flash.
- For a small standalone EEPROM chip, the [Microchip 24LC256 family](https://www.microchip.com/en-us/product/24lc256) is **32 KiB**, up to **64 bytes per page**, with a **5 ms maximum internal page-write cycle**. 512 pages × 5 ms = **2.56 seconds of maximum per-page internal write-cycle allowance**, *excluding* the bus transfer, tool setup and independent verification. It says nothing about a larger ECU NOR flash, nor about what a field programmer actually achieves.
- The Microchip [AT27C256R OTP EPROM](https://onlinedocs.microchip.com/oxy/GUID-D5A62023-1BAF-4D06-95AC-5BD61217B4D3-en-US-2/GUID-63A67F88-4ECD-449D-BB28-8B287696B976.html) documents a typical **100 μs/byte** programming algorithm. This is a chip-specific programming specification, *not* a complete programmer duration, and an OTP device is not erasable.

**KingAI future estimate model** (planning API, not an implemented ETA feature):

\`\`\`text
estimated_operation_time =
  handshake/session setup
  + target read/identity checks
  + erase / unlock / mode transition
  + transferred_payload_bytes / measured_effective_bytes_per_second
  + target program/settle waits
  + checksum/signature/readback verification
  + required resets / reinitialization
  + measured retry margin
\`\`\`

For user-facing times, label **measured hardware/tool/firmware revision data** separately from derived bit-rate lower bounds. A controller should expose a **measured progress state**, not pretend that a single baudrate determines a safe timeout. An unexpectedly lengthy write needs vendor procedure and recovery logic, not an agent-induced interruption.

### 4.1 Operator planning categories

| Workflow | Reasonable expectation to communicate | Evidence requirement |
| --- | --- | --- |
| Modify/export BIN on host | Usually computational file work, not a vehicle programming operation; measure actual tool performance | Input/output hashes and timing of file operation |
| Supported *calibration-only* emulator update | Potentially seconds after correctly loading full image; varies with device | Vendor documentation + actual adapter test, compare device readback |
| First full emulator image | Depends on chip capacity, device transport and vendor utility; may require ECU restart | Actual vendor test and full-image identity |
| Diagnostic CAN-based ECU flash | **Minutes**; Toyota gives 2–7 min in its specified procedure | Exact ECU, flasher, vehicle and interface-specific benchmark |
| Older serial/K-line or multi-stage full reprogram | **Several to 30+ minutes can be possible**; Toyota cites 3–30 min per file | Actual link, file size, protocol and OEM/tool instructions |
| Boot/bench programming | No defensible general timing; may be faster or slower than OBD | Tool + target measurements including verify |
| External EPROM/EEPROM/flash burning | Chip/algorithm-specific programming time plus remove/erase/verify/reinstall labor | Actual chip datasheet and programmer logs |

Never extrapolate the Toyota figures to every brand or claim the FlashOnline product can flash a 1 MiB ECU in the UART minimum time.

## 5. Fork this repo: a concrete adapter contribution walkthrough

**This is a process for developing a new adapter in your own fork.** It does **not** activate a plugin loader or bypass existing Editor write restrictions.

### Step 1: Fork, install and establish a baseline

Fork [KingAI CLI Map Editor](https://github.com/KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor) on GitHub, then on a Windows developer workstation with Python 3.10+ and Git:

\`\`\`powershell
git clone https://github.com/YOUR_GITHUB_NAME/tunerpro-xdf-bin-cli-map-editor.git
cd tunerpro-xdf-bin-cli-map-editor
git remote add upstream https://github.com/KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor.git
git switch -c feature/mock-your-hardware-name
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe cli_map_editor.py --help
\`\`\`

Run the documented read-only CLI \`preflight\` and \`list-maps\` against a synthetic or permissioned exact XDF/BIN pair. **Record actual outcomes**, including failures. The Editor pins an external Exporter source; installation therefore needs that dependency to be available. Check [README](../README.md), [AGENTS](../AGENTS.md) and any red CI rather than assuming all environments pass.

### Step 2: Write the target support declaration *before code*

In your fork, propose a file such as \`extensions/your_vendor/adapter.toml\` or equivalent versioned JSON containing:

\`\`\`toml
# PROPOSED metadata only; the public CLI does not parse this file.
adapter_id = "contributor.mock-eprom"
version = "0.1.0"
implementation_status = "simulation-only"
adapter_kind = "rom_emulator"
host_operating_system = ["windows"]
driver_abi = "not-applicable"
capabilities = ["probe_mock", "preview_upload"]
exact_hardware_revisions = []
exact_ecu_software_ids = []
image_sizes_bytes = []
licence = "MIT"
external_vendor_binary = false
\`\`\`

For real hardware, **required facts** include exact hardware/chip revision, bus width, voltage, memory capacity, bank/address mapping, vendor firmware/driver version, host architecture, supported operating mode, independently read device identity, permitted target software layout, start/end/data granularity and readback semantics. Empty support lists mean **no hardware qualified**, not “all hardware accepted.”

### Step 3: Build a *no-hardware* reference adapter and proof

The first commit can implement \`probe_mock()\`, \`preview_upload()\` and a structured refusal for unsupported operations. For example, a **standalone illustrative helper**, **not** a plugin entry point provided by the current Editor:

\`\`\`python
# extensions/your_vendor/mock_adapter.py -- conceptual standalone example
from pathlib import Path
import hashlib

class UnsupportedHardwareOperation(RuntimeError):
    pass

def preview_upload(path: Path, expected_sha256: str, exact_image_size: int):
    payload = path.read_bytes()  # mock review only, no device connection
    measured = hashlib.sha256(payload).hexdigest()
    if measured != expected_sha256:
        raise ValueError("Source BIN hash differs from the reviewed input")
    if len(payload) != exact_image_size:
        raise ValueError("Wrong image size for this exact device profile")
    return {
        "status": "simulated_only",
        "can_write_hardware": False,
        "image_sha256": measured,
        "byte_length": len(payload),
    }

def flash(*args, **kwargs):
    raise UnsupportedHardwareOperation("No qualified hardware writer registered")
\`\`\`

Add tests for correct/wrong hash, correct/wrong size, missing file, duplicate devices, unsupported chip width, unavailable driver, truncated image, denied operation, loss of link and inconclusive readback. A mock's simulated “success” is only a test that the host program made the expected decision.

### Step 4: Choose ONE external interface strategy

| Available asset | Preferred contribution path | What is explicitly **not** acceptable |
| --- | --- | --- |
| Licensed Python checksum code | Pure Python verifier/repair **to new copy** with independent golden vectors | Importing arbitrary code supplied inside the edit plan |
| Named external flasher executable | Local **allowlisted executable** with typed argument-vector inputs, dry-run first, version and identity capture | Shell-string interpolation or unverified unattended program/erase commands |
| J2534 interface with installed vendor DLL | Windows J2534 driver discovery and **read-only** transport probe first; protocol separately | Calling the J2534 DLL as if it were a universal flash algorithm |
| TunerPro RT plugin/checksum DLL | Use the supported **TunerPro host** or independently documented SDK/ABI under appropriate licence | Guessing exported function addresses or calling an unknown DLL via \`ctypes\` |
| FlashOnline/MotronicRT/Ostrich | Supported utility-hosted handoff or documented manufacturer API, mock file watcher first | Claiming a BIN-save event automatically means the ECU changed |
| Chip burner/programmer | Manufacturer-supported chip/programmer CLI, independent chip-ID and verify receipts | Guessing erase voltage, package pinout or chip command sequences |
| Vendor software with private definition/IP | Named, authorized semantic API/SDK, if the provider offers one | Scraping/exporting proprietary definitions or circumventing licence/authorization |

For **J2534**, Opus IVS documents discovery through vendor registry entries such as \`PassThruSupport.04.04\` and a per-device \`FunctionLibrary\`; confirm current DLL API/bitness and handle multi-device enumeration. A J2534 DLL is **not the same ABI** as a TunerPro data-acquisition/emulation/checksum plugin. [Official vendor example](https://opusivs-au.com/support/oem-customer-support/how-to-program-with-opus-ivss-passthru-sae-j2534-dll/discovery-of-the-dll/).

For DLLs from external tools, retain their binary, licence and installation **outside the MIT repository** unless redistribution is clearly permitted. Prefer a deliberately configured **local child process** for native/vendor code so errors, architecture, output and privilege can be monitored independently. Separate process isolation does not make ECU commands physically safe.

### Step 5: Implement the adapter tests and a reference receipt

A documented mock/driver contract should eventually include:

\`\`\`text
identify_adapter -> id, version, binary hash, vendor, licence
probe_device(read_only=True) -> exact device identity, firmware, capabilities
verify_candidate_image(image_sha256, target_identity) -> eligible | refusal
preview_handoff -> intended byte count, strategy, expected result, dry_run=true
execute_supervised_handoff -> only when exact adapter/target/operation qualified
verify_destination -> verified | mismatch | inconclusive | unsupported
safe_stop/recovery -> recorded outcome; never presume an interrupted flash succeeded
\`\`\`

A device operation receipt must distinguish \`file_created\`, \`image_validated\`, \`transfer_started\`, \`device_reported_success\`, \`independent_readback_verified\`, and \`physical_effect_validated\`. These are not equivalent. Report **actual elapsed time**, byte count and *effective measured throughput* only when observed.

Retain original BIN/XDF and all evidence. Do not promote a checksum verifier into a repair function without exact checksum-storage offsets, dependency order, golden repaired images and an independent full-image diff. Existing [MS42/MS43/VY checksum verifiers](../raw_patch_checksum_profiles.py) are useful **read-only examples** but are not a general chip-burning plugin system.

### Step 6: Keep the CLI canonical; GUI and MCP are future clients

**One execution rule:** CLI, agent tool and any future **single-script PySide6/Qt GUI** must use the **same deterministic command registry and validation engine**. A GUI should be an optional client, not a second write implementation or another permission boundary. An agent can keep using CLI arguments even if a user later prefers buttons.

**ChatGPTz idea 💡 (proposed):** a typed \`CommandSpec\` / argument registry describing names, types, defaults, units, safety class, help text, supported capabilities, and result schema; generate \`--help\`, contributor/agent guides, JSON tools and eventual Qt forms from it. **This registry is not in today's released CLI**, and no existing command gains new arguments from the examples here. The idea is motivated by avoiding drift across CLI help, \`AGENTS.md\`, MCP and GUIs.

In future, a GUI may translate clicks to validated command args or call the same internal handler. If a GUI button can perform something the CLI/API cannot express, the interfaces have diverged and should be reconciled. Do **not** use a GUI to bypass any write guard.

### Step 7: Raise a targeted pull request

Submit **one adapter/protocol and one reviewable milestone** per PR. Include:

- Public provenance, licence, and exact **supported** devices/chips/software versions, supported host OS/bitness.
- Synthetic fixtures with success/negative outcomes; optional private exact-target tests reported using hash-only evidence.
- Dependency lock/version, no bundled private DLL or ECU image, no VIN/credentials/secret commands.
- Explicit read-only / mock / verified-in-host / bench-tested / vehicle-qualified labels.
- A command usage example that is **really implemented**, not hypothetical syntax from this guide.
- Source image hash, plan identity where applicable, full diff/receipt and observed device outcome without claiming physical safety.
- Failure policy for interruptions, target mismatch, missing hardware, wrong bank/voltage, checksum unknown, incomplete verification.

See [CONTRIBUTING.md](../CONTRIBUTING.md) for expectations. A README/roadmap PR is welcome too; do not mark a proposed adapter as shipping.

## 6. Boundaries and threat model: professional use, AI and platform APIs

### 6.1 Human-directed editing ≠ autonomous ECU programming

The user's clearly scoped request can authorize a supported **local file** edit without repeated per-cell confirmation. A device-side calibration upload, erase or physical flash is a separate action with a named target, eligible mode, operator control and recovery procedure. “I own a J2534 adapter” or “I am a professional” is **not enough** to infer a write-safe ECU strategy.

The MIT licence does not impose a legal *professionals-only use restriction*; the project may accurately state “**intended for experienced, qualified users**,” document risks and decline unqualified functionality. Do not promise that a connected adapter “will have no dramas.”

### 6.2 Future partner API: semantic handles protect definition IP

**For a partner's proprietary, server-owned definition database**, agent-visible plans can use a stable, version-scoped **semantic handle**, row/column and engineering-unit target instead of exposing raw memory addresses:

\`\`\`text
agent sees:  vendor-approved map_handle + row/col + units + requested value
server owns: handle -> verified definition/address/memory mapping -> byte writer
agent gets:  change receipt with map/value, opaque image/plan identity and status
vendor retains: full private byte/offset audit and underlying definitions
\`\`\`

This is **not** how the public Editor currently hides data: users of the public XDF/BIN CLI have local definitions and full raw byte diffs. An externally returned full byte/offset receipt would disclose those offsets; a private partner would need a deliberate **redacted external receipt plus internally retained full audit**. Never claim both complete public raw offsets and secret address maps simultaneously.

A semantic-handle API reduces unstructured GUI automation but cannot prevent users from operating an unrelated GUI. Proper authorization, rate limits, capability allowlists, independent validation and auditing remain essential. A **signed plan and approval token** can be a future security feature with authentic key ownership and a replay policy; **the public Editor does not presently implement a trusted signing/authentication service**. Its current hashes prove file identity/integrity, not the operator's identity.

### 6.3 Network MCP is a security feature only if engineered

Do not connect an unprotected remotely callable MCP tool directly to a flasher, key/seed service or device write path. A future service needs authentication, narrowly scoped capabilities, binding to local adapters, replay protection, operation/target allowlists, audit logs, redaction, time-limited operator authorization, safe abort/recovery and privilege separation. Start with **read-only** MCP; separate any hardware writer into a specifically enabled local worker. A structured endpoint is not inherently secure just because a GUI mouse is less reliable.

## 7. Recommended implementation path, not a release claim

1. Complete independent qualification of [draft transactional PR #10](https://github.com/KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor/pull/10) and resolve current CI failures, then keep its typed file-edit plan the sole write-to-BIN path.
2. Publish a **mock adapter SDK + dry-run capability explorer** and exact image/receipt schema without connecting to hardware.
3. Implement one narrow checksum **verify + repair-copy + independent verify** on exact licensed golden fixtures; distinguish checksum status from flash eligibility.
4. Add a vendor-utility file-handoff test for **FlashOnline/CobraRTP Utility or Ostrich/EmUtility**, first in a filesystem simulator with no ECU, then only with device-specific evidence.
5. Add a **read-only J2534 driver discovery and transport** proposal with a validated Windows DLL ABI; do not claim to ship a universal flasher.
6. Where available and lawfully documented, contribute a qualified external flasher integration as a **separate PR**, requiring actual bench and recovery validation.
7. Future optional single-script PySide6 frontend, typed CLI argument registry and read-only MCP server may share the same engine. No alternate path to raw bytes or hardware writes.

**No fixed delivery dates or “works with any ECU” guarantees are implied.**

## References and provenance

1. [CobraRTP FlashOnline R4 product, supported memory, checksums, FAQ](https://cobrartp.com/en/product/flashonline/)
2. [CobraRTP official downloads and manuals](https://cobrartp.com/en/downloads/)
3. [CobraRTP MotronicRT product](https://cobrartp.com/en/product/motronicrt/)
4. [Moates Ostrich 2.0 capabilities and ROM geometry](https://shop.moates.net/pages/ostrich-2-0)
5. [Moates EmUtility standalone emulator control](https://shop.moates.net/pages/emutility-standalone-emulator-control)
6. [SAE J2534-1 programming interface scope](https://saemobilus.sae.org/standards/j2534-1_5_00-recommended-practice-pass-thru-vehicle-programming)
7. [Opus IVS J2534 DLL discovery and protocol declaration](https://opusivs-au.com/support/oem-customer-support/how-to-program-with-opus-ivss-passthru-sae-j2534-dll/discovery-of-the-dll/)
8. [Toyota Techstream ECU flash bulletin T-SB-0134-16, p.17 (2016)](https://static.nhtsa.gov/odi/tsbs/2016/MC-10149217-9999.pdf)
9. [Microchip 24LC256 32 KiB EEPROM](https://www.microchip.com/en-us/product/24lc256)
10. [Microchip AT27C256R OTP EPROM programming specification](https://onlinedocs.microchip.com/oxy/GUID-D5A62023-1BAF-4D06-95AC-5BD61217B4D3-en-US-2/GUID-63A67F88-4ECD-449D-BB28-8B287696B976.html)
11. [KingAI existing hardware/checksum adapter roadmap](HARDWARE_CHECKSUM_FLASH_PLUGIN_ROADMAP.md)
12. [KingAI public adapter contribution requirements](../CONTRIBUTING.md)

**Source classification:** manufacturer statements remain vendor claims; Toyota figures are specific to that OEM's documented programming procedure; serial timing table is an explicitly **calculated lower bound**, not a measured result; example code and future contracts are **proposals only**. No hardware/DLL/ECU tests were performed for this documentation. Do not infer that any device listed here works with a particular KingAI-owned ECU from this document alone.

**ChatGPTz idea 💡:** typed command-argument registry, semantic partner API boundary and public-safe adapter capability/receipt templates are AI-originated architecture proposals inspired by the existing CLI/Exporter separation, immutable edit receipts and external vendor tool patterns; none are represented as user-authored shipped code.
