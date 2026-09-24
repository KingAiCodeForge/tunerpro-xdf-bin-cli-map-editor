# BMW MS42, MS43 and MS43X AI Tuning Guide

**Updated:** 20 September 2026
**Scope:** BMW MS42, stock MS43 and MS43X XDF+BIN work through `cli_map_editor.py`
**Status:** evidence-gated offline editing; screenshots are reference material

MS42, stock MS43 and MS43X are separate calibration/code targets. Similar
Siemens names describe related concepts, but addresses, axes, equations,
configuration semantics, patches and runtime logging operands are not portable
by appearance alone.

## Evidence contract

Use these labels in every AI response:

| Label | Meaning |
|---|---|
| `REFERENCE_ONLY` | screenshot, post, filename, tune label or unmatched definition |
| `CLI_CHECKED` | exact OSID/layout and BIN/XDF hashes recorded; CLI export, raw diff and write round-trip agree; native parity is still due |
| `STATIC_PROVED` | `CLI_CHECKED` plus retained native TunerPro display/write parity for the exact XDF structures and edited parameter form |
| `VEHICLE_TESTED` | named artifact has a retained readback and log from the exact vehicle/hardware |
| `DYNO_VALIDATED` | retained before/after runs support the stated result |
| `FLASH_READY` | exact DME match, checksum/signature, write/readback and recovery are all proved |

Apply `LEGACY_REBUILD_REQUIRED` to existing MS43/MS43X patches and formulas
that predate the latest disassembly and tracing. Keep their hashes and diffs as
provenance, then regenerate each hook, payload and equation from the exact
clean parent instead of copying the former bytes.

The owner's aggressive-throttle and ghost-cam experiments have been reported
as working in the car. That is valuable behavioural evidence, but it does not
promote every similarly named file: some retained full-image lineages contain
known damaged code bytes. Vehicle-tested behaviour must be tied to the exact
artifact hash and readback before reuse.

For the narrow `0110C6` ghost-cam family, the exact full-image exclusions are:

- SHA-256 `F6E6B2DCC1D36BD5657B519FFC86D0F4F7CBEA656DAB69465271C3958675F0C4`
  contains the intended 84 calibration bytes but also inherits a broken C166
  `CALLS` first half at file offsets `0x709AE-0x709AF`;
- SHA-256 `A2305997E204E71D6D10478055871049B82A439CE1A8532485678B5FE11FD3DD`
  inherits that code fault and adds 108 writes exactly `0x48000` below the
  intended map bodies; and
- the retained patch-test image has the 108 misplaced writes but none of the
  intended calibration change.

All three are `DO_NOT_FLASH` and must not be used as full-image donors. A clean
reconstruction may use the five named-map values as reference data, but must
apply them through the matching XDF to the independently clean stock parent,
then prove that no program byte or unexplained calibration byte changed. The
owner's in-car observation remains unassigned until its actual post-flash or
readback hash is recovered.

## Required identity before any edit

```yaml
ecu: "MS42 | MS43 | MS43X"
osid: "exact value, for example 0110C6 or 430069"
engine: "M52TUB20/B25/B28 or M54B22/B25/B30"
chassis_and_market: "E46/E39/etc, LHD/RHD, EU2/EU3/EU4/US"
transmission: "exact manual/automatic"
emissions_hardware: "SAP, catalysts and pre/post-cat sensor configuration"
intake_hardware: "MAF, manifold, throttle body, cams, injectors"
base_bin:
  path: "exact path"
  layout: "512 KiB full or proved calibration-only layout"
  sha256: "64 hex characters"
xdf:
  path: "exact path"
  sha256: "64 hex characters"
requested_effect: "one effect only"
```

Rules:

- `0110C6`, `0110CA`, `430069` and `MS43X001` are not synonyms.
- Match full/partial layout as well as OSID. Never repair a missing boot/code
  area by grafting from an unidentified read.
- Match engine displacement and hardware. A B25/B28/B30 calibration is not a
  generic stage level.
