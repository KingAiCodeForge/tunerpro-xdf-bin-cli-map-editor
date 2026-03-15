# AI-Assisted ECU Tuning Plan — Log Analysis + Map Adjustment via CLI Editor

**Version:** 1.0  
**Date:** March 2026  
**Author:** Jason King (KingAiCodeForge)  
**Status:** Planning

---

## Overview

if you want to add a ecu partial or full and have a good idea on what you want done this tool is made to ask a ai to do what you could do yourself with copy paste or smoothing/interopolation etc etc

im using bmw ms42, ms43 and holden vy v6 as test platforms but the tool is designed to be universal for any XDF/BIN pair with edits to the code.

This document outlines the plan for enabling an AI agent (Copilot/Claude in VS Code agent mode) to:

1. **Read** datalog CSV files from a running car (TunerPro, EFILive, HP Tuners, etc.)
2. **Read** current BIN+XDF calibration exports
3. **Analyze** log data against current calibration to identify problems
4. **Recommend** specific map/scalar changes with reasoning
5. **Apply** changes via `cli_map_editor.py` commands
6. **Verify** changes by comparing pre/post BIN diffs and reviewing logs

The goal is a closed-loop tuning workflow: **log → analyze → adjust → flash → log → verify**.

---

## Part 1: What's Already Working (CLI Editor v1.0.0)

| Capability | Status | Command |
|---|---|---|
| Load XDF+BIN, parse all elements | ✅ Done | Internal |
| List all maps/scalars/flags | ✅ Done | `list-maps` |
| Show table data with axes | ✅ Done | `show-map` |
| Show scalar values | ✅ Done | `show-scalar` |
| Edit table cells (single/range) | ✅ Done | `edit` |
| Edit scalar values | ✅ Done | `edit-scalar` |
| Batch edits from CSV | ✅ Done | `batch` |
| Save with timestamp + TunerPro log | ✅ Done | `save` |
| Export snapshot (TXT/JSON/MD) | ✅ Done | `export` |
| Port maps between ECUs | ✅ Done | `port` |
| Preflight validation | ✅ Done | `preflight` |
| Byte-level BIN diff | ✅ Done | `diff` |
| Inverse math (real→raw) | ✅ Done | Internal |
| AFR↔Lambda conversion | ✅ Done | Internal |
| Bilinear resample for different axes | ✅ Done | Internal |

**Tested platforms:** BMW MS42 0110C6, BMW MS43 430069, Holden VY V6 $060A Enhanced

**Platform details:** See `GENERAL_INFO_FOR_MS42.MD`, `GENERAL_INFO_FOR_MS43.MD`, and `GENERAL_INFO_FOR_vy_V6_ENHANCED_L36.MD` for hardware specs, memory layouts, firmware versions, XDF/BIN file names, key maps, and flash tools for each platform.

**Improvement backlog:** See `ignore/test_run_20260303/IMPROVEMENT_IDEAS.MD` for the prioritized list of features to implement.

---

## Part 2: What's Missing for AI Agent Readiness

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

**Output:** Interpolated value at the requested RPM/load point, plus the 4 surrounding cells and their values. This lets the AI say "at 3200 RPM / 450 CYLAIR, the current fuel target is 0.92 lambda, but the log shows 0.88 actual — the correction is -4%, indicating the base map is lean."

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

**Output:** A batch CSV file with proposed changes, plus reasoning in comments:
```csv
# Suggestion: reduce knock at 3200-4800 RPM / 400-600 CYLAIR
# Evidence: 12 knock events in log at these operating points
# Strategy: pull 2 degrees timing in affected cells
map,row,col,value
ip_igab__n__maf,5,8,22.0
ip_igab__n__maf,5,9,21.5
ip_igab__n__maf,6,8,23.0
ip_igab__n__maf,6,9,22.5
```

The user can review this CSV, modify if needed, then apply with `batch`.

### 2.5 Session State / Multi-Edit Workflow

**Problem:** Currently each command is stateless — loads XDF+BIN fresh every time. For an AI doing iterative tuning, this is slow and doesn't track cumulative changes.

