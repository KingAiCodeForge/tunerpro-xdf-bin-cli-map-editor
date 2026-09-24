# AI-Assisted ECU Tuning Plan — Log Analysis + Map Adjustment via CLI Editor

**Version:** 1.2
**Date:** 24 September 2026
**Author:** Jason King (KingAiCodeForge)
**Status:** CLI editing works for proved fixtures; log-analysis commands remain planned

---

## Overview

This guide turns a tuning goal into a reviewable AI task. Supply an exact
XDF/BIN pair, hardware and fuel details, logs, constraints, and a measurable
result. The AI can use the CLI for deterministic inspection and bounded edits,
then produce a proposal, byte-level diff, and verification plan. Copying,
smoothing, interpolation, and table porting are useful only when the source,
destination, units, axes, and intended effect are identified.

BMW MS42, MS43 and Holden VY V6 are the initial fixture families. Other
XDF/BIN pairs are supported only after their TunerPro XDF structures and
native displayed values pass the compatibility tests.

Platform-specific tuning guidance is deliberately split. Use:

- [`HOLDEN_AI_TUNING_GUIDE.md`](HOLDEN_AI_TUNING_GUIDE.md) for Holden/Delco work;
- [`BMW_MS42_MS43_MS43X_AI_TUNING_GUIDE.md`](BMW_MS42_MS43_MS43X_AI_TUNING_GUIDE.md) for BMW MS42, stock MS43 and MS43X.
- [`PATCH_REBUILD_REGISTER.md`](PATCH_REBUILD_REGISTER.md) for the current
  patch/formula withdrawal, rebuild, bench and trace queue.

Those guides contain the current evidence labels, effect experiments and
copy/paste AI request templates. This file is the implementation roadmap. A
map recipe, screenshot or tune filename is not proof that a file is compatible,
checksummed, flashable, dyno-developed or even based on the stated OS.

This document outlines the plan for enabling an AI agent (Copilot/Claude in VS Code agent mode) to:

1. **Read** datalog CSV files from a running car (TunerPro, EFILive, HP Tuners, etc.)
2. **Read** current BIN+XDF calibration exports
3. **Analyze** log data against current calibration to identify problems
4. **Recommend** specific map/scalar changes with reasoning
5. **Apply** changes via `cli_map_editor.py` commands
6. **Verify** changes by comparing pre/post BIN diffs and reviewing logs

The goal is a closed-loop tuning workflow: **log → analyze → adjust → flash → log → verify**.

---

## Part 1: Current release boundary (CLI Editor v1.1.0)

| Capability | Status | Command |
|---|---|---|
| Load XDF+BIN and parse implemented parameter forms | ✅ Fixture-scoped | Internal |
| List all maps/scalars/flags | ✅ Done | `list-maps` |
| Show table data with axes | ✅ Done | `show-map` |
| Show scalar values | ✅ Done | `show-scalar` |
| Edit table cells (single/range) | Bounded integer layouts; no scoped MATH writes | `edit --autosave` |
| Edit scalar values | Bounded integer/affine conversions | `edit-scalar --autosave` |
| Edit flags | Preserve sibling bits; bounded mask | `edit-flag --autosave` |
| Batch edits from CSV | Disabled: partial-result defect | `batch` |
| Persist unbound temp edits | Disabled: no source/XDF binding | `save` |
| Export snapshot (TXT/JSON/MD) | ✅ Done | `export` |
| Port maps between ECUs | Disabled: partial-result and interpolation validation gaps | `port` |
| Preflight validation | ✅ Done | `preflight` |
| Byte-level BIN diff | ✅ Done | `diff` |
| Inverse math (real→raw) | Symbolically affine only; no numerical fallback | Internal |
| AFR↔Lambda conversion | Experimental, not release-enabled | Internal |
| Bilinear resample for different axes | Experimental, not release-enabled | Internal |
| Exact-hash raw patches | Strict v2 manifest with optional registered checksum verifier | `verify-raw-patch`, `apply-raw-patch` |

**Historical fixture families:** BMW MS42 0110C6, BMW MS43 430069, Holden VY V6 $060A Enhanced.
These names are not blanket compatibility claims. Current portable tests use
synthetic fixtures and the pinned exporter 3.7.2. One-shot edits produce new
exclusive outputs; temp sessions are disabled. Source/log/diff and target-specific
native/hardware review remain mandatory before vehicle use.