- EU2/EU3/EU4 is a configuration/hardware distinction, not a performance
  stage. Confirm SAP, O2/catalyst configuration, MAF and diagnostics separately.
- A stock-MS43 patchlist and MS43X custom firmware do not share a universal
  patch/data contract. Never port code patches with the CLI `port` command.

## What the basic-tuning screenshots actually prove

The imported photo set contains two explicit warnings: improper use or
transcription can set a car on fire, and RPM scaling must be checked. Keep
those warnings attached to every derivative.

The hashes below identify the reviewed images. The evidence is limited to what
was visibly open in TunerPro; no screenshot contains a complete BIN identity,
checksum, log, readback or dyno result.

| Source image (SHA-256 prefix) | Visible evidence | Correct interpretation |
|---|---|---|
| `ghost cam.png` (`06853fdf89fa`) | idle intake/exhaust cam targets, idle ignition correction and normal/A-C idle-speed tables; warm rows visibly show 850 rpm | a multi-map idle-torque hypothesis; not proof of OSID, safe cam units or power gain |
| `basic pops and bangs with ac - cruise control.png` (`52f75178c3b8`) | normal and A/C overrun RPM gates plus normal/A-C overrun ignition min/max tables | shows how an accessory-conditioned path may differ; does not prove the selector logic or safe temperatures |
| `MS42 Launch Control Settings.png` (`c55f18f82e47`) | LC speed, pedal, RPM, temperature and ignition-retard-related scalars | patch/configuration reference only; patch version and active code are missing |
| `MS42 Aggressive Hardcut 6000 rpm.png` (`3d2f3c8e4532`) | limiter/hysteresis controls and an added high-RPM ignition row | high-risk recipe; visible labels alone do not prove the final limiter path, dwell/cut behaviour or RPM scaling |
| `ms42 disa hack for a little more peak power.png` (`97ea11a9bb83`) | `id_vim_fl_n_vim` and `id_vim_pl_n_vim_maf` switch tables | identifies DISA transition candidates; `1/0` physical flap meaning and torque result still require code/log/dyno proof |
| `MS43 2-step using hardcut.png` (`07e5aa078a57`) | gear limiters, hysteresis and LC/RAL scalars | a combined limiter/patch recipe, not a normal calibration-only stage tune |
| `MS43 Aggressive 2-step and Launch Control together.png` (`534c78ea62f4`) | the above plus an injection-time row near the activation speed | deliberately combines several effects; fuel/EGT/catalyst risk cannot be inferred from the picture |
| `MS43 aggressive hardcut 6500 rpm.png` (`ff3e54655194`) | high/low-octane ignition and injection rows added around 6450-6480 rpm plus gear limits | shows a boundary-row technique; no evidence of combustion safety, checksum or vehicle result |
| `ms43 quick throttle response and pops between shifts.png` (`68d0b8fa93c7`) | deceleration-time tables, recovery/hysteresis scalars, gear request values and a torque/request table | a combined response/overrun payload; zero/full-scale values require exact code-use proof before interpretation |
| `Torch tune.png` (`a565c93399cd`) | injection, throttle request and heavily retarded overrun ignition tables | extreme exhaust-effect reference; not a safe recipe and not suitable with catalysts |
| `MS43X001 Aggressive Hardcut.png` (`8fa7c4ca6eaa`) | MS43X limiter enable/hysteresis, gear limits and a retarded boundary row | MS43X-only hypothesis; do not apply to stock `430069` |
| `MS43X001 LC_RAL_NLS basic settings.png` (`f51599de409a`) | separate NLS, RAL and LC enable/threshold/AF/ignition controls | proves the definition exposes these controls; sentinel-looking compare values mean the exact source BIN/XDF is mandatory |
| `updating to ms43 v69 software version.png` (`7e2ccf8c4614`) | a 2021 recommendation to full-write an untouched matching `v0069`, full-read it, modify that read, then full-write | useful lineage discipline, but tool/version, voltage, recovery and current official procedure still need verification |

