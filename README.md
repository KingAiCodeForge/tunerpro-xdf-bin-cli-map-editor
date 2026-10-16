# KingAI CLI Map Editor — AI-Friendly XDF + BIN Editor

**Version:** 1.1.0
**Author:** Jason King (KingAiCodeForge)  
**Copyright:** (c) 2025 KingAI Pty Ltd

**Using Claude Code or Codex?** Start with [AGENTS.md](AGENTS.md) for the read-only-first workflow, exact CLI commands, refusal rules and review report. Terminal execution and a matching XDF/BIN pair are required; the source ZIP by itself cannot tune a car.

---

## CLI 1.1.0 release boundary and dependency review

This is an offline file editor, not a flasher or a vehicle-safety certification.
This branch proposes Universal Exporter **3.7.3** at the MIT-licensed commit
`85a02600a288c1861cda8e772bdd6e7a081be955`. No sibling checkout is needed.
**Before merging or describing this as a tested release, run the installed-package,
unit, Windows/Linux and exact-definition regression checks.** The historical
validation receipts below relate to older dependency revisions.
Python 3.10+ and Git are required to install the pinned dependency:

```console
python -m pip install .
kingai-map-editor --help
```

| Capability | Current boundary |
|---|---|
| Read, list, export, diff | Supported XDF forms only; malformed definitions fail closed |
| One-shot table/scalar edits | Integer storage, supported contiguous layout, bounded affine inverse; requires `--autosave --output-dir` |
| Flag edits | Bounded mask updates preserving other bits; requires `--autosave --output-dir` |
| Scoped row/column/cell MATH writes | Refused pending write/log parity tests |
| `batch`, `port`, standalone `save` | Disabled: partial-success and unbound-temp defects reproduced |
| Raw patches | Existing strict v2, exact-hash apply/reverse/verify contract retained |
| Hardware, checksum repair, flashing | Not implemented or certified |

Edits create a new BIN plus project-owned `.log` and detailed CSV. Existing
outputs are never overwritten. Use the previous output BIN as the next input;
there is no persistent temp session. Review the actual rounded value and byte
diff: an engineering value may quantize to the nearest representable integer.
Float writes, nonlinear inverse math and unsupported storage/strides are refused.

`export` writes into a newly created timestamped snapshot subdirectory and
refuses a directory collision. An I/O failure is reported as a failure; retain
any incomplete output for diagnosis and do not use it as a validated BIN.

```console
kingai-map-editor edit-scalar --xdf definition.xdf --bin original.bin --name "Example scalar" --value 10 --autosave --output-dir output
kingai-map-editor diff --bin-a original.bin --bin-b output/REPLACE_WITH_ACTUAL_OUTPUT.bin --xdf definition.xdf
```