**Platform details:** See `GENERAL_INFO_FOR_MS42.MD`, `GENERAL_INFO_FOR_MS43.MD`, and `GENERAL_INFO_FOR_vy_V6_ENHANCED_L36.MD` for hardware specs, memory layouts, firmware versions, XDF/BIN file names, key maps, and flash tools for each platform.

**Improvement backlog:** See `ignore/test_run_20260303/IMPROVEMENT_IDEAS.MD` for the prioritized list of features to implement.

**Current status note:** the CLI and exporter read actual TunerPro XDF XML, but
support remains fixture-scoped. Native TunerPro parity checks and
padding/stride experiments must not be treated as universal. The shared-copy
refactor must retain the exact `BASEOFFSET`, `EMBEDDEDDATA`, `XDFAXIS`,
`embedinfo`, `MATH` and `VAR` behavior proved by the retained native fixtures.

**Where the next value is:** log ingestion, `compare-log`, `query-map`, and `suggest` are still the best follow-on commands for moving from map editing into practical tuning guidance.

### What "proven" means here

The repeatable part is the method, not a universal spark value, fuel
percentage, limiter setting, or table name. Use this evidence order:

1. Record exact ECU/software identity, BIN/XDF hashes and sizes, engine,
   transmission, fuel, sensors, injectors, fuel pressure, and hardware.
2. Prove address, shape, axes, units, byte order, signedness, equation, and
   orientation against a retained target-specific fixture and native TunerPro.
3. Establish mechanical and sensor health, including stable fuel pressure and
   trustworthy lambda data when mixture is part of the decision.
4. Reproduce the baseline in comparable operating cells. Reject transient,
   faulted, intervention, and poorly populated samples.
5. Change the smallest connected region that tests one stated hypothesis.
6. Repeat the same test and compare the requested effect and side effects.
   Keep, revise, or revert from that evidence.

The audit chain is: exact input hashes -> observed cells -> proposed edit ->
exact changed bytes -> checksum/signature handling -> comparable re-log.

### Calibration edits, XDF patches, and direct ASM patches

These are separate operations:

- **Calibration edit:** `XDFTABLE`/`XDFCONSTANT` data is decoded through the
  XDF equation and changed with `edit --autosave` or `edit-scalar --autosave`.
- **XDF patch:** `XDFPATCH`/`XDFPATCHENTRY` can describe expected base bytes
  and replacement bytes. The current parser reports patch status, but this
  CLI does not yet expose a proved patch-application command.
- **Direct ASM patch:** a version-specific hook, code cave, branch, or data
  payload is applied by raw file offset only after its exact original bytes
  and execution context are proved. This is the appropriate model for VY ASM
  work and MS43X features that change code rather than calibration data.

Never use `port` for code patches. The guarded raw-patch v2 commands now exist;
see README for the actual JSON schema and portable tests. The following older
YAML is a design sketch, not an accepted manifest:

```yaml
patch_id: "human-readable name and revision"
target:
  ecu: "exact family"
  software_id: "exact OS/version"
  image_layout: "full/partial and address basis"
  byte_count: 0
  parent_sha256: "64 hex characters"
architecture: "for example HC11 or C167"
chunks:
  - file_offset: "0x000000"
    expected_hex: "original bytes"
    replacement_hex: "same-length replacement or proved hook"
    purpose: "one behaviour"
checksum:
  covered_ranges: "proved ranges"
  repair_tool_and_version: "external tool until implemented"
verification:
  - "disassembly and control-flow review"
  - "apply then reverse-apply byte-for-byte"
  - "complete diff contains declared chunks only"
  - "bench execution/readback and recovery test"
```

An XDF may remain the human-facing description for these patches, while the
actual writer uses this hash- and expected-byte-gated manifest. That keeps the
patch auditable without pretending it is portable between operating systems.

### Rebuild policy for legacy patches and formulas

Existing VY, MS43 and MS43X patches are discovery evidence. Rebuild them when
newer disassembly, call tracing, RAM tracing, native TunerPro evidence, or
conversion analysis is available. Do not merely copy the old replacement
bytes into a new manifest.

For each legacy patch or questionable formula:

1. Recover the exact clean parent and record its identity and SHA-256.
2. Re-find the function, callers, inputs, outputs and final actuator or lookup
   path in the current disassembly; record tool version and addresses.
