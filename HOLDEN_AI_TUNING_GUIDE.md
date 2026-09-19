# Holden AI Tuning Guide

**Updated:** 20 September 2026
**Scope:** Holden/Delco XDF+BIN work driven through `cli_map_editor.py`
**Status:** evidence-gated offline editing; not an automatic tuner or flasher

This guide is intentionally separate from the BMW guide. A Holden table name,
equation, packet offset, checksum and tuning method must not be inferred from
an MS42/MS43 screenshot or copied from another Delco operating system.

## What is proved and what is not

Use these evidence labels in every AI response:

| Label | Minimum evidence | What it permits |
|---|---|---|
| `REFERENCE_ONLY` | screenshot, forum post, filename or unpaired tune | locate candidates and design checks only |
| `CLI_CHECKED` | exact BIN/XDF hashes and OS identity plus CLI export, raw-byte diff and write round-trip; native parity still due | review the proposed bytes only |
| `STATIC_PROVED` | `CLI_CHECKED` plus retained native TunerPro display/write parity for the exact parameter form | bounded offline edit proposal |
| `VEHICLE_TESTED` | `STATIC_PROVED` plus named readback and retained log from the same vehicle | repeat the tested configuration on that exact setup |
| `DYNO_VALIDATED` | `VEHICLE_TESTED` plus retained before/after runs and conditions | make the measured claim only |
| `FLASH_READY` | exact ECU match, checksum/signature, write/readback and recovery path all proved | human may decide to flash |

Apply `LEGACY_REBUILD_REQUIRED` to every existing VY ASM/XDF patch whose bytes
or formulas predate the latest disassembly and tracing. Retain it for
comparison, then regenerate the hook, payload and equations from the exact
clean parent; do not promote an older R-number merely because it is newer.

`preflight` proves only the XDF structures implemented by this project fit
inside the supplied file. It does not identify the PCM, validate a tune, repair
a checksum or make a file flash-ready.

## Keep the Holden families separate

At minimum, record the exact service number, OS/calibration ID, engine,
transmission, file size, definition and transport before editing. In this
workspace, VS `$51 Enhanced`, VX/VY `$060A` and later GM controllers are
different targets. They do not share a universal BIN layout, XDF, ADX packet,
checksum or flash method.

Important examples:

- A cable-throttle L36 does not have a BMW-style electronic pedal-to-throttle
  request table. Response changes have to be traced through the actual fuel,
  spark, airflow, torque/transmission and transient strategies.
- A stock `$060A` XDF and an Enhanced-OS XDF are not interchangeable merely
  because both describe a V6 calibration.
- VS G6/Ostrich images and VY flash-PCM images have different hardware and
  read/write proof paths.
- L36 and L67 data are not interchangeable. Injector, load, spark, boost and
  transmission assumptions all change.

## Required input manifest

An AI must stop at inventory if any required field is missing:

```yaml
platform: Holden
ecu_family: "for example VS $51 Enhanced or VY $060A"
service_number: "scan/label value"
os_or_calibration_id: "exact value"
engine: "L36/L67/LS family and displacement"
transmission: "exact manual/automatic and model"
hardware_changes:
  injectors: "part number, pressure and characterization source"
  maf_or_map: "part number and housing"
  induction: "NA/supercharged/turbo; boost physically disabled for first proof"
  exhaust_and_catalysts: "present/absent and legal context"
base_bin:
  path: "user-supplied path"
  bytes: 0
  sha256: "64 hex characters"
xdf:
  path: "user-supplied path"
  sha256: "64 hex characters"
log_definition:
  type: "ADX/EFILive/HPT/other"
  path_or_version: "exact identity"
requested_effect: "one effect only"
```

Do not let an AI select a file because its filename says `stock`, `stage`,
`enhanced`, `crackle` or `working`. Establish the factory parent by identity and
binary lineage first.

## Commands that exist today

The following is the current auditable inspection loop:

```powershell
python cli_map_editor.py preflight --xdf <exact.xdf> --bin <parent.bin>
python cli_map_editor.py export --xdf <exact.xdf> --bin <parent.bin> --output-dir <audit-dir>
python cli_map_editor.py list-maps --xdf <exact.xdf> --bin <parent.bin>
python cli_map_editor.py show-map --xdf <exact.xdf> --bin <parent.bin> --map "<exact table title>"
python cli_map_editor.py show-scalar --xdf <exact.xdf> --bin <parent.bin> --name "<exact scalar title>"
```

