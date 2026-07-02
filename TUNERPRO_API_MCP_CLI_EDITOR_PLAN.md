# TunerPro API, MCP, and CLI Editor Plan

Status: proposal

This project should be positioned as a local automation layer around XDF/BIN
workflows, not as a TunerPro replacement. TunerPro remains the reference GUI
for human review. The CLI/API/MCP layer should provide deterministic,
auditable operations that agents and scripts can call safely.

## Current Boundary

- Keep the existing CLI as the source of truth for read/edit/diff/preflight.
- Treat XDF compatibility as per-fixture, not universal.
- Mark the VY/VX Enhanced `v2.09` XDF family as needing fresh regression
  testing against current TunerPro behavior and current public XDFs.
- Do not claim compatibility until a fixture exports correctly, diffs cleanly,
  and matches human-reviewed expectations.

## Phase 1 - Regression Harness

1. Build a fixture manifest format:
   - XDF path
   - BIN path
   - expected BIN size/hash
   - expected table/scalar/flag counts
   - known tables and axis sanity checks
   - expected warnings
2. Add `validate-fixture` and `export-fixture` commands.
3. Add fixtures for:
   - BMW MS42/MS43/MS45 known-good pairs
   - Holden VY/VX/V6 Enhanced `v2.09` pairs
   - older Holden Enhanced pairs that previously worked
4. Save outputs under an ignored local folder, then compare summarized results
   in public-safe reports.

Commit point: commit after fixture manifests and commands work with public-safe
sample fixtures or synthetic fixtures. Do not commit private bins, private XDFs,
or local absolute paths.

## Phase 2 - Stable Python API

Expose the CLI engine as importable Python functions:

- `load_project(xdf, bin)`
- `list_maps(filter)`
- `read_map(id_or_name)`
- `edit_cells(map_id, edits)`
- `preflight()`
- `diff(original_bin, edited_bin)`
- `export(format)`

The API should return structured objects, not terminal text. The existing CLI
can call the API so behavior stays consistent.

Commit point: commit when CLI output remains backward compatible and API calls
have unit tests around address resolution, axis handling, inverse math, and
write-back.

## Phase 3 - MCP Server

Create a local MCP server that wraps only safe, deterministic operations first:

- `tunerpro_list_maps`
- `tunerpro_read_map`
- `tunerpro_preflight`
- `tunerpro_diff`
- `tunerpro_export_summary`

Gate write operations behind explicit local flags:

- `tunerpro_edit_cells`
- `tunerpro_apply_batch`
- `tunerpro_write_bin`

Write tools should require:

- explicit output path
- baseline hash
- preflight pass
- generated edit log
- human review note or `--allow-write` local config

Commit point: commit read-only MCP first. Commit write tools only after the
fixture harness proves byte-level diffs are exactly bounded.

## Phase 4 - Local HTTP API

Add an optional local FastAPI server for GUIs and external tools:

- no cloud dependency
- bind to `127.0.0.1` by default
- no secrets required
- project file references only
- explicit CORS lock-down

This should reuse the same Python API as the CLI and MCP server.

Commit point: commit after read-only routes work and have tests. Add write
routes later with the same guardrails as MCP.

## Phase 5 - Share Pack for Mark or Other Tool Authors

Do not send raw private bins, private XDFs, auth material, logs, or local
machine-specific paths.

Prepare a small review pack:

- GitHub repo links
- one-page architecture summary
- short screen recording or screenshots
- public-safe synthetic fixture output
- exact bug/regression description for `v2.09` if still reproducible
- clear statement that this is a companion automation layer, not a replacement

Use Drive only for large artifacts that do not belong in GitHub:

- videos
- zipped synthetic test outputs
- public/sample XDF/BIN fixtures if license-safe

Source code should go through GitHub. Drive is for review artifacts, not the
canonical source of truth.

## Commit and Push Rule

Commit when:

- docs no longer overclaim compatibility
- `git diff --check` passes
- no local machine paths, auth material, or private exports are staged
- tests or at least `py_compile` pass
- dirty local test files are ignored or intentionally excluded

Push when:

- the commit is public-safe
- the README clearly says what is proven, what is experimental, and what needs
  re-test
- the branch is not mixing source fixes with private regression outputs