3. Re-run the relevant trace and distinguish calibration storage, RAM state,
   diagnostic data and code operands.
4. Re-derive the hook, branch, code-cave payload, table dimensions, signedness,
   endian, scaling and inverse equation from that evidence.
5. Generate new expected/replacement bytes or corrected XDF math from source,
   rather than hand-editing the old artifact.
6. Compare old and rebuilt forms and explain every difference. Preserve the old
   hash as provenance, not as authority.
7. Prove reverse application, declared-byte-only diff, native display/write
   behavior where applicable, checksum coverage, bench execution and recovery.

Label an older artifact `LEGACY_REBUILD_REQUIRED` until this chain is complete.
Better formulas should replace guessed constants only when forward decoding,
inverse encoding and round-trip behavior all agree for the stored raw range.

---

## Part 2: What's Missing for AI Agent Readiness

> **Command-status boundary:** `ingest-log`, `query-map`, `compare-log` and
> `suggest` in this section are proposed interfaces. They are not commands in
> `cli_map_editor.py` as of 20 September 2026. Do not give the examples below
> to an agent as though they can run today. The current executable commands are
> `list-maps`, `show-map`, `show-scalar`, `edit`, `edit-scalar`, `batch`,
> `save`, `export`, `port`, `preflight` and `diff`.

### 2.1 Log Ingestion Command (`ingest-log`)

**Problem:** The AI has no way to load datalog data into the session. It can read CSVs manually, but needs a structured command that:
- Parses TunerPro `.csv` / EFILive `.csv` / HP Tuners `.csv` log formats
- Normalizes channel names to XDF parameter names where possible
- Computes summary statistics (min/max/avg/percentile per channel)
- Flags anomalies (knock events, lean spikes, timing retard, misfires)

**New command:**
```
python cli_map_editor.py ingest-log --log datalog.csv --xdf def.xdf --format tunerpro
```

**Output:** Structured summary AI can reason about — JSON or formatted text with:
- Channel list with units
- Per-channel statistics (min, max, mean, p5, p95, stdev)
- Detected operating regions (idle, part-load, full-load, overrun)
- Anomaly flags (knock counts, lean excursions, timing pull)
- Cross-reference to XDF map names where channel maps to a tunable parameter

**Supported log formats (priority order):**
1. TunerPro RT ADX datalog CSV (channel names from ADX definition)
2. EFILive V8 scan tool CSV
3. HP Tuners VCM Scanner CSV
4. Generic CSV with headers (AI tries to match column names)
5. ccflash
6. others.

### 2.2 Map Query Command (`query-map`)

**Problem:** `show-map` prints the whole table. AI needs to query specific operating points.

**New command:**
```
python cli_map_editor.py query-map --xdf def.xdf --bin fw.bin --map "Fuel Map" --rpm 3200 --load 450
```

**Output:** Interpolated value at the requested RPM/load point, plus the four
surrounding cells and their values. For example: "At 3200 RPM / 450 CYLAIR,
commanded lambda is 0.92 and measured lambda is 0.88. The measured mixture is
about 4.3% richer than commanded (`0.88 / 0.92 - 1`). This observation does
not identify the responsible table; verify operating state, wideband scaling,
injector/fuel-pressure data and the active fuel path before proposing an edit."

### 2.3 Compare-to-Log Command (`compare-log`)

**Problem:** AI needs to see current calibration values *at the operating points that actually occurred in the log*, not the entire table.

**New command:**
```
python cli_map_editor.py compare-log --xdf def.xdf --bin fw.bin --log datalog.csv --map "Spark Table"
```

**Output:** For each logged sample point, show:
- RPM + load from log
- Commanded value from log (if available)
- Calibration table value at that RPM/load (interpolated from BIN)
- Delta between commanded and calibration
- Knock retard at that point (if knock channel present)

This is the core analysis tool — it shows WHERE the tune disagrees with what the ECU is doing.

### 2.4 Suggest Command (`suggest`)

**Problem:** AI needs a structured way to propose changes that the user can review before applying.

**New command:**
```
python cli_map_editor.py suggest --xdf def.xdf --bin fw.bin --log datalog.csv --target "reduce knock"
```

**Output:** First emit a diagnosis record. Do not emit edit rows until the
active path, repeatability, proposed engineering value and acceptance test are
reviewed:
```csv
# Observation: repeated retard events at 3200-4800 RPM / 400-600 CYLAIR
# Status: NEEDS_ACTIVE_PATH_AND_CAUSE_REVIEW
# Alternatives: false knock, shift/limiter/traction event, fuel pressure,
#               temperature correction, timestamp or axis mismatch
# Proposed value: <none until reviewed>
map,row,col,value
```