Several MS43 screenshots visibly use an MS43 definition while the compare title
references an MS42 `0110C...` file. Therefore colour and compare values in those
captures cannot be treated as a valid MS42-to-MS43 tune diff.

## Commands that exist today

Audit first:

```powershell
python cli_map_editor.py preflight --xdf <exact.xdf> --bin <parent.bin>
python cli_map_editor.py export --xdf <exact.xdf> --bin <parent.bin> --output-dir <audit-dir>
python cli_map_editor.py list-maps --xdf <exact.xdf> --bin <parent.bin>
python cli_map_editor.py show-map --xdf <exact.xdf> --bin <parent.bin> --map "<exact table title>"
python cli_map_editor.py show-scalar --xdf <exact.xdf> --bin <parent.bin> --name "<exact scalar title>"
```

After human approval, create one bounded candidate and verify it:

```powershell
python cli_map_editor.py edit --xdf <exact.xdf> --bin <parent.bin> --map "<exact table title>" --rows <1-based rows> --cols <1-based cols> --value <approved value> --save --output-dir <candidate-dir>
python cli_map_editor.py diff --bin-a <parent.bin> --bin-b <candidate.bin>
python cli_map_editor.py preflight --xdf <exact.xdf> --bin <candidate.bin>
python cli_map_editor.py export --xdf <exact.xdf> --bin <candidate.bin> --output-dir <candidate-audit-dir>
```

The current CLI has no ADX ingestion, checksum repair, RSA signing or flasher.
`preflight` cannot establish flash readiness.

### XDF edit or direct binary patch?

Use XDF tables/scalars for proved calibration data. `XDFPATCH` entries can
describe base and replacement bytes, but the current CLI reports their status
and does not yet expose a proved apply-patch command. Use a hash- and
expected-byte-gated direct patch manifest for exact-version code work such as
MS43X hooks. The manifest must identify the OS/full-image layout, file-offset
address basis, disassembly context, original and replacement bytes, code-cave
ownership, checksum/signature coverage and reverse patch. Refuse it on any
mismatch; never run code patches through `port`.

## Effect experiments suitable for an AI proposal

### 1. Throttle-response candidate

Goal: change requested throttle/torque shape, not claim extra engine power.

Method:

1. Identify the exact warm/cold and mode/gear request maps in the target XDF.
2. Export the stock surfaces and the exact known in-car-tested artifact.
3. Diff in engineering and raw units; reject unexplained code/config changes.
4. Propose a smooth, monotonic intermediate surface, preserving closed-pedal,
   full-pedal and cold/fault behaviour.
5. Log pedal request, commanded and actual throttle, load/torque intervention,
   RPM, gear, lambda and knock.

Success is a repeatable reduction in pedal-to-throttle delay with no oscillation,
surge, plausibility fault or unintended full-throttle request. This can be a
good first CLI-generated test because it can remain separate from fuel/spark.

The current bounded `0110C6` B28 EU3 reconstruction follows this method. It
ports only `ip_tps_sp_pvs_tco_1__pvs__n` and
`ip_tps_sp_pvs_tco_2__pvs__n` from the owner-linked source onto clean parent
SHA-256
`65C3B91A05A0D6AE40F82E39F327FDC2FF672F9B61E2C3233780535E44539F90`.
The result changes 416 bytes inside the two 288-byte map bodies; both output
bodies have SHA-256
`9FDA5433BFBA7DDAAC9F0D935662E1579DF0099B38F1B91F603F965B78E90889`,
axes stay stock and the clean `DA 06 82 08` code sentinel at `0x709AE` is
preserved. The pre-checksum CLI output is
`8EEB90CB61FE9373C338FEE17686AE272AA22F2E8E0BE5FA6631B24AAF877B49`.
Exact 0110C6 CAL-CRC repair changes only `0x4FEE0..0x4FEE1`, giving final
SHA-256 `BABE46932DEA70FE7796E7441F2C176CC9D009DCA17F3249098CE46AD488E4A6`
and 418 total parent differences. All three stored CRCs then verify. This is
`STATIC_PROVED`, not flash approval: it remains an aggressive EU3 request-map
experiment and still needs native TunerPro parity, exact-DME matching,
recovery, write/readback and logged vehicle tests.