**Enhancement:** Add a `--session` flag or a `session` command that:
- Loads XDF+BIN once
- Accepts multiple edit commands interactively (stdin or pipe)
- Tracks all changes in memory
- Saves once at the end with a single combined log

**Alternative:** Keep the current stateless CLI but add a `--base-bin` flag that lets the AI stack edits:
```
# First edit: from factory bin
python cli_map_editor.py edit --xdf def.xdf --bin factory.bin --map "Spark" --rows 5-6 --cols 8-9 --value 22.0 --save

# Second edit: from the output of the first
python cli_map_editor.py edit --xdf def.xdf --bin output/factory_edited_20260304_120000.bin --map "Fuel" --rows 3 --cols 4 --value 0.95 --save
```

This already works. The AI just needs to chain commands using the output BIN from the previous step.

---

## Part 3: Log Analysis — What the AI Looks At

### 3.1 Critical Channels (by platform)

#### BMW MS42/MS43 (TunerPro RT channels via ADX):

**Note:** MS42 uses `kf_*`/`tab_*` naming (e.g., `kf_zw_roz98_vanos_tl__n__lm`). MS43 uses `ip_*`/`id_*` IVVT naming (e.g., `ip_iga_ron_98_pl_ivvt__n__maf`). Both platforms share 410 common table names in `ip_*` format. The table below uses MS43 names where shared and notes MS42-only names.

| Channel | XDF Parameter Link | What AI Checks |
|---|---|---|
| RPM | axis — all tables | Operating point identification |
| MAF (kg/h) | `id_maf_tab` (both) | Load axis for all MAF-indexed tables |
| Lambda actual | MS42: `kf_lam_*`, MS43: `ip_lam_i__n__maf` | Actual vs target fueling |
| Lambda target | Same as actual — compare to table output | Commanded mixture |
| Ignition angle | MS42: `kf_zw_roz98_vanos_tl__n__lm`, MS43: `ip_iga_ron_98_pl_ivvt__n__maf` | Actual spark advance |
| Knock retard | MS42: `tab_zw_dec_kr_1__n` / `tab_zw_dec_kr_2__n`, MS43: `ip_fac_knk_*` | Knock events = pull timing |
| Coolant temp | `ip_tco__v_tco` | Warm-up and enrichment state |
| Intake air temp | `ip_tia__v_tia` | Heat soak, charge temp compensation |
| Throttle position | `ip_pvs_*` | Load request, WOT detection |
| Battery voltage | `ip_td__vb` (both) | Injector deadtime compensation |
| VANOS intake/exhaust | MS42: `kf_vanos_ein/aus_*`, MS43: `ip_cam_sp_in/ex_*` | Cam timing vs target |
| Idle speed | `ip_n_sp_is__tco` | Idle stability |

#### Holden VY V6 (ADX or EFILive channels):
| Channel | XDF Parameter Link | What AI Checks |
|---|---|---|
| RPM | axis — all tables | Operating point |
| CYLAIR (mg/cyl) | load axis | Load identification |
| Spark advance | Main Spark Tables | Timing vs knock |
| Knock retard | Knock Retard Scalar | Active knock response |
| O2 voltage / wideband | Commanded AFR | Fueling accuracy |
| Coolant temp | CTS tables | Warm-up state |
| MAF Hz / MAF g/s | MAF calibration | Airflow accuracy |
| TPS % | PE enable, accel enrichment | Load request |
| Injector PW | Injector tables | Fueling delivery |
| BLM / INT (fuel trims) | Fuel trim tables | Long-term fueling correction |

### 3.2 Analysis Rules the AI Applies

**Knock Analysis:**
- If ANY knock retard > 0 at a logged operating point:
  - Identify the cells in the spark table at that RPM/load
  - Recommend pulling timing by retard amount + 1 degree safety margin
  - Flag as HIGH PRIORITY if knock retard > 3 degrees

**Fueling Analysis (Lambda/AFR):**
- If actual lambda deviates from target by >3% at steady-state:
  - Identify the operating cells
  - If lean (actual > target): flag for enrichment
  - If rich (actual < target): flag for leaning out
  - Cross-reference with fuel trims (BLM/INT) if available
  - If fuel trims are compensating >±10%: base map needs correction