After review, `suggest` may place only the approved cells and values into a
separate batch CSV. Event count alone must never generate a timing value.

### 2.5 Session State / Multi-Edit Workflow

**Problem:** Currently each command is stateless — loads XDF+BIN fresh every time. For an AI doing iterative tuning, this is slow and doesn't track cumulative changes.

**Enhancement:** Add a `--session` flag or a `session` command that:
- Loads XDF+BIN once
- Accepts multiple edit commands interactively (stdin or pipe)
- Tracks all changes in memory
- Saves once at the end with a single combined log

**Current alternative:** keep the stateless CLI and chain edits by passing the
previous timestamped output back through the existing `--bin` argument:
```
# First edit: from factory bin
python cli_map_editor.py edit --xdf def.xdf --bin factory.bin --map "<map>" --rows <rows> --cols <cols> --value <reviewed-value> --save

# Second edit: from the output of the first
python cli_map_editor.py edit --xdf def.xdf --bin output/factory_edited_20260304_120000.bin --map "<map>" --rows <rows> --cols <cols> --value <reviewed-value> --save
```

This already works. The AI just needs to chain commands using the output BIN from the previous step.

---

## Part 3: Log Analysis — What the AI Looks At

### 3.1 Critical Channels (by platform)

#### BMW MS42/MS43 (runtime channels plus calibration context)

An ADX runtime item and an XDF calibration item are different objects. The
names below are calibration candidates to inspect after the runtime channel,
units, packet location and equation are proved for the exact logger/firmware.

| Runtime channel | Candidate XDF context, not an ADX mapping | What AI checks |
|---|---|---|
| RPM | speed axes in the active strategy | Operating-cell identification |
| Measured airflow | `id_maf_tab` and load-indexed maps | Sensor range, load calculation and correlation |
| Measured lambda | target-lambda maps and complete fuel path | Measured versus commanded mixture after state filtering |
| Commanded lambda | active target-lambda map plus later corrections | Which target path was active |
| Delivered ignition angle | base spark, corrections and interventions | Delivered versus candidate base value; do not assume equality |
| Knock retard/status | knock thresholds, factors and retard paths | Repeatable event context; not an automatic spark edit |
| Coolant/intake temperature | temperature-indexed corrections and protections | Warm-up, heat soak and active protection state |
| Pedal/throttle/load request | request maps and torque interventions | Requested versus delivered response |
| Battery voltage | injector latency/voltage compensation | Whether voltage-dependent fueling error is plausible |
| VANOS target/actual | MS42 `kf_vanos_*`; MS43 `ip_cam_sp_*` candidates | Target tracking and active cam path |
| Target/actual idle speed | idle target, air and ignition control | Target error, controller authority and load state |

#### Holden VY V6 (runtime channels plus calibration context)

| Runtime channel | Candidate XDF context, not an ADX mapping | What AI checks |
|---|---|---|
| RPM | speed axes in the active strategy | Operating-cell identification |
| CYLAIR/load | load axes and airflow model | Load identification and axis correlation |
| Delivered spark advance | active spark path and corrections | Delivered timing versus candidate base tables |
| Knock retard/status | knock-control calibration and intervention path | Repeatability and false-knock/intervention alternatives |
| O2/wideband lambda | commanded-mixture path and fuel model | Mixture error after proving sensor transfer and state |
| Coolant/intake temperature | temperature corrections and protections | Warm-up and protection state |
| MAF frequency/airflow | exact MAF transfer and housing | Airflow-model hypothesis after leak/pressure checks |
| TPS/load request | PE and transient enable candidates | Driver request and operating-mode selection |
| Injector pulse width | injector flow, latency and pressure model | Delivered-fuel context, not a direct table value |
| BLM/INT | no direct table equivalence | Learned/short-term correction used as diagnostic evidence |

### 3.2 Analysis Rules the AI Applies

**Knock Analysis:**
- Do not turn one non-zero retard sample into a table edit. First exclude a
  shift, limiter contact, traction/torque intervention, sensor fault, transient
  noise and a wrong RPM/load alignment.