After human approval, one bounded edit may be made on a copy:

```powershell
python cli_map_editor.py edit --xdf <exact.xdf> --bin <parent.bin> --map "<exact table title>" --rows <1-based rows> --cols <1-based cols> --value <proved engineering value> --save --output-dir <candidate-dir>
python cli_map_editor.py diff --bin-a <parent.bin> --bin-b <candidate.bin>
python cli_map_editor.py preflight --xdf <exact.xdf> --bin <candidate.bin>
```

`ingest-log`, `query-map`, `compare-log` and `suggest` are roadmap commands,
not current CLI commands. Until implemented, log calculations must be emitted
as a separate review report and must not silently write a BIN.

### XDF edit or direct binary patch?

Use XDF tables/scalars for calibration data whose address, equation, units and
axes are proved. An XDF may also carry `XDFPATCH` entries, but the current CLI
only reports their state; it does not yet provide a proved apply-patch command.

Use a direct binary patch for exact-OS code changes such as a VY `$060A` ASM
hook or launch/fuel-cut routine. Require the parent BIN SHA-256, OS identity,
file-offset address basis, expected original bytes, replacement bytes,
disassembly evidence, checksum coverage, reverse patch and bench/recovery
test. Refuse the patch when any expected byte differs. Do not apply the same
patch to another service number or Enhanced-OS revision because its visible
calibration tables look similar.

## Effect experiments an AI may propose

### 1. Stock-versus-tune audit

This is the safest and most reusable job.

Ask the AI to identify the exact stock parent, export both files, group changed
bytes by XDF parameter, report unexplained bytes, and distinguish calibration
changes from code or checksum regions. It must not infer `Stage 1` from the
number of changed cells.

Acceptance: every changed byte belongs to a named, intended region or is
explicitly unresolved; axes, equations, signedness and byte order display
sanely in both the CLI and TunerPro.

### 2. Closed-loop fuel-model diagnosis

For the currently documented VS `$51 Enhanced` path, learned BLM is a
diagnostic observation:

```text
learned multiplier = raw BLM / 128
```

Use only stable, time-separated samples with closed loop and O2 readiness
proved, coolant inside the learning window, DFCO and purge inactive, no PE,
fault or knock, short-term correction near neutral and both banks reasonably
consistent. Do not write a BLM value directly into a fuel table. First decide
whether the cause is injector data, fuel pressure, intake/exhaust leak, MAF
transfer or another model error.

Effect sought: reduce repeatable closed-loop correction while preserving
bank-to-bank agreement and transient behaviour.

### 3. Open-loop/wideband fuel correction

Only after wideband transfer and timestamp alignment are proved:

```text
required fuel multiplier = measured lambda / commanded lambda
```

AFR can replace lambda only when both values use the same stoichiometric basis.
Measured leaner than commanded yields a multiplier greater than one. Initially
propose small, well-populated regions only; report hit count and spread; do not
extrapolate; do not make a first-pass lean-direction change under PE or boost.

Effect sought: measured lambda follows commanded lambda in the same stable
operating region. This is not proof of injector duty, fuel-pressure margin or
safe boost.

### 4. Knock containment and spark review

An AI may correlate repeatable knock retard with RPM, load/CYLAIR, lambda,
temperature, gear and transient state. It must first exclude false knock,
limiter/shift/traction events, fuel-pressure loss and a wrong active-spark
table. The first recommendation may be to abort and diagnose hardware.

Do not use a generic `add two degrees` recipe. Do not automatically copy the
high-octane table over the low-octane/fallback table. Retain the fallback and
make performance claims only from repeatable dyno data.

Effect sought: remove repeatable knock while preserving the intended fallback,
not maximize the displayed spark number.

### 5. Idle-quality experiment

Inspect target idle, idle-air/IAC authority, idle spark feedback, commanded and
measured mixture, adaptations and accessory loads. Correct leaks and mechanical
faults first. Change one mechanism at a time and require hot/cold restart,
in-gear load, A/C load and stall-recovery tests.

A deliberate lumpy-idle or `ghost cam` effect on a non-VVT L36 is an idle
torque-control effect, not a camshaft change or a power tune. Treat old ghost-
cam documents as hypotheses until their exact BIN/XDF pair and logs are
recovered. Do not create the effect by uncontrolled misfire.

### 6. Transmission behaviour

