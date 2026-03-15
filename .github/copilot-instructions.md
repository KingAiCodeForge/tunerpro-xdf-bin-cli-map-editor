# KingAI CLI Map Editor — AI Agent Instructions

## What This Tool Is

A headless (no GUI) CLI tool for reading and writing ECU calibration data, **designed for AI agents to use autonomously** inside VS Code (GitHub Copilot agent mode, Claude Opus 4.6, or equivalent). The human operator's role is:
- **Guiding** the AI via natural language prompts in VS Code
- **Reviewing** logs, exported data, and end results
- **Handling hardware** (flashing BINs to ECU, bench testing, vehicle operation)
- **Verifying** critical changes — even with deterministic scripts, AI evaluation, and checksums, hex-level errors can still occur

The AI does the heavy lifting: parsing XDFs, reading/writing BIN calibration data, running batch edits, diffing files, cross-platform porting, and exporting snapshots — all through CLI commands in the terminal. The human is there to check the output and connect the digital work to the physical car.

It pairs a TunerPro XDF definition file with a BIN firmware file and provides
structured read/write access suitable for AI agents operating in a tool-use loop.

**This is a file editor, not a flash tool.** It reads/writes `.bin` files on disk.
Flashing to an ECU requires separate hardware and software (MS4x Flasher, EFILive, etc.).

## Architecture

```
cli_map_editor.py         ← CLI entry point (argparse commands)
  └─ XDFBinSession        ← Session wrapper: load, read, write, save
      └─ UniversalXDFExporter  ← XDF parser + address resolver
tunerpro_exporter_for_cli_editor_version.py  ← The exporter (v3.5.0)
porting_templates.py      ← Map classification for cross-ECU porting
mappings/                 ← CSV reference data for cross-platform porting
```

## CLI Commands Reference

| Command | Purpose | Key Args |
|---|---|---|
| `preflight` | Validate XDF+BIN compatibility | `--xdf`, `--bin` |
| `list-maps` | List all tables/scalars/flags/patches | `--xdf`, `--bin` |
| `show-map` | Print table data with axes | `--xdf`, `--bin`, `--map` |
| `show-scalar` | Print scalar value | `--xdf`, `--bin`, `--name` |
| `edit` | Write table cell(s) | `--xdf`, `--bin`, `--map`, `--rows`, `--cols`, `--value` |
| `edit-scalar` | Write scalar value | `--xdf`, `--bin`, `--name`, `--value` |
| `batch` | Apply CSV of edits | `--xdf`, `--bin`, `--csv` |
| `port` | Port maps between ECUs | `--src-xdf/bin`, `--dst-xdf/bin` |
| `diff` | Byte-level BIN comparison | `--bin-a`, `--bin-b` |
| `export` | Snapshot to TXT/JSON/MD | `--xdf`, `--bin` |

### Running Commands

```bash
python cli_map_editor.py <command> [args]
```

All commands are stateless — each invocation loads XDF+BIN fresh. Chain edits
by using the output BIN from the previous step as input to the next.

## Key Concepts for AI Agents

### Address Resolution
- XDF stores **relative addresses** (e.g., `0x1234`)
- BASEOFFSET (stored in XDF header) converts to absolute file offset
- MS42: BASEOFFSET=0x48000, MS43: BASEOFFSET=0x70000
- The exporter handles this automatically — agents never need to compute offsets

### Forward/Inverse Math
- XDF defines an equation per axis: `real = f(raw)` (e.g., `X*0.75-48.0`)
- **Reading**: raw bytes → equation → real values (e.g., 103 → 15.0°)
- **Writing**: real value → inverse equation → raw bytes
- The `--value` flag takes **real-world values** by default
- Use `--raw` flag only when writing raw integer values directly

### Table Indexing
- Rows and columns are **1-based** (matching TunerPro convention)
- Ranges: `--rows 1-5 --cols 1-3` (inclusive on both ends)

### Batch CSV Format
```csv
map,row,col,value
id_maf_tab,5,1,999.0
c_tco_swi_wup,,,55.0
```
- Empty `row`/`col` → treated as scalar edit
- Column names also accept: `MAP_NAME`, `ROW`, `COLUMN`/`COL`, `VALUE`

### Porting
- `port` command handles axis dimension differences via bilinear resampling
- AFR↔Lambda conversion is automatic when source/destination units differ
- Mass-unit tables (MAF calibration) are skipped — require manual review

## Output Files

Every write operation produces:
- `<stem>_edited_YYYYMMDD_HHMMSS.bin` — modified firmware
- `<stem>_edited_YYYYMMDD_HHMMSS.log` — TunerPro-compatible change log
- `<stem>_edited_YYYYMMDD_HHMMSS_detailed.csv` — cell-level audit trail

## Important Limitations

1. **No checksum correction** — saved BINs need checksums fixed before flashing
   (use MS4x Flasher, EFILive FlashScan, or equivalent)
2. **No real-time flash/read** — this is a file editor
3. **Inverse math uses brute-force search** for non-affine equations (0..65535)
4. **Temp files** (`.edited.tmp`) are only created by `edit`/`edit-scalar`
   without `--save`; use `save` command or `--save` flag to persist

## Supported Platforms (Tested)

| Platform | XDF | Notes |
|---|---|---|
| BMW MS42 (0110C6) | Siemens_MS42_0110C6_ENG_512K_v1.1.xdf | 597 tables, 1384 scalars |
| BMW MS43 (430069) | Siemens_MS43_430069_512K_1.1.3v.xdf | 1454 tables, 2256 scalars |
| Holden VY V6 ($060A) | VX VY_V6_$060A_Enhanced_v2.09a.xdf | GM Delco, different conventions |

## Development Guidelines

- The exporter copy (`tunerpro_exporter_for_cli_editor_version.py`) must stay
  in sync with `TunerPro-XDF-BIN-Universal-Exporter/tunerpro_exporter.py`
- Test with `run_test_suite.py` after changes
- All edits produce TunerPro-compatible log files (verified against 54 real logs)
- Do not truncate table/scalar names in any output — full names always