- Correlate repeated events with fuel, temperature, requested/actual load and
  the ECU's active ignition path. Identify all tables and corrections that can
  contribute; the visible high-octane table may not be the active source.
- The safe first result can be `abort and diagnose`, not an edit. An AI must not
  invent `retard + margin` math or add timing back automatically.

**Fueling Analysis (Lambda/AFR):**
- Prove sensor transfer, units, stoichiometric basis, timestamp alignment and
  commanded operating mode before calculating an error.
- Use only stable samples with adequate hit count. Reject transient,
  deceleration fuel cut, purge, cold start, fault and knock rows as required by
  the platform guide.
- Report measured/commanded error and spread. Do not assume the visible fuel
  table is the cause: injector data, pressure, MAF/load model, closed-loop
  trims and late corrections can produce the same symptom.

**MAF Accuracy:**
- A repeatable trim trend makes MAF transfer one hypothesis, not a conclusion.
  Check leaks, fuel pressure, injector characterization, exhaust leaks and both
  banks first.
- Never apply a global MAF multiplier from one log. Propose only measured,
  well-populated regions and preserve monotonicity and sensor limits.

**Idle Stability:**
- Separate target idle from control error. Check mechanical air leaks,
  adaptations, ICV/throttle authority, cam targets, ignition correction,
  lambda and accessory-load state before changing a calibration.
- A deliberate `ghost cam` effect is an idle-torque experiment, not a power
  tune. It needs an exit condition above idle and checks for stalls, oil
  pressure, catalyst temperature and drivability.

**Thermal Compensation:**
- Compare repeated hot/cold logs, but do not remove a factory temperature
  protection simply because it reduces torque. Diagnose the reason the
  protection became active and retain a safe fallback path.

---

## Part 4: AI Agent Workflow — Step by Step

### 4.1 Initial Tune Assessment

```
USER: "Here's my car's datalog and current tune. What needs fixing?"

AI ACTIONS:
1. preflight --xdf tune.xdf --bin tune.bin
2. export/list-maps/show-map for the exact candidate calibration paths
3. Analyze the log separately with proved channel IDs, units, state filters,
   hit counts and timestamp alignment
4. [PLANNED] ingest-log/compare-log may automate step 3 after implementation
5. Report observations, competing causes and unresolved identity/evidence gaps
6. Propose a bounded A/B test only when the active path is established
```

### 4.2 Apply Recommended Changes

```
USER: "Fix the knock issue at 3200-4800 RPM"

AI ACTIONS:
1. Prove that events repeat in the same cells and are not shift, limiter,
   traction, sensor-noise, fuel-pressure or timestamp-alignment artefacts
2. Prove the active base/fallback/correction path for the exact OS
3. show-map every contributing table and report current axes/values
4. Propose the smallest bounded cell region, with pass and abort criteria;
   do not derive a change from `knock_retard + margin`
5. After the exact scope is reviewed, generate and apply the batch CSV
6. diff the exact parent/candidate and fail on any undeclared byte
7. preflight/export the candidate and issue a review-only receipt
```

### 4.3 Verify After Re-Log

```
USER: "Here's the new log after flashing. Did the changes work?"

AI ACTIONS:
1. Analyze the new log separately with the same proved channels, filters,
   operating cells and conditions as the baseline
2. [PLANNED] ingest-log/compare-log may automate that comparison after they
   are implemented
3. Check whether the original observation repeated in the target cells
4. Check delivered timing, lambda, temperatures, interventions and faults
5. Compare pass/abort metrics and any unrequested side effects
6. Report the repeatability, temperatures, lambda, delivered timing and all
   side effects. Hold or revert from evidence. Any later advance experiment is
   a separate, reviewed dyno/A-B proposal; never add timing back automatically.
```

### 4.4 Iterative Refinement

The AI tracks the history of changes across sessions:
```
Session 1: parent → candidate A (one named region and one stated hypothesis)
Session 2: candidate A → keep/revert decision from comparable re-log
Session 3: accepted parent → candidate B (next independent hypothesis)
```

Each session uses the previous output BIN as input, with a full change log chain.

---

## Part 5: Implementation Priority

### Phase 1 — Core AI Readiness (implement first)
| # | Task | Effort | Impact |
|---|---|---|---|
| 1 | `ingest-log` command — parse TunerPro CSV logs | Medium | Critical |
| 2 | `query-map` command — interpolated point lookup | Small | High |
| 3 | `compare-log` command — log vs calibration overlay | Medium | Critical |
| 4 | AI agent prompt template with safety rules | Small | High |
| 5 | Log format auto-detection (TunerPro/EFILive/HPT) | Medium | Medium |

