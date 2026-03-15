# KingAI CLI Map Editor — AI-Friendly XDF + BIN Editor

**Version:** 1.0.0  
**Author:** Jason King (KingAiCodeForge)  
**Copyright:** (c) 2025 KingAI Pty Ltd

---

## Verified Test Results (March 2026)

All commands tested against real XDF+BIN pairs from three ECU platforms:

| Platform | XDF | Constants | Tables | Flags | Patches | BIN Size |
|----------|-----|-----------|--------|-------|---------|----------|
| **BMW MS42 0110C6** | Siemens_MS42_0110C6_ENG_512K_v1.1.xdf | 1,384 | 597 | 0 | 0 | 512KB |
| **BMW MS43 430069** | Siemens_MS43_430069_512K_1.1.3v.xdf | 2,256 | 1,454 | 0 | 0 | 512KB |
| **Holden VY V6 $060A** | VX VY_V6_$060A_Enhanced_v2.09a.xdf | 1,310 | 330 | 351 | 3 | 128KB |

**Commands verified:**
- `show-map` — MAF table `id_maf_tab` (256x1, equation `0.015625*X`, values in kg/h) ✓
- `edit` — 3-cell write: rows 5-7 of `id_maf_tab`, old_raw 317/330/343 → new_raw 384 ✓
- `diff` — Exactly 3 bytes changed at file offsets 0x497AE-0x497B2 (XDF addr + BASEOFFSET 0x48000) ✓
- `preflight` — VY V6: 330 tables OK, 3 benign overlaps (multi-view MAF + adaptive spark) ✓
- `port` — Ignition table `ip_iga_maf_n__n__maf` from M52TUB28→M52TUB25 BIN: 48 cells, 32 bytes changed ✓
- MS42↔MS43 common tables: **410 exact name matches** (69% of MS42 tables directly portable)

---

## What This Is

A strict, deterministic CLI tool for editing ECU calibration data (BIN files) using XDF definition files. Every command is predictable, every change is logged, and original files are never modified.

Built specifically for AI agent workflows — Copilot, Claude, ChatGPT, or any LLM that can run shell commands. The agent reads maps, edits cells, ports calibrations between firmware versions, and reviews diffs, all through structured CLI output that's easy to parse programmatically.

### Why This Exists

Every ECU tuning tool available today is GUI-based. None expose a CLI or API that an AI agent can call:

| Tool | Cost | Limitation |
|------|------|-----------|
| **WinOLS** | ~$600+ license | Proprietary, Windows GUI only, no CLI/API |
| **ECM Titanium** | ~$400+ | GUI with driver database, no scripting |
| **HP Tuners** | $300-900+ hardware | Vendor-locked to GM/Ford/Chrysler, GUI only |
| **EFILive** | $600-1000+ hardware | GUI only, annual subscriptions |
| **Swiftec** | Subscription | Dashboard GUI, no programmatic access |
| **BitEdit** | Subscription | Binary editor, no XDF support |
| **TunerPro** | Free | Full XDF+BIN GUI, but no CLI, no API, no scripting |
| **RomRaider** | Free/OSS | Subaru-only, Java GUI, mostly inactive |

The few open-source alternatives are read-only or incomplete:

| Tool | What It Does | What It Can't Do |
|------|-------------|-----------------|
| **Atlas** (MOTTechnologies) | Open-source calibration app | A2L-focused, not XDF, early development |
| **ecushark/serpentine** | Web-based XDF viewer | Read-only, no BIN editing, no write-back |
| **xdfbinext** (jtownson) | XDF+BIN diff reports, MHD logging | Read-only comparison, no editing |
| **OpenECU Calibrator** | CAN-based real-time calibration | Requires specific hardware, not XDF-based |

None of these can read a fuel map from a BIN, change three cells, write back a new timestamped BIN with a TunerPro-compatible edit log, and port calibration between firmware versions — all from a command line that an AI agent can operate. This tool can.

### What About "ChatGPT Tuning"?

There are ChatGPT tuning experiments across YouTube, Reddit, HP Tuners forums, and Holley forums. Some are custom GPT chatbots ("Car ECU Tuning" GPT, Gen4 V8 E38 tuning bots). Some are people pasting datalogs into ChatGPT and asking for calibration advice. They all share the same fundamental limitation: **the AI has no access to the actual BIN data**.