### 2. Mild ghost-cam/idle-effect candidate

The screenshot evidence shows that the observed effect was not just an idle
RPM change: idle setpoints, intake/exhaust cam targets and idle-speed ignition
correction were changed together. That explains why files which only raise
idle speed should not be called ghost-cam tunes.

Build a mild candidate as a separate layer against one exact stock parent.
Limit changes to proved warm-idle cells, preserve cold start and an exit above
idle/load, and do not touch the main part-load ignition or fuel maps. Log target
and actual RPM, intake/exhaust target and actual angle, idle controller,
ignition, lambda, misfire/roughness, coolant and A/C/load state.

Success requires hot/cold restart, no stalls, stable oil pressure, acceptable
lambda/misfire behaviour and clean transition out of idle. A sound change is
not a dyno gain.

For `0110C6` B28 EU3 the current clean comparison parent is SHA-256
`65C3B91A05A0D6AE40F82E39F327FDC2FF672F9B61E2C3233780535E44539F90`.
Use the exact five-map reconstruction as a forensic parity target first; make
any milder blend as a separate candidate, never by editing one of the damaged
F6/A230 full images. This does not make the reconstructed file flash-ready:
checksum correction, native TunerPro visual review, vehicle identity,
read/write/recovery and logged tests remain separate gates.

There is an additional unresolved parity issue: the reviewed TunerPro image
shows negative idle-ignition correction values and different error-axis
breakpoints in several columns, while the current local F6/A230 body retains
the stock axis and the CLI export interprets raw bytes `C9/BD/...` as positive
values. The 84-byte raw reconstruction is therefore held for forensic review;
it is not the first test candidate until native TunerPro signedness and axis
parity are resolved.

### 3. DISA transition experiment

The photo identifies two switch tables, but not whether `0` or `1` means the
same physical flap state under every condition. Prove code use or log commanded
and actual DISA state first. Then move one boundary region at a time and compare
repeatable torque data. A dyno is required for a peak-power claim.

### 4. EU2 configuration conversion

Treat this as a stock-variant reconstruction, not a stage tune. Use a factory
EU2 and factory EU3 calibration with the same OSID and engine/hardware wherever
possible. Diff configuration, diagnostic thresholds, MAF and all other changed
regions separately. Do not assume every non-stock file is catless, and do not
silence a DTC without recording the physical hardware and legal purpose.

For `0110C6` or `0110CA`, an AI request must name the exact factory donor and
parent hashes. If an original full read has damaged/leaped offsets, quarantine
it; do not use copy/paste to make a new full image.

### 5. Engine-size or chassis port

Same OSID is necessary but not sufficient. Compare B25/B28/B30 injector data,
MAF transfer, displacement/load model, VANOS, torque/throttle, idle, limiters,
exhaust-temperature/catalyst model, transmission and market configuration.
Classify every target as exact-copy, resample candidate or manual/code review.
The CLI `port` command is a byte-producing tool, not an authority that similarly
named maps are physically equivalent.

### 6. Ignition/dyno experiment

Preserve the low-octane/fallback path. Never copy RON98 over RON91 merely to
prevent fallback. Begin from the correct stock engine and fuel, make a bounded
proposal only in repeatedly logged cells, and require knock/temperature/lambda
logs. A dyno or controlled repeatable acceleration test is needed to distinguish
real torque from noise and adaptation.

### 7. Rev limiter, launch control, NLS and RAL

These features depend on final scheduling code, activation logic and patch
version, not just visible scalars. Keep enable, speed/pedal/temp gates, cut
threshold, hysteresis and recovery coherent. Require timeout, fault abort and
safe restoration. Do not implement hardcut by globally zeroing coil dwell.