**MAF Accuracy:**
- If fuel trims show a consistent offset across a MAF range:
  - The MAF calibration table (`id_maf_tab`) may need rescaling
  - Calculate correction factor: `new_maf = old_maf × (1 + trim/100)`

**Idle Stability:**
- If RPM variance at idle > ±50 RPM consistently:
  - Check idle air/PWM tables
  - Check ignition timing at idle
  - Check for ICV (idle control valve) response

**Thermal Compensation:**
- Compare hot-soak (IAT > 50°C) performance to cool:
  - If timing pull only occurs at high IAT, charge temp comp needs adjustment
  - If fueling goes rich at high ECT, warmup enrichment tables need trimming

---

## Part 4: AI Agent Workflow — Step by Step

### 4.1 Initial Tune Assessment

```
USER: "Here's my car's datalog and current tune. What needs fixing?"

AI ACTIONS:
1. preflight --xdf tune.xdf --bin tune.bin
2. ingest-log --log datalog.csv --xdf tune.xdf --format tunerpro
3. compare-log --xdf tune.xdf --bin tune.bin --log datalog.csv --map "Spark Table"
4. compare-log --xdf tune.xdf --bin tune.bin --log datalog.csv --map "Fuel Map"
5. Analyze knock events, fueling errors, idle stability
6. Report findings to user with specific recommendations
```

### 4.2 Apply Recommended Changes

```
USER: "Fix the knock issue at 3200-4800 RPM"

AI ACTIONS:
1. show-map --xdf tune.xdf --bin tune.bin --map "ip_igab__n__maf"
2. Identify rows 5-8 (3200-4800 RPM region) from axis labels
3. Calculate new values: current minus (knock_retard + 1.0)
4. Generate batch CSV with proposed changes
5. Show user the proposed changes for approval
6. batch --xdf tune.xdf --bin tune.bin --csv proposed_changes.csv
7. diff --bin-a tune.bin --bin-b output/tune_batch_XXXXXXXX.bin
8. Report: "Pulled 2-3 degrees in rows 5-8, cols 6-10. New BIN saved."
```

### 4.3 Verify After Re-Log

```
USER: "Here's the new log after flashing. Did the changes work?"

AI ACTIONS:
1. ingest-log --log new_datalog.csv --xdf tune.xdf --format tunerpro
2. compare-log --xdf tune.xdf --bin tune_v2.bin --log new_datalog.csv --map "Spark Table"
3. Check: any knock events remaining?
4. Check: did timing retard decrease or disappear?
5. Check: did fueling stay on target?
6. Report: "Knock events reduced from 12 to 0 in target region. Fueling stable.
   Recommend: hold current values. Optional: try adding 0.5 deg back in low-knock cells."
```

### 4.4 Iterative Refinement