These are just ChatGPT with some system instructions and maybe a knowledge base file uploaded. The accuracy is entirely dependent on the LLM's general knowledge, which is unreliable for safety-critical calibration values. The chatbot can discuss tuning concepts in general terms — what a MAF transfer function does, why ignition timing matters — but it can't read what's actually in your ECU right now. It can't verify values against the binary. It can't write changes back. And when it gives bad advice — and forum users have reported duty cycle pressures, boost targets, and ignition timing suggestions that would damage engines — there's no validation layer to catch the error before it reaches the ECU. It's conversation, not tooling.

### What About ChatGPT Agent Mode or Cloud AI Platforms?

ChatGPT in agent mode can execute code. It has sandboxed Ubuntu servers. In theory it could run Python scripts against BIN files. In practice, ECU calibration is a terrible fit for cloud AI:

- **No persistent local context.** Cloud agents spin up disposable environments. They don't have your BIN collection, your XDF library, your datalogs, or any history of what you've already tuned. Every session starts cold. You'd need to upload everything, every time.
- **Error-prone on domain-specific work.** Even with code execution, the LLM still has to write correct XDF parsing logic, handle BASEOFFSET addressing, resolve embedinfo axis links, and get byte-order right. These are hard problems with subtle edge cases. Cloud agents will get things wrong in ways that corrupt calibration data silently.
- **No safety validation.** A cloud agent can't run preflight checks against your specific XDF+BIN pairing, can't verify that a fuel map edit didn't overflow into an adjacent ignition table, and can't cross-reference against your known-good baseline BIN. It's guessing.
- **Same applies to Manus.im and similar orchestration platforms.** They can chain multi-step workflows, but they don't have the domain-specific tooling for ECU work. The XDF format, TunerPro math equations, linked axes, BASEOFFSET modes — none of this exists in their tool libraries.
- **Privacy.** Proprietary calibration data, custom XDFs, and tuning strategies shouldn't be uploaded to third-party cloud servers.

ECU calibration is a safety-critical domain. A cloud AI estimating spark advance values without reading the actual binary is dangerous. The model needs deterministic tools with guaranteed correct address resolution, proper byte-order handling, and logged before/after values — not probabilistic text generation hoping it got the offset right.

### The Right Architecture: Local Agent + Deterministic CLI

The practical approach is a local AI agent with direct terminal access to this CLI tool. That means VS Code with Copilot or Claude, a local LLM via Ollama or llama.cpp, or any agent framework that can run shell commands. No API keys required for the tool itself — bring whatever model you want.

The workflow:

1. **Agent reads the maps** — `show-map` returns real values extracted from the BIN using the XDF's math equations, not hallucinated guesses from training data
2. **Agent builds a plan** — based on the actual current calibration state, with full awareness of what every table contains right now
3. **Agent writes changes** — `edit` or `batch` with deterministic inverse math, logging old and new values (both raw bytes and real-world units)
4. **Agent validates** — `preflight` catches address errors and overlaps, `diff` proves exactly which bytes changed and nothing else
5. **Human reviews** — edit logs are TunerPro-compatible CSV, fully inspectable before anything gets flashed

A model with a high context window and well-defined instructions can hold the full map state, the edit plan, and the validation results simultaneously. It generates a report of every change and why — creating an auditable trail that a human tuner reviews before flashing. This is how AI-assisted tuning should work: the AI handles the tedious cross-referencing and calculation, the human makes the final call.

Live tuning — an agent correcting values in real-time while driving based on datalog feedback — is technically possible with this architecture, but requires a validated calibration plan and robust safety bounds. Human-in-the-loop is essential until models are trained on real-world sensor data and understand cause-and-effect relationships in combustion, not just statistical patterns from text. The model needs to know what's up and what's down, what positive and negative mean for each parameter, and what happens when you change one value on everything else in the system.

### Who Is This For?

This is not a consumer product. It's infrastructure — the open-source backbone for the next generation of ECU calibration tools.

**Developers and integrators** — Fork this, add your own LLM credentials and frontend, wrap it in a REST API or MCP tool server, and build a commercial or open-source tuning platform on top. The CLI produces structured output that's trivial to integrate.

**Tuners and researchers** — Use it today with VS Code + Copilot or any terminal-capable LLM to read, analyze, compare, and modify calibrations without touching a GUI. Works on any platform with any XDF+BIN pair.