Start ASM work with a harmless, observable patch on the exact OS, bench-read it
back, and prove checksum/recovery before modifying ignition or injection
scheduling. A screenshot is not enough to assemble a patch.

The preferred first ASM proof is the `0110C6` DS2 Logging Feature Enhancement,
not a hardcut, launch or combustion patch. Its strict manifest, extracted from
community patchlist v1.7.1, declares a hook at `0x20950-0x20955` changing
`DA 01 26 D2 0D 02` to `FA 06 00 0E CC 00`, program-CRC bytes at
`0x50306-0x50307` changing `47 F3` to `88 AF`, logger part 1 at
`0x60E00-0x60EFF` (256 bytes), and logger part 2 at `0x60F00-0x60FC7`
(200 declared bytes, 198 actual changes). The manifest is bound to clean parent
SHA-256 `65C3B91A05A0D6AE40F82E39F327FDC2FF672F9B61E2C3233780535E44539F90`
and produces final SHA-256
`AF72CCEB84CF12D75A8791051A43BCE00F4CC33447ECF51C3B1B2625810ED9DD`.
The strict-v2 manifest SHA-256 is
`94CE827E565747F5E559646D8D5AC8D60CBF63CD6BCC7D4F333048E23C24C579`;
its trusted-profile forward and reverse canonical-evidence SHA-256 values are
`2E4AC373CF1D25596B2E2883DF9DDE68E8A0A29B8AFDD1F8D174775463D204F3`
and `D4DB8B5CD5CCBF61468748F633670757818D8DB0EF62AB8A9F9AD21406033EE0`.
The output has exactly 462 actual changed bytes, no changes outside the four
declared ranges, and valid boot, CAL and program checksums. Reverse application
restores the exact clean-parent SHA-256.

The hook is covered by the ECU program CRC, but the logger payload at
`0x60E00-0x60FC7` is outside ECU program-CRC coverage. A valid program CRC
therefore does not authenticate the payload. Require the complete final-image
SHA-256 and a matching physical readback before executing it. This is
`STATIC_PROVED / BENCH_NEXT`, not approved for an on-car flash.

First bench proof should be one manual 9600-baud transaction: send the complete
DS2 frame `12 05 0B B0 AC`, verify the `12 49 A0` reply framing, length/XOR and
plausible values, and compare an unpatched clean DME as a negative control. Do
not initially combine the separate baud-bypass or speed increase patches. The
matching M52TUB28 ADX currently has SHA-256
`2BFE535BB6CC9E628B6ED740CC355794CBED1E3EF1DEA46D460CB8446F7C8B46`.
That ADX automatically switches to 125000 baud, so treat it as a later
high-speed reference rather than the first manual proof; do not combine its
baud behavior or any separate speed patch in this test. Physical DME readback,
request/reply trace, recovery proof and repeated power-cycle behavior remain
open bench gates.

### 8. Overrun sound / A-C or cruise selector

Normal, A/C and cruise-selected behaviour must be traced to the actual code or
official patchlist for that OS. Do not assume an A/C-labelled table is selected
by the A/C button under all conditions. Retarded combustion with retained fuel
can overheat exhaust valves, manifolds, turbos and catalysts and can dilute oil.
Keep this as a separate, explicitly selected experiment; never produce a
`cat-destruction` calibration.

### 9. MS43X boost/flex/MAFless work

MS43X is custom firmware. First prove the exact MS43X release, definition and
stock base. Generated local MS43X turbo files labelled `DO_NOT_FLASH_UNCHECKED`
remain evidence-only. A boost candidate additionally needs sensor transfer,
injector characterization, fuel-pressure/duty margin, load/torque model,
overboost and lambda/knock/temperature aborts. Do not infer those from the two
MS43X screenshots.

## XDF versus ADX rule