TunerPro RT **5.00.10305** (21 January 2026) was the current official download
and installed reference at this review. See the
[official download page](https://www.tunerpro.net/downloadApp.htm). That version
check does not prove every editor write agrees with native TunerPro. Validate
each exact XDF/BIN pair independently; do not infer support from an ECU name.

Portable synthetic tests run against the installed editor and pinned exporter,
away from both source trees. CI covers Windows/Linux and Python 3.10/3.13 when
GitHub Actions can run. A local pass is not a cloud-CI or hardware pass.

The sections below retain historical examples and design context. Where they
describe batch, port, temp sessions or broader compatibility, this current
release boundary takes precedence; those operations are not enabled.

## Compatibility Snapshot (March 2026)

These are local regression fixtures used while developing the CLI. Treat them
as a snapshot, not a guarantee that every later XDF or TunerPro build behaves
the same way.

| Platform | XDF | Constants | Tables | Flags | Patches | BIN Size |
|----------|-----|-----------|--------|-------|---------|----------|
| **BMW MS42 0110C6** | Siemens_MS42_0110C6_ENG_512K_v1.1.xdf | 1,384 | 597 | 0 | 0 | 512KB |
| **BMW MS43 430069** | Siemens_MS43_430069_512K_1.1.3v.xdf | 2,256 | 1,454 | 0 | 0 | 512KB |
| **Holden VY V6 $060A** | VX VY_V6_$060A_Enhanced_v2.09a.xdf | 1,310 | 330 | 351 | 3 | 128KB |

**Important:** the VY/VX Enhanced `v2.09` family needs fresh verification
against current TunerPro behavior and the current public XDFs. Do not make a
compatibility claim for that XDF until the regression set proves it.

**Commands covered in the snapshot:**
- `show-map` — MAF table `id_maf_tab` (256x1, equation `0.015625*X`, values in kg/h) ✓
- `edit` — 3-cell write: rows 5-7 of `id_maf_tab`, old_raw 317/330/343 → new_raw 384 ✓
- `diff` — Exactly 3 bytes changed at file offsets 0x497AE-0x497B2 (XDF addr + BASEOFFSET 0x48000) ✓
- `preflight` — VY V6: 330 tables OK, 3 benign overlaps (multi-view MAF + adaptive spark) ✓
- `port` — Ignition table `ip_iga_maf_n__n__maf` from M52TUB28→M52TUB25 BIN: 48 cells, 32 bytes changed ✓
- MS42↔MS43 common tables: **410 exact name matches** (69% of MS42 tables directly portable)

---

## What This Is

A strict, deterministic CLI tool for reading, auditing, editing, and porting ECU calibration data (BIN files) using TunerPro XDF definition files. Every command is predictable, every change is logged, and original files are never modified.

The parser is intended to be ECU-family neutral, but compatibility must be proven per XDF/BIN pair. BMW MS42/MS43/MS45, Holden/GM V6/V8, Ford/Barra-adjacent Bosch work, and other XDF-defined projects can use different addressing, axis, math, and patch conventions. This tool does not replace TunerPro validation, and it does not handle checksums, RSA signing, flashing safety, or every XDF variation by itself.

### XDF Iteration + Reverse Engineering Workflow

This tool is also useful while building or repairing XDFs during reverse engineering. A practical loop is:

1. Load the firmware in Ghidra/IDA and use Ghidra `analyzeHeadless` to export labels, xrefs, immediate-hit windows, and function context.
2. Add or adjust candidate XDF entries from RR/A2L/DAMOS/ASM evidence.
3. Run this CLI/exporter against the candidate XDF + matching BIN.
4. Check whether axes, dimensions, units, endian, signedness, and table values look sane.
5. Diff the export against known-good stock/stage files and repeat until the XDF is stable.

That makes it a fast feedback tool for XDF development: disassembly finds likely addresses and code-use, while the exporter shows whether the candidate XDF renders consistently as editable calibration data. Final truth still comes from comparing against TunerPro, known-good bins, and platform-specific test fixtures.

Built for AI agent workflows with terminal access. On supported XDF/BIN pairs an agent can inspect maps, run preflight, export values, review bounded changes and compare BINs. The `port` and `batch` commands are disabled in this release.

### Why This Exists

Many ECU tuning tools already have their own scripting, programming,
diagnostic or file interfaces. This project's specific contribution is an
auditable, offline command-line workflow using TunerPro XDF definitions and
matching raw BIN files. Its scope and compatibility are narrower than the
broader ecosystem of ECU calibration, flashing and logging applications.

It complements, rather than replaces, software used for ECU acquisition,
checksum repair, flashing, logger integration and professional calibration
validation. Commercial tuning workshops may use the MIT-licensed source,
subject to the terms of any third-party code and data they use.

### What About "ChatGPT Tuning"?

An AI assistant without access to the exact BIN, matching definition and an
execution environment cannot directly inspect or verify calibration bytes.
A terminal-enabled agent can run file-aware tools when those inputs are made
available, whether locally or in an authorised remote environment.

Access to a file alone does not establish valid map semantics or a safe tune.
The definition may be incorrect, a map may be unverified, and a technically
successful edit may still require checksum correction, legal review and real
engine testing. Treat LLM interpretation as a proposal and the CLI report
as file-level evidence, not a substitute for professional calibration.

Use a local execution environment when customer data must remain on site.
If a remote assistant is used, confirm the data owner permits those uploads.

### The Right Architecture: Agent + Deterministic CLI

The tool can be operated by a human or by any coding agent with an authorised
terminal, Python environment and access to the files. The CLI itself needs no
LLM API key. See [AGENTS.md](AGENTS.md) for specific steps and guardrails.

1. Run `preflight` against the exact XDF and raw BIN and inspect all errors.
2. Run `list-maps` and `show-map` or `show-scalar` to read actual values.
3. Independently verify the chosen object's address, axes, conversion and meaning.
4. If the user approves a specific supported edit, write a separate BIN with
   `--autosave --output-dir`; never modify the original file.
5. Reload and compare the result using `diff`, audit the output logs, and report
   hashes, changed offsets and unresolved checks to the human reviewer.

Unsupported layouts and operations must be refused. `batch`, `port` and
standalone `save` are intentionally disabled. No CLI result certifies that a
calibration is mechanically safe or ready to flash.

### Who Is This For?

This is not a consumer product. It's infrastructure — the open-source backbone for the next generation of ECU calibration tools.

**Developers and integrators** — Fork this, add your own LLM credentials and frontend, wrap it in a REST API or MCP tool server, and build a commercial or open-source tuning platform on top. The CLI produces structured output that's trivial to integrate.

**Tuners and researchers** - Use it today with VS Code + Copilot or any terminal-capable LLM to inspect and compare calibration data. Editing/write-back should stay inside a verified fixture set until the target XDF/BIN pair passes preflight, export sanity checks, TunerPro comparison, and human review.

**Will commercial vendors like HP Tuners or Alientech use this?** — Probably not directly. They build in C/C++ with encrypted proprietary libraries and hardware-locked license dongles. The likely audience is developers, tuners, researchers, and hobbyists who need programmable access for verified XDF/BIN pairs and want an auditable local toolchain.

### Parsing Engine

This tool reuses the **UniversalXDFExporter** engine ([TunerPro-XDF-BIN-Universal-Exporter](https://github.com/KingAiCodeForge/TunerPro-XDF-BIN-Universal-Exporter)) for XDF parsing, BIN reading, math evaluation, BASEOFFSET handling, embedinfo axis linking, and linked variable resolution. Improvements flow both ways — fixes in the exporter get pulled here, and vice versa. The CLI editor adds write-back, porting, cross-platform table matching, and TunerPro-style edit logging on top.

---

## File Structure

```
tunerpro-xdf-bin-cli-map-editor/
├── cli_map_editor.py                              # Main CLI tool
├── tunerpro_exporter_for_cli_editor_version.py     # XDF/BIN parsing engine (cloned from exporter)
├── porting_templates.py                            # Porting classification rules
├── README.md                                       # This file
├── FUTURE_PATHS_AND_IDEAS.md                       # Roadmap and integration ideas
├── LICENSE                                         # MIT License
├── AI_TUNING_PLAN.md                               # AI agent tuning workflow plan
├── HOLDEN_AI_TUNING_GUIDE.md                       # Holden effect tests and patch rebuild prompts
├── BMW_MS42_MS43_MS43X_AI_TUNING_GUIDE.md          # BMW effect tests and patch rebuild prompts
├── PATCH_REBUILD_REGISTER.md                       # Current legacy patch/formula rebuild queue
├── GENERAL_INFO_FOR_MS42.MD                        # MS42 ECU specs, maps, firmware, flash tools
├── GENERAL_INFO_FOR_MS43.MD                        # MS43 ECU specs, maps, firmware, flash tools
├── GENERAL_INFO_FOR_MS45.MD                        # MS45 ECU specs, maps, firmware, flash tools
├── GENERAL_INFO_FOR_vy_V6_ENHANCED_L36.MD          # VY V6 ECU specs, OS IDs, XDFs, Enhanced mod
├── mappings/                                       # Cross-platform table mapping CSVs
│   ├── ms42_to_ms43_common_tables.csv             # 410 common tables (auto-generated)
│   └── vs_to_vy_v6_mapping.csv                    # Holden VS→VY name mapping
└── output/                                         # Auto-created output directory
    ├── <name>_edited_<YYYYMMDD_HHMMSS>.bin
    ├── <name>_edited_<YYYYMMDD_HHMMSS>.log
    ├── <name>_ported_<YYYYMMDD_HHMMSS>.bin
    ├── <name>_ported_<YYYYMMDD_HHMMSS>.log
    ├── <name>_batch_<YYYYMMDD_HHMMSS>.bin
    └── <name>_batch_<YYYYMMDD_HHMMSS>.log
```

---

## Naming Conventions

### Output Files
| File Type | Pattern | Example |
|-----------|---------|---------|
| Edited BIN | `<stem>_edited_<YYYYMMDD_HHMMSS>.bin` | `ms42_edited_20260303_151230.bin` |
| Ported BIN | `<stem>_ported_<YYYYMMDD_HHMMSS>.bin` | `ms43_ported_20260303_151230.bin` |
| Batch BIN | `<stem>_batch_<YYYYMMDD_HHMMSS>.bin` | `ms42_batch_20260303_151230.bin` |
| Edit Log | Same stem as BIN, `.log` extension | `ms42_edited_20260303_151230.log` |

### Log Format (TunerPro-Compatible CSV)
```csv
MAP_NAME,ROW,COLUMN,ADDRESS,OLD_RAW,NEW_RAW,OLD_REAL,NEW_REAL
Fuel Map,1,1,0x1A3F,128,132,12.50,13.00
Fuel Map,1,2,0x1A41,130,134,13.00,13.50
```

### Rules
- Original BIN files are **never modified**
- Temp files use `.edited.tmp` extension
- Output directory defaults to `<bin_dir>/output/` (auto-created)
- BIN and LOG files share the same timestamp to pair them
- Logs are written immediately when saving

---

## Commands

### `list-maps` — Show all maps in an XDF
```
python cli_map_editor.py list-maps --xdf def.xdf --bin fw.bin
```
Lists all tables, scalars, flags, and patches with their addresses, dimensions, and equations.

### `show-map` — View a table's data
```
python cli_map_editor.py show-map --xdf def.xdf --bin fw.bin --map "Fuel Map"
```
Shows the full data matrix with axis labels, units, and dimensions.

### `show-scalar` — View a scalar's value
```
python cli_map_editor.py show-scalar --xdf def.xdf --bin fw.bin --name "RPM Limit"
```

### `edit` — Edit table cells
```
# Single cell
python cli_map_editor.py edit --xdf def.xdf --bin fw.bin --map "Fuel Map" --rows 1 --cols 1 --value 13.0

# Range of cells (rows 1-3, cols 1-2)
python cli_map_editor.py edit --xdf def.xdf --bin fw.bin --map "Fuel Map" --rows 1-3 --cols 1-2 --value 13.0 --save

# Raw mode (write raw integer, bypass conversion)
python cli_map_editor.py edit --xdf def.xdf --bin fw.bin --map "Fuel Map" --rows 1 --cols 1 --value 132 --raw --save
```
- `--rows` and `--cols` accept single number or range (e.g., `1-5`), 1-based
- `--save` flag saves immediately to output directory
- Without `--save`, writes to `.edited.tmp` for review

### `edit-scalar` — Edit a scalar value
```
python cli_map_editor.py edit-scalar --xdf def.xdf --bin fw.bin --name "RPM Limit" --value 7200 --save
```

### `batch` — Disabled; historical CSV design
```
python cli_map_editor.py batch --xdf def.xdf --bin fw.bin --csv edits.csv
```
CSV format:
```csv
map,row,col,value
Fuel Map,1,1,13.0
Fuel Map,1,2,13.5
Ignition Map,3,4,28.0
RPM Limit,,,7200
```
Scalars don't need row/col. Maps without a row/col will be treated as scalars.

### `save` — Disabled; unbound temp sessions are not supported
```
python cli_map_editor.py save --bin fw.bin --output-dir ./output
```
Saves the `.edited.tmp` to a timestamped final file.

### `export` — Snapshot BIN+XDF data
```
python cli_map_editor.py export --xdf def.xdf --bin fw.bin --output-dir ./export
```
Creates TXT, JSON, and MD exports of every map/scalar/flag.

### `port` — Disabled; historical interface only
```
# Auto-match by name
python cli_map_editor.py port --src-xdf ms42.xdf --src-bin ms42.bin --dst-xdf ms43.xdf --dst-bin ms43.bin

# Single map
python cli_map_editor.py port --src-xdf ms42.xdf --src-bin ms42.bin --dst-xdf ms43.xdf --dst-bin ms43.bin --map-name "Fuel Map"

# With mapping CSV and AFR/Lambda conversion
python cli_map_editor.py port --src-xdf ms42.xdf --src-bin ms42.bin --dst-xdf ms43.xdf --dst-bin ms43.bin --map-csv mapping.csv --stoich 14.7
```

### `preflight` — Validate XDF+BIN before editing
```
python cli_map_editor.py preflight --xdf def.xdf --bin fw.bin
```
Checks: address validity, table overlap, read access, BASEOFFSET handling.

### `diff` — Byte-level diff between BINs
```
python cli_map_editor.py diff --bin-a original.bin --bin-b edited.bin
```

### `verify-raw-patch` / `apply-raw-patch` — Strict v2 ASM/raw patches

```powershell
# Read-only: validates and stages the result in memory; writes no files
python cli_map_editor.py verify-raw-patch `
  --bin exact-base.bin --manifest strict-patch.json

# Forward apply: creates a new BIN and JSON receipt
python cli_map_editor.py apply-raw-patch `
  --bin exact-base.bin --manifest strict-patch.json --output new-patched.bin

# Reverse uses the patched hash/bytes and must restore the exact base hash
python cli_map_editor.py apply-raw-patch --reverse `
  --bin new-patched.bin --manifest strict-patch.json --output restored-base.bin
```

Raw code patches remain separate from XDF map editing and `port`. Manifests must
use `kingai.raw-patch.v2` and literal `file_offset` addresses; v1 is rejected
because it lacks the required target layout, generic identity probes and named
immutable ranges. A concise generic shape is:

```json
{
  "schema": "kingai.raw-patch.v2",
  "patch_id": "<ecu>-<software>-<feature>-v1",
  "address_space": "file_offset",
  "target": {
    "ecu": "<exact ECU family>",
    "software_id": "<exact software/OS ID>",
    "image_layout": "<layout and address basis>",
    "architecture": "<CPU architecture>",
    "parent_filename": "<exact-parent.bin>",
    "size": 524288,
    "base_sha256": "<64 hex>",
    "patched_sha256": "<64 hex>",
    "identity_probes": [
      {"name": "software identity", "offset": "0x...", "expected_hex": "<literal hex>"}
    ]
  },
  "chunks": [
    {
      "name": "exact hook or payload",
      "kind": "code",
      "offset": "0x...",
      "expected_hex": "<literal original bytes>",
      "replacement_hex": "<literal replacement bytes>"
    }
  ],
  "immutable_ranges": [
    {"name": "untouched code", "offset": "0x...", "length": "0x...", "sha256": "<64 hex>"}
  ],
  "checksum": {
    "profile": "<registered in-process profile>",
    "covered_ranges": [{"offset": "0x...", "length": "0x..."}],
    "stored_ranges": [{"offset": "0x...", "length": "0x..."}],
    "parameters": {"<profile-specific key>": "<value>"}
  }
}
```

The checksum object is optional. If present, its profile must be registered in
the CLI's trusted in-process verifier registry; otherwise validation fails
closed. A manifest can never supply or execute a command, and this path does
not repair checksums. The registered verifier checks both staged input and
output against the declared contract. Whole-image SHA-256 remains critical,
especially for payload bytes outside the ECU's own checksum coverage.

Registered profiles currently include:

- `bmw-ms42-0110c6-crc16-v1` — exact 512 KiB `0110C6` boot, calibration and
  program CRC16 records;
- `bmw-ms43-430069-crc16-v1` — exact 512 KiB `430069` boot, program and
  calibration CRC16 records only; its two 32-bit additive monitors are
  explicitly outside the profile;
- `bmw-ms43-430069-all-five-checksums-v1` — the same three CRC16 records plus
  the exact program/calibration 32-bit additive monitors, seeds, half-open
  descriptor ranges and invariant metadata block; repair additive records
  first because calibration ADD32 storage is covered by calibration CRC16;
- `holden-vy-060a-92118883-additive16-bypass-aware-v1` — exact 128 KiB
  Enhanced `$060A`/92118883 additive checksum plus the preserved `0xAA` ECU
  checksum-bypass identity byte.

Both commands require the semantic target fields, exact size and whole-image
hash, all identity probes, every original byte, disjoint chunks and named
immutable-range hashes. They reject unknown fields, overlaps, out-of-bounds
ranges and any undeclared change. `verify-raw-patch --reverse` can also prove
the reverse path without writing.

`apply-raw-patch` refuses in-place writes and never overwrites an existing BIN
or receipt. It rereads the new BIN from disk and verifies its bytes and hash
before writing the receipt. The receipt separates a canonical, path-free and
timestamp-free evidence object from run paths and time metadata; only the
canonical object determines the reproducible `evidence_sha256`. Reverse mode
requires the exact patched image and must reproduce the exact base SHA-256.

These checks prove the static byte contract, not instruction semantics or safe
runtime behavior. Code patches still require disassembly review, controlled
bench execution, physical write/readback, recovery proof and vehicle-specific
validation before vehicle use.

---

## Safety Rules

Use the platform guide before asking an AI to propose calibration or patch
changes:

- [`HOLDEN_AI_TUNING_GUIDE.md`](HOLDEN_AI_TUNING_GUIDE.md)
- [`BMW_MS42_MS43_MS43X_AI_TUNING_GUIDE.md`](BMW_MS42_MS43_MS43X_AI_TUNING_GUIDE.md)
- [`PATCH_REBUILD_REGISTER.md`](PATCH_REBUILD_REGISTER.md)

They contain evidence grades, effect-oriented request examples and the rule to
rebuild legacy patches/formulas from the latest disassembly and tracing.

1. **Never modify original BIN files** — all writes go to temp or timestamped outputs
2. **Run `preflight` before any edits** — catches address errors, overlaps, mismatches
3. **Run `show-map` before editing** — verify you're changing the right table
4. **Review logs after every save** — logs are TunerPro-compatible CSV
5. **Do NOT flash without checksum verification** — use a registered exact-profile verifier and require a passing result
6. **Never send patch tables through `port`** — ASM/raw changes require the exact-hash `apply-raw-patch` manifest path and separate code/checksum/recovery proof

---

## AFR / Lambda Handling

| Source Unit | Destination Unit | Action |
|-------------|-----------------|--------|
| AFR | AFR | Direct copy |
| Lambda | Lambda | Direct copy |
| AFR | Lambda | Auto-convert: λ = AFR / stoich |
| Lambda | AFR | Auto-convert: AFR = λ × stoich |
| Mass (mg/st) | Any | MANUAL REVIEW — requires engine params |

Default stoich: 14.7 (configurable via `--stoich`)

Detection heuristics (checks Z-axis output, not axis labels):
- Z-axis unit contains "lambda" → Lambda
- Z-axis unit contains "afr", "air/fuel" → AFR
- Z-axis unit contains "mg/", "g/s", "kg/h", "cylair" → Mass (manual review)
- Table name starts with `id_maf_tab` → Mass (the MAF calibration itself)
- Table name contains "_lam_" → Lambda
- Tables like `ip_iga_maf_n__n__maf` are ignition tables indexed by MAF, **not** mass tables

---

## Agent Prompt Template

Give Claude Code, Codex or another coding agent this instruction, together
with an authorised, matching BIN/XDF pair and an executable local workspace:

```text
Read AGENTS.md and the current release boundary in README.md first.
Default to read-only analysis. Hash the original files.
Run preflight, list-maps and show-map/show-scalar for the exact object.
Show original values, units, axes, addresses, validation errors and unknowns.
Do not guess ECU map locations or tuning targets.
Do not call batch, port or standalone save; those paths are disabled.
Do not modify any file until I approve a named object and numeric value.
For a supported approved edit, use autosave to a new output directory.
Reload, diff, report changed offsets and hashes, and retain logs.
Never claim that checksum handling, flashing or engine safety is certified.
```

## Technical Details

### Inverse Math (Real → Raw Conversion)

The shared bounded expression parser must prove an equation affine before
engineering-value writes are allowed. The inverse is rounded to an integer,
range checked and evaluated with staged dependencies. There is no numerical
search fallback. Unsupported or unstable conversions are refused. `--raw`
does not bypass layout, type, range or scoped-equation restrictions.

### BASEOFFSET Handling
Inherited from UniversalXDFExporter — handles both `subtract=0` (file has 
header before calibration) and `subtract=1` (ECU addresses mapped to file) 
automatically.

### Axis Linking (embedinfo)
MS42/MS43 XDFs use embedinfo to link axis breakpoints to shared tables. 
The exporter resolves these automatically via uniqueid index.

---

## Acknowledgments

**Mark Mansur** — creator of [TunerPro RT](http://www.tunerpro.net/). This project is not affiliated with TunerPro; it exists because TunerPro and the XDF format made community calibration work possible. TunerPro continues to evolve, so this tool should be validated against current TunerPro builds and current XDFs before any compatibility claim is made. If you're in a position to support Mark's work, get the registered edition.

**The XDF community** — the tuners, reverse engineers, and enthusiasts who have built, refined, and shared XDF definition files for hundreds of ECU platforms over the years. Every verified address, every corrected axis link, every documented equation in an XDF represents hours of someone's time with a hex editor and a running engine. This tool stands on that collective work.

---

## License

The editor and the proposed pinned Universal Exporter revision are both
licensed under the **MIT License**, including commercial use. See
[Editor LICENSE](LICENSE) and the
[Exporter licence at the proposed pin](https://github.com/KingAiCodeForge/TunerPro-XDF-BIN-Universal-Exporter/blob/85a02600a288c1861cda8e772bdd6e7a081be955/LICENSE).

This branch has not yet established installed-package or real-definition
parity for the updated dependency. Do not merge the pin change without
regression checks and inspection of third-party code and data licences.

Copyright (c) 2025-2026 KingAI Pty Ltd — Jason King

## Local diff/report integration, 2026-10-07
The selectively imported diff changes add optional JSON/CSV reports, source hashes,
XDF-only filtering, explicit unequal-size reporting and masked-bit-aware flag ownership.
Existing focused editor tests passed: 92, against the declared exporter dependency
f81e0cd6b522b8142e7424774ec068c9bb711792, not an uncommitted local replacement.
The dependency pin is unchanged. Unsupported conversion/edit forms retain existing holds.
Additional local report tests passed 5 cases but one new assertion incorrectly assumed
lowercase SHA256 strings. That supplemental test file is not included in this integration;
the uppercase report value is correct. It remains local pending assertion correction.
No source BIN, tuning dump, hardware output or private local configuration is included.

## Supplemental report regression closure: 2026-10-08

Six supplemental cases cover machine-readable diff hashes/CSV, opt-in unequal-size tails, refusal to overwrite report targets or inputs, duplicate output paths, and masked flag ownership. SHA256 assertions compare parsed fields case-insensitively; the report's uppercase hash format is unchanged. These are generated tiny fixtures, not ECU identity or flash-readiness evidence. The prior hash-test hold is superseded after the focused suite passes.

The declared exporter pin is unchanged. The focused editor suite is also exercised against the revised exporter separately to detect integration regressions; that does not silently update the dependency pin.
`Validation receipt (2026-10-08): 98 focused tests passed against the declared published dependency and 98 passed against revised exporter source. Dependency pin unchanged.`