### Phase 2 — Smart Analysis (after Phase 1 works)
| # | Task | Effort | Impact |
|---|---|---|---|
| 6 | Knock analysis rules engine | Medium | High |
| 7 | Fuel trim analysis + MAF correction calculator | Medium | High |
| 8 | `suggest` command — generate batch CSV with reasoning | Medium | High |
| 9 | Operating region classifier (idle/part/full/overrun) | Small | Medium |
| 10 | Thermal analysis (IAT/ECT correlation) | Small | Medium |

### Phase 3 — Workflow Polish
| # | Task | Effort | Impact |
|---|---|---|---|
| 11 | Session state (interactive mode) | Medium | Medium |
| 12 | Change history tracker across sessions | Small | Medium |
| 13 | Checksum calculator integration (MS42/MS43/VY) | Large | Critical for flash |
| 14 | Unit test suite for all commands | Medium | Quality |
| 15 | Pre-built ADX channel→XDF parameter mapping files | Small | Convenience |

---

## Part 6: Log File Format Reference

### TunerPro RT Datalog CSV
```csv
Time,RPM,MAF (kg/h),Lambda,Coolant (°C),Knock Retard,Spark Advance,TPS %
0.000,780,12.5,1.000,82,0.0,12.3,0.5
0.050,785,12.8,0.998,82,0.0,12.5,0.5
0.100,3200,145.2,0.920,88,2.1,28.4,45.0
```
- Header row has channel names (from ADX definition)
- Units may be in parentheses or separate
- Time column is seconds from log start
- Sample rate varies (typically 10-50 Hz for TunerPro RT)

### EFILive V8 CSV
```csv
Timestamp,Engine Speed (RPM),Mass Air Flow (g/s),Equivalence Ratio,ECT (°C)
00:00:00.000,780,4.2,1.000,82
00:00:00.100,785,4.3,0.998,82
```
- Similar structure, different channel naming convention
- Uses g/s for MAF (not kg/h)
- Uses Equivalence Ratio (lambda) not AFR

### HP Tuners VCM Scanner CSV
```csv
Time (sec),Engine Speed (RPM),MAF (g/s),Commanded AFR,Actual AFR,Spark Advance (°),KR (°)
0.00,780,4.2,14.68,14.70,12.3,0.0
```
- Uses AFR directly (not lambda)
- KR = Knock Retard in degrees

---

## Part 7: Safety Constraints for AI

These rules are **non-negotiable** — the AI must ALWAYS follow them:

1. **NEVER call an output flash-ready** — this editor does not prove the ECU
   identity, code compatibility, checksum/signature, write path, power supply,
   readback or recovery path. Verify each of those outside this CLI.

2. **NEVER modify original BIN files** — all changes go to timestamped output copies.

3. **NEVER auto-apply a tuning proposal** — first emit a reviewable plan with
   exact parameter names, axes, current values, proposed values, reason,
   evidence grade and abort conditions. A human must select the edit scope.

4. **NEVER port code patches** — patches are firmware-version-specific binary
   modifications. Even calibration data is portable only after units, axes,
   engine/hardware meaning and target code use are proved.

5. **NEVER change MAF calibration without explicit user request** — MAF tables are sensor-specific calibrations. Wrong MAF cal = wrong fueling everywhere.

6. **NEVER change injector characterization without hardware info** — injector deadtime and flow rate depend on physical injector specs.

7. **Do not use a universal timing allowance** — neither `+3 degrees` nor
   unlimited retard is inherently safe. Retard can raise exhaust temperature;
   advance can cause knock. Propose bounded, logged cells only and require a
   platform-appropriate knock/EGT/temperature review. Do not add timing from a
   screenshot or another engine.

8. **Do not use a universal fuel allowance** — excessive enrichment can wash
   bores, overheat or destroy catalysts and dilute oil; leaning can damage the
   engine. A correction needs a proved commanded target, measured wideband
   scaling, stable operating state and hardware-specific injector/pressure
   data. Do not extrapolate into unlogged cells.

9. **Always log every change** — every edit must have a corresponding log entry.