An XDF map address is calibration storage. An ADX item may use a RAM address,
diagnostic identifier, packet offset and equation. They are not interchangeable.
MS42/MS43 DS2 and MS43X logging must use the exact firmware/logger/patch
contract. An ADX that merely parses and fits a packet is
`ADX_DEFINITION_CHECKED`, not `STATIC_PROVED`. Runtime proof requires an
on-car request/response and decoded-value comparison against an independent
measurement or known state.

## Copy/paste AI requests

### Audit a BMW tune without editing

```text
Audit this BMW BIN without editing it. Record BIN/XDF SHA-256, byte count,
full/partial layout, exact OSID, engine size, chassis/market, transmission and
emissions/intake hardware. Find the exact stock parent with the same OSID and
engine. Run preflight and export both, then group raw changed bytes by XDF
parameter and code/config/checksum region. Explain the likely cause and effect
of every named change, list every unexplained byte and grade the evidence.
Do not trust the tune filename or call it flash-ready/dyno-proven.
```

### Build a separate mild throttle candidate

```text
From this exact stock BMW parent and exact matching XDF, compare the owner's
named in-car-tested aggressive-throttle artifact. Propose a mild intermediate
throttle-request surface only; preserve monotonicity, closed/full pedal, cold
and fault behaviour. Show current and proposed engineering/raw values first.
After approval, edit a copy with cli_map_editor.py, diff and export it, and stop
if any byte outside the approved request maps changes. Produce required logging
channels and pass/fail tests. Do not alter fuel, ignition, VANOS, emissions or
limiters and do not flash.
```

### Build a separate mild idle-effect candidate

```text
Using the exact BMW parent/XDF and the reviewed ghost-cam screenshot only as a
map-discovery reference, identify the proved idle-speed, idle VANOS and idle
ignition-correction maps in this OS. Compare them with the exact owner-tested
artifact if its hash is available. Propose a mild warm-idle-only layer with a
clear exit above idle/load and no main fuel/spark changes. Show the proposal,
then create a copied candidate only after approval. Diff/export it and provide
hot/cold restart, cam tracking, lambda, misfire, stall and transition tests.
```

### Design an ASM patch without emitting road code

```text
For this exact OS/full-image hash, map the requested behaviour through
disassembly: inputs, final actuator scheduling path, existing limiter/fault
logic, free code/data space, calls and checksum-covered ranges. Produce a patch
design with pseudocode, hook proof, register/stack preservation, timeout,
hysteresis, fault abort, restoration and bench tests. First implement only a
harmless observable test patch. Do not emit or call an ignition/fuel-cut patch
vehicle-ready until bench execution, checksum, readback and recovery are proved.
```

### Rebuild a legacy MS43/MS43X patch

```text
Treat the named MS43/MS43X patch as LEGACY_REBUILD_REQUIRED. Starting from the
exact clean full-image hash and newest disassembly/call/RAM traces, re-identify
the hook, callers, final scheduling path, code cave, registers, stack and
checksum-covered ranges. Re-derive any XDF equations from raw storage and code
use. Generate new expected/replacement/reverse bytes and compare them with the
old patch, explaining every difference. Do not reuse an old opcode sequence,
sentinel or conversion constant unless the current trace independently proves
it. Emit a review-only manifest and bench plan before any vehicle candidate.
```

## Required hand-off receipt

Every candidate needs:

- parent/candidate/XDF SHA-256 and file sizes;
- exact ECU, OSID, layout, engine, chassis/market and transmission;
- hardware/configuration manifest;
- parameter names, addresses, axes, units and old/new raw/engineering values;
- complete changed-byte ranges and unexplained-byte count;
- CLI preflight/export/diff result and native TunerPro visual check still due;
- checksum/signature, write/readback and recovery status;
- required log channels, test conditions, aborts and rollback file;
- evidence grade, never higher than `CLI_CHECKED` while native TunerPro parity
  remains due and never higher than `STATIC_PROVED` before physical validation.