For the exact automatic transmission, audit upshift/downshift tables, TCC
enable/release, pressure/torque-management interactions and the engine rev
limit together. A higher shift command cannot safely exceed the usable engine
speed or validated transmission range. Change one shift region at a time and
log slip, shift time, temperature and commanded/actual gear.

Effect sought: a measured change in shift timing or feel without flare, bind,
excess slip or loss of torque protection.

### 7. Limiter research

Read the exact XDF equation and disassemble the exact OS code path before
interpreting an 8-bit RPM scalar or a sentinel value. A displayed maximum does
not prove `disabled`, and a forum value for one OS must not be copied to
another. Keep soft/hard thresholds and hysteresis coherent. Raising a limiter
does not prove the valvetrain, oiling, ignition dwell or rotating assembly is
safe at that speed.

### 8. Pops, bangs and catalyst-heating effects

Local `vx crack bangs.bin` and forum recipes are useful comparison targets, not
portable proof. First recover their exact parent, hash, OS and changed-byte
ledger. Retarded combustion plus retained overrun fuel can sharply increase
exhaust-valve, manifold, turbo and catalyst temperature; excess fuel can wash
bores and dilute oil. Do not use this workflow to damage or remove catalysts,
and do not call a screenshot-derived recipe vehicle-tested.

## Copy/paste AI requests

### Audit only

```text
Audit this Holden BIN without editing it. Record SHA-256 and size for the BIN
and XDF, identify the exact ECU/OS/calibration/engine/transmission and whether
the file is stock, Enhanced or unknown. Run preflight, export, list-maps and a
byte diff against the exact stock parent. Group changes by named parameter,
show axes/units/equations, list every unexplained byte and assign an evidence
grade. Do not create a candidate or make a flash-ready claim.
```

### Propose a log-backed fuel correction

```text
Using this exact Holden manifest, BIN/XDF export and log, produce a review-only
fuel-correction proposal. Prove wideband scaling, operating mode and timestamp
alignment. Reject transient, DFCO, purge, fault, knock and insufficient-hit
samples. Report commanded versus measured lambda, median error, spread and hit
count per populated region. Diagnose injector/pressure/MAF/leak alternatives.
Do not edit the BIN and do not extrapolate into unlogged cells.
```

### Build one approved candidate

```text
Apply only the approved Holden table/scalar changes to a copy of the exact
parent BIN with cli_map_editor.py. Show every current value before editing.
Save to a new output directory, diff against the exact parent, rerun preflight,
export the candidate and produce a receipt containing hashes, map names,
addresses, old/new raw values, old/new engineering values, reason and required
vehicle acceptance tests. Stop if any byte outside the approved regions changes.
Do not flash or claim checksum/write readiness.
```

### Design a VY ASM patch

```text
For this exact Holden service number, $060A OS/full-image SHA-256 and matching
disassembly, trace the requested behaviour to the final fuel/ignition/limiter
path. Produce a review-only patch manifest containing file offsets, expected
original bytes, replacement bytes, instruction-boundary and branch-target
proof, register/stack preservation, code-cave ownership, checksum-covered
ranges, reverse bytes and bench tests. First create a harmless observable test
patch. Refuse to emit a vehicle-test candidate if the parent hash or any
expected byte differs. Do not use cli_map_editor.py port for ASM code.
```

### Rebuild an existing VY patch from newer evidence

```text
Treat the named VY patch as LEGACY_REBUILD_REQUIRED. Locate its exact clean
parent, current disassembly project, call/xref trace and any RAM/runtime trace.
Re-derive the patched function and every calibration equation from those
sources. Generate a new manifest with parent hash, expected/replacement bytes,
instruction and branch proof, code-cave ownership, checksum ranges, reverse
bytes and tests. Compare old versus rebuilt bytes/formulas and explain every
difference. Do not copy old payload bytes or constants unless the new trace
independently proves them.
```

## Required hand-off receipt

Every candidate must end with:

- parent and candidate SHA-256 and byte count;
- exact XDF SHA-256 and OS/calibration identity;
- engine, transmission and hardware manifest;
- parameter, address, axes, units, old/new raw and engineering values;
- changed-byte ranges and unexplained-byte count;
- preflight/export result and known parser limitations;
- checksum/signature tool still required;
- logging channels, test conditions, abort limits and recovery plan;
- evidence grade (`CLI_CHECKED` while native parity is due; `STATIC_PROVED` at
  most until physical validation exists).