10. **Always establish exact identity before preflight** — record SHA-256,
    length, full/partial layout, OSID/software/calibration ID, engine,
    transmission, emissions/hardware variant and XDF hash. `preflight` checks
    implemented XDF/BIN structure; it cannot prove those identities for you.

11. **Separate evidence grades** — `cli-checked` records exact identity plus
    CLI export/diff/write round-trip; `static-proved` additionally requires
    retained native TunerPro display/write parity for that structure;
    `vehicle-tested` requires a named artifact and retained log/readback; and
    `dyno-validated` requires retained before/after data. A screenshot or
    filename is `reference-only` until correlated to its BIN.

12. **Keep XDF and ADX addressing separate** — an XDF calibration address is
    not automatically an ADX runtime address, diagnostic identifier or packet
    offset. Logging definitions need their own protocol and firmware proof.

---

## Part 8: Channel-to-Parameter Mapping Files

Future mapping files should correlate proved runtime channels with calibration
*candidates*. They must not imply that an ADX item is an XDF address or that a
runtime value equals a base-table value. These will live in `mappings/`:

### Format
```csv
log_channel,adx_identifier,xdf_candidate,type,notes
RPM,<proved per ADX>,,axis,"Locate operating cells"
Measured Lambda,<proved per ADX>,,measurement,"Compare with proved commanded-lambda channel"
Commanded Lambda,<proved per ADX>,<active target map candidate>,compare,"Account for later corrections"
Knock Retard,<proved per ADX>,,flag,"Event evidence; no direct XDF equivalence"
Delivered Spark,<proved per ADX>,<active spark path candidates>,compare,"Delivered value may include corrections"
Coolant,<proved per ADX>,<temperature correction candidates>,context,"Operating state and protections"
Battery Voltage,<proved per ADX>,<injector latency candidate>,context,"Investigate voltage-dependent error"
```

- `type=axis` — locate candidate calibration cells after axis units are proved
- `type=measurement` — observation with no direct XDF equivalence
- `type=compare` — compare only after the active path and later corrections are known
- `type=context` — evidence used to select state or investigate a cause
- `type=flag` — event/status to correlate; nonzero alone does not prescribe an edit

### Per-Platform Files Needed
- `mappings/ms42_tunerpro_channels.csv` — BMW MS42 ADX → XDF mapping
- `mappings/ms43_tunerpro_channels.csv` — BMW MS43 ADX → XDF mapping
- `mappings/vy_v6_tunerpro_channels.csv` — Holden VY ADX → XDF mapping
- `mappings/vy_v6_efilive_channels.csv` — Holden VY EFILive → XDF mapping

---

## Method references and limits

These primary vendor references support the measurement order used above:

- [Haltech: Tuning Base Tables](https://support.haltech.com/portal/en/kb/articles/tuning-base-tables)
  explains why engine volume, injector flow and injector dead time must be
  correct before treating a VE table as a physical engine-efficiency model.
- [Haltech: Injector Dead Time](https://support.haltech.com/portal/en/kb/articles/injector-dead-time)
  describes the voltage, pressure and short-pulse dependencies that make
  guessed latency values a poor substitute for injector characterization.
- [Link ECU: Fuel Equations](https://linkecu.com/software-support/fuel-equations-pclink/)
  separates modelled VE, injector/fuel properties and lambda targets instead
  of asking the VE surface to absorb every setup error.
- [MoTeC: M1 Tune](https://www.motec.com.au/products/M1%20Tune) documents a
  task-specific logging and calibration workflow suitable for controlled A/B
  testing.

These references describe general calibration practice. They do not validate
BMW or Holden table names, addresses, targets, limits, checksums, patches, or
flash procedures. Repository-specific parser and write claims still require
retained native fixtures and regression tests for the exact XDF structures.

---

## Appendix A: AI Agent Session Prompt Template

```
You have access to cli_map_editor.py in the tunerpro-xdf-bin-cli-map-editor repo.
This tool reads and writes ECU calibration data using XDF definitions and BIN firmware files.

REQUEST:
- Effect sought: [one observable result]
- Pass metric: [measured before/after condition]
- Abort limits: [sensor, temperature, pressure, knock, fault and timeout limits]
- ECU/software/layout: [exact identity]
- Engine/transmission/hardware/fuel: [complete manifest]
- XDF/BIN/log paths and SHA-256: [exact files]
- Allowed scope: [audit only, named calibration parameters, or patch design]

CURRENT WORKFLOW (always follow in order):
1. Record identity, hashes and baseline evidence; stop at inventory if they do
   not match.
2. Run preflight, export, list-maps and the required show-map/show-scalar
   commands.
3. Analyze any log separately, with channel units, operating-state filters,
   hit counts, spread and timestamp alignment stated. `ingest-log`,
   `query-map`, `compare-log` and `suggest` are PLANNED, not current commands.
4. Report observations, competing causes, evidence grade and unresolved items.
5. Propose one bounded change set and its A/B acceptance test. Do not write it
   while the scope is still unresolved.
6. Apply only the reviewed rows/cells/scalars with edit/edit-scalar/batch to a
   copy of the exact parent.
7. Diff parent against candidate, rerun preflight, export the candidate and
   fail if any undeclared byte changed.
8. Produce a receipt with hashes, raw and engineering values, changed-byte
   ranges, checksum/signature status, rollback and required re-log.

SAFETY:
- Treat output as review-only until exact identity, checksum/signature,
  write/readback and recovery proof are complete
- NEVER modify original BIN files
- NEVER auto-apply without user approval
- Do not use generic timing or fueling allowances
- Do not port code patches or copy maps between engine sizes by name alone
- Always run preflight first
- Always show-map before editing
- Always export and diff the exact parent/output pair
- State the evidence grade and required logging/dyno acceptance test

FILE PATHS:
- XDF: [user provides]
- BIN: [user provides]
- LOG: [user provides]
- Output: ./output/ (auto-created, timestamped)
```

---

## Appendix B: Example Full Tuning Session

> **Illustrative roadmap only:** the identities, values and command output in
> this example are fictional, and several commands are not implemented. It is
> not a tune recipe or a flash procedure. Use the relevant platform guide for a
> current request template.

```
USER: I have a BMW E46 328ci with MS42. Here's my datalog from a highway run
      and my current tune. The car is knocking under load.

FILES PROVIDED:
  - tune.xdf (Siemens_MS42_0110C6_ENG_512K_v1.1.xdf)
  - tune.bin (current calibration)
  - highway_log.csv (TunerPro RT datalog)

AI SESSION:

> preflight --xdf tune.xdf --bin tune.bin
  BASEOFFSET: 0x48000 subtract=0
  BIN size: 524288 bytes (512KB)
  Tables: 597 OK
  ALL CHECKS PASSED

> ingest-log --log highway_log.csv --xdf tune.xdf --format tunerpro
  Duration: 342 seconds (5.7 minutes)
  Samples: 17,100 @ 50Hz
  RPM range: 740 - 6,280
  MAF range: 8.2 - 298.4 kg/h
  Knock events: 14 (all at RPM 3200-5600, MAF 180-260)
  Lambda drift: actual 0.94 vs target 0.98 at WOT (4% rich)

> compare-log --xdf tune.xdf --bin tune.bin --log highway_log.csv --map ip_igab__n__maf
  KNOCK RETARD detected at 14 sample points:
    RPM 3200-4000 / MAF 180-220: avg 1.8° retard (rows 5-7, cols 7-8)
    RPM 4400-5600 / MAF 220-260: avg 3.1° retard (rows 8-10, cols 8-9)

RECOMMENDATION:
  Do not edit from event count alone. Confirm the active spark path and reject
  shift/limiter/traction events, false knock, fuel-pressure loss and timestamp
  misalignment. If the same cells remain implicated, propose a small bounded
  retard in those cells, preserve the fallback path, and state abort limits.

  Measured lambda is richer than commanded in this sample. Verify wideband
  scaling and repeatability; do not assume that richness is safe or that the
  visible base-fuel table is the cause.

USER: Approve the reviewed, exact-cell spark proposal.

> batch --xdf tune.xdf --bin tune.bin --csv spark_fix_v2.csv
  Applied 12 cell changes to ip_igab__n__maf
  Saved: output/tune_batch_20260304_143022.bin
  Log:   output/tune_batch_20260304_143022.log

> diff --bin-a tune.bin --bin-b output/tune_batch_20260304_143022.bin
  Changed bytes: 12
  All changes in range 0x4F2B5-0x4F2E0 (ignition table region)

DONE: Review-only candidate produced. Exact identity, native TunerPro display,
      checksum/signature, write/readback and recovery remain unproved. Do not
      flash on the strength of this example. If independently cleared for a
      controlled test, re-log the same conditions and retain the readback.
```