The AI tracks the history of changes across sessions:
```
Session 1: Factory bin → v2 (knock fix: -2 deg spark rows 5-8)
Session 2: v2 → v3 (fuel trim correction: MAF rescale +4% at 200-400 kg/h)
Session 3: v3 → v4 (idle stability: ISA PWM +5% at 85-95°C coolant)
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

1. **NEVER flash a BIN without checksum verification** — the CLI editor does not compute ECU checksums. The user must verify/fix checksums with their flash tool before flashing.

2. **NEVER modify original BIN files** — all changes go to timestamped output copies.

3. **NEVER auto-apply changes without user review** — always show proposed changes and wait for confirmation.

4. **NEVER port code patches** — patches are firmware-version-specific binary modifications. Only calibration data (tables/scalars) can be ported.

5. **NEVER change MAF calibration without explicit user request** — MAF tables are sensor-specific calibrations. Wrong MAF cal = wrong fueling everywhere.

6. **NEVER change injector characterization without hardware info** — injector deadtime and flow rate depend on physical injector specs.

7. **Maximum timing change per iteration: 3 degrees** — never add more than 3 degrees spark advance in a single tuning session. Pull timing is unlimited (safety direction).

8. **Maximum fueling change per iteration: 5%** — never lean out more than 5% in a single session. Enrichment is unlimited (safety direction).

9. **Always log every change** — every edit must have a corresponding log entry.

10. **Always run preflight before any edits** — catch address errors and mismatches before writing bytes.

---

## Part 8: Channel-to-Parameter Mapping Files

Pre-built mapping files tell the AI which log channel corresponds to which XDF parameter. These live in `mappings/`:

### Format
```csv
log_channel,xdf_parameter,type,notes
RPM,,axis,"Row axis for all speed-indexed tables"
MAF (kg/h),id_maf_tab,reference,"MAF calibration output — matches load axis"
Lambda,ip_lam_i__n__maf,compare,"Compare actual vs table target"
Knock Retard,ip_fac_knk_0__n__maf,flag,"Non-zero = knock event at this cell"
Spark Advance,ip_igab__n__maf,compare,"Compare actual vs table commanded"
Coolant (°C),,axis,"Column axis for temp-indexed tables"
TPS %,,axis,"Axis for throttle-indexed tables"
Battery V,ip_td__vb,compare,"Injector deadtime compensation"
```

- `type=axis` — this channel is used to locate table cells (not compared directly)
- `type=compare` — compare log value vs table value at that operating point
- `type=reference` — the table defines the calibration for this measurement
- `type=flag` — non-zero/non-default = anomaly to investigate

### Per-Platform Files Needed
- `mappings/ms42_tunerpro_channels.csv` — BMW MS42 ADX → XDF mapping
- `mappings/ms43_tunerpro_channels.csv` — BMW MS43 ADX → XDF mapping
- `mappings/vy_v6_tunerpro_channels.csv` — Holden VY ADX → XDF mapping
- `mappings/vy_v6_efilive_channels.csv` — Holden VY EFILive → XDF mapping

---

## Appendix A: AI Agent Session Prompt Template

```
You have access to cli_map_editor.py in the tunerpro-xdf-bin-cli-map-editor repo.
This tool reads and writes ECU calibration data using XDF definitions and BIN firmware files.

WORKFLOW (always follow in order):
1. preflight — validate XDF+BIN compatibility
2. ingest-log — parse the datalog CSV (when a log is provided)
3. list-maps — understand available maps and current values
4. show-map / show-scalar — inspect specific tables before any changes
5. compare-log — overlay log data on calibration tables to find issues
6. Analyze and report findings to the user
7. Propose changes as a batch CSV — show to user for approval
8. batch — apply approved changes
9. diff — verify byte-level changes are correct
10. Review the log file to confirm all changes are recorded

SAFETY:
- NEVER flash without checksum verification
- NEVER modify original BIN files
- NEVER auto-apply without user approval
- Max +3 degrees timing per session
- Max -5% fueling (lean direction) per session (could be set to a higher limit if user requests.)
- Always run preflight first
- Always show-map before editing

FILE PATHS:
- XDF: [user provides]
- BIN: [user provides]
- LOG: [user provides]
- Output: ./output/ (auto-created, timestamped)
```

---

## Appendix B: Example Full Tuning Session

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
  Pull timing in knock-affected cells:
    rows 5-7, cols 7-8: current 30-32° → reduce to 28-29° (pull 2-3°)
    rows 8-10, cols 8-9: current 32-34° → reduce to 29-31° (pull 3-4°)
  
  Fueling is 4% rich at WOT — leave it for now, slight rich is safe.
  After knock fix, re-log and check if timing stabilizes.

USER: Go ahead with the spark fix.

> batch --xdf tune.xdf --bin tune.bin --csv spark_fix_v2.csv
  Applied 12 cell changes to ip_igab__n__maf
  Saved: output/tune_batch_20260304_143022.bin
  Log:   output/tune_batch_20260304_143022.log

> diff --bin-a tune.bin --bin-b output/tune_batch_20260304_143022.bin
  Changed bytes: 12
  All changes in range 0x4F2B5-0x4F2E0 (ignition table region)

DONE: New BIN ready. Flash with TunerPro after verifying checksums.
      Re-log at same conditions and provide new datalog for verification.
```