**Will commercial vendors like HP Tuners or Alientech use this?** — Probably not directly. They build in C/C++ with encrypted proprietary libraries and hardware-locked license dongles. But their users will. The community of tuners, researchers, and hobbyists who can't afford thousands in hardware and annual subscriptions — or who need programmable access that vendor tools deliberately don't provide — is exactly who benefits from open-source tooling. And developers building the next WinOLS alternative now have a proven read/write/port/diff engine they don't have to write from scratch.

### Parsing Engine

This tool reuses the proven **UniversalXDFExporter** engine ([TunerPro-XDF-BIN-Universal-Exporter](https://github.com/KingAiCodeForge/TunerPro-XDF-BIN-Universal-Exporter)) for all XDF parsing, BIN reading, math evaluation, BASEOFFSET handling, embedinfo axis linking, and linked variable resolution. Improvements flow both ways — fixes in the exporter get pulled here, and vice versa. The CLI editor adds write-back, porting, cross-platform table matching, and TunerPro-compatible edit logging on top.

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

### `batch` — Apply edits from CSV
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

### `save` — Persist temp edits
```
python cli_map_editor.py save --bin fw.bin --output-dir ./output
```
Saves the `.edited.tmp` to a timestamped final file.

### `export` — Snapshot BIN+XDF data
```
python cli_map_editor.py export --xdf def.xdf --bin fw.bin --output-dir ./export
```
Creates TXT, JSON, and MD exports of every map/scalar/flag.

### `port` — Port maps between firmware
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

---

## Safety Rules

1. **Never modify original BIN files** — all writes go to temp or timestamped outputs
2. **Run `preflight` before any edits** — catches address errors, overlaps, mismatches
3. **Run `show-map` before editing** — verify you're changing the right table
4. **Review logs after every save** — logs are TunerPro-compatible CSV
5. **Do NOT flash without checksum verification** — this tool does not compute ECU checksums
6. **Patch tables are SKIP only** — never port code patches between firmware versions

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

When using this tool from an AI agent (Copilot, Claude, etc.), use this session instruction:

```
Context: Repo has cli_map_editor.py in tunerpro-xdf-bin-cli-map-editor/.
XDF and BIN files are provided by the user.
Always run these commands in order:
1. preflight — validate XDF+BIN
2. list-maps — understand available maps
3. show-map — verify target table before editing
4. edit/batch/port — make changes
5. Review the log file after save
Never flash a BIN without checksum verification.
All outputs are timestamped and logged.
```

---

## Technical Details

### Inverse Math (Real → Raw Conversion)
When writing a real-world value (e.g., 13.5 AFR), the tool needs to compute 
the raw byte value that the ECU stores. It does this by:

1. **Affine detection**: Evaluate the equation at X=0 and X=1000 to derive 
   `a` and `b` from `real = a*X + b`, then invert: `X = (real - b) / a`
2. **Numerical search**: If affine detection fails, search raw values 0–65535 
   to find the closest match
3. **Round-trip verification**: After computing raw, verify by re-evaluating 
   the forward equation

### BASEOFFSET Handling
Inherited from UniversalXDFExporter — handles both `subtract=0` (file has 
header before calibration) and `subtract=1` (ECU addresses mapped to file) 
automatically.

### Axis Linking (embedinfo)
MS42/MS43 XDFs use embedinfo to link axis breakpoints to shared tables. 
The exporter resolves these automatically via uniqueid index.

---

## Acknowledgments

**Mark Mansur** — creator of [TunerPro RT](http://www.tunerpro.net/). TunerPro has been the go-to free ECU tuning platform for over two decades. The XDF definition format that this entire tool ecosystem is built on exists because Mark designed it and maintained TunerPro through years of community use across every platform from OBD1 GM trucks to Siemens MS4x BMW DMEs. Without TunerPro and the XDF format, none of this would exist. If you're in a position to support his work, get the registered edition.

**The XDF community** — the tuners, reverse engineers, and enthusiasts who have built, refined, and shared XDF definition files for hundreds of ECU platforms over the years. Every verified address, every corrected axis link, every documented equation in an XDF represents hours of someone's time with a hex editor and a running engine. This tool stands on that collective work.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

Copyright (c) 2025-2026 KingAI Pty Ltd — Jason King
