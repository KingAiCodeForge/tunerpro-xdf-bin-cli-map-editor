# KingAI CLI Map Editor

**Offline XDF/BIN inspection, bounded calibration edits and reproducible byte-level review.**

- **Version:** **1.2.0rc1**, an experimental integration prerelease.
- **Documentation review:** 20 October 2026.
- **Author:** KingAI Pty Ltd / KingAiCodeForge.
- **Status:** Research and engineering tooling. **Not a flasher, autonomous tuner or vehicle-safety approval.**

The editor reads TunerPro XDF definitions against a supplied BIN, lets a human or a terminal-capable agent inspect supported items, and produces new BINs and audit records for a narrowly supported set of integer edits. **A valid-looking table, preflight pass or successful byte diff does not prove the selected calibration controls the intended ECU function.** Verify exact software identity, storage, equations, linked items and firmware consumers independently before relying on a definition.

This README describes this integration revision. Read [AGENTS.md](AGENTS.md) for the read-only-first workflow and [integration evidence](docs/INTEGRATION_20261020.md) for provenance, executed checks and unresolved qualification. Historical documentation and examples are preserved in [the previous README revision](https://github.com/KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor/blob/95cc0f9f79bda3f5b17e49c4a3b9b3ea71241b9/README.md); its disabled-command examples are not current instructions.

## Who operates this tool?

**The conversation is the human interface; the command line is the AI agent's interface.** The intended user can describe a calibration inspection or a precisely specified edit in ordinary language. A terminal-capable agent such as **Codex** or **Claude Code** reads the tool's help, inspects the provided XDF/BIN, executes supported Python commands and returns the measured result, diff and audit evidence. A human can use the same commands manually, but this project is designed primarily as a **machine-operable calibration engine**, not another table-editing GUI.

The agent is an **operator of deterministic software**, not an oracle for ECU control semantics. A correct byte write to the *wrong* map is still a wrong tune. The actual firmware strategy, selector, calibration purpose, vehicle setup, protections and measured effects require independent evidence. The person retains final authority over any modification.

**How it differs from conventional editors:** TunerPro already supports rich XDF math, smoothing, interpolation, graphing and (with compatible hardware) RT logging. Commercial tools often provide integrated vehicle definitions, logging and flashing. KingAI's proposed value is a **source-inspectable, text/JSON/CSV-friendly, headless interface for coding agents**, with explicit failures and byte-level receipts. It is not currently a replacement for TunerPro's full parser, native interpolation, vehicle support or flashing.

| A person asks the agent | Supported action on this public release | Important restriction |
| --- | --- | --- |
| “What's in this calibration?” | Inspect XDF/BIN, preflight, list/show/export supported items | A definition title or plausible value is not proof of the active control |
| “What changed between stock and modified?” | Compare BIN bytes and optionally attribute changes through the XDF | Keep unattributed bytes in the review |
| “Change this **verified** scalar/cell to the value I approve” | Execute a supported bounded integer edit on a copy, then re-read/diff | Must have exact input identity, valid math/storage and human approval |
| “Apply this **exact** supplied raw-byte patch” | Verify hash-bound v2 manifest and, if approved, apply to a new file | Static verification does not prove code execution or flash readiness |
| “Make a bouncing limiter / decel tune” | **Investigate first**: locate candidate controls, request hardware/log evidence, report what's proved | No automatic tune recipe, unproven limiter patch or claim of engine safety |

**Execution requirement:** the AI must actually have filesystem and terminal access, a working Python environment and the pinned Exporter dependency. Attaching the source ZIP to an ordinary chat **does not necessarily allow it to run**. No built-in LLM, GPU or MCP server is required to operate the present CLI; an MCP server is a future *adapter* rather than a prerequisite. The Editor and its pinned Exporter source use the MIT licence; see [Licensing](#licensing).

## Install

Requirements: Python **3.10+**, Git and access to the pinned dependency.

```console
git clone https://github.com/KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor.git
cd tunerpro-xdf-bin-cli-map-editor
python -m pip install .
kingai-map-editor --help
```

The package is `kingai-tunerpro-map-editor==1.1.0`. Its `pyproject.toml` pins the **Universal Exporter 3.7.2** source to commit `f81e0cd6b522b8142e7424774ec068c9bb711792`. `tunerpro_exporter_for_cli_editor_version.py` is a compatibility entry point importing that installed package, **not a second bundled/cloned parser**. No sibling Exporter checkout is required for the installed CLI.

The commands below use the installed `kingai-map-editor` entry point. `python cli_map_editor.py` also works from a correctly installed source checkout. Use a matching, lawfully obtained XDF and BIN; neither is supplied in this repository.

An offline release bundle contains the exact Editor and Exporter wheels, checksums and a Python installer. It requires Python 3.10+; extract it and run `python "path to bundle/install.py"`. The installer checks wheel hashes before creating a new environment, installs with no network index and refuses an existing environment. This is a portable Python distribution; it does not include a Python interpreter or standalone executable. To reproduce the asset, run `python -m build_portable_bundle --help` and supply the two exact tested wheels and exporter commit.

## What works on `main`

| Command | Current behaviour | Qualification boundary |
| --- | --- | --- |
| `list-maps`, `show-map`, `show-scalar`, `show-flag` | Read supported XDF items and decoded BIN values | Parsing is not proof of active map semantics or native TunerPro parity |
| `preflight` | Check declared addresses, readable items, BIN bounds and reported table overlaps | Structural heuristic only; not OSID, firmware-consumer, checksum or hardware proof |
| `diff` | Compare raw BIN bytes; optional XDF attribution and JSON/CSV reports | Attribution depends on definition accuracy; unknown bytes remain unknown |
| `export` | Create a new timestamped snapshot directory holding BIN, TXT, JSON, Markdown and conversion-error report | Refuses incomplete supported export; not a TunerPro native export |
| `validate-fixture`, `export-fixture` | Verify exact BIN size and BIN/XDF SHA-256, then reuse preflight and optionally guarded export | Identity is not native parity, ECU semantics or flash qualification |
| `edit`, `edit-scalar` | Bounded integer edits with supported contiguous storage and proven affine or narrow `K/X` inverse; raw mode where allowed | Requires `--autosave --output-dir`; rejects unsupported math/storage/geometry |
| `edit-flag` | Set/clear declared 8-bit masks without altering unrelated bits in the same byte | Requires `--autosave --output-dir`; mask and definition must be correct |
| `verify-raw-patch`, `apply-raw-patch` | Check and apply/reverse strict v2, hash-bound byte manifests to **new** files | Static byte contract only; does not verify patch execution or flash readiness |
| `batch`, `port`, standalone `save` | **Disabled; return an error** | Do not use examples from the historical README as supported workflows |

**Unsupported writes:** IEEE-754 float writes, nonlinear inverses outside the proven affine and narrow `K/X` classes, scoped per-cell XDF math, arbitrary/non-contiguous strides, automatic cross-ECU porting and multi-operation batch writes. Reciprocal zero targets and unsupported rearrangements fail closed; there is no numerical-search inverse fallback. Live ECU communication, checksum repair and flashing are unavailable. Synthetic success does not qualify any real ECU definition.

## Exact-pair fixture gate

`validate-fixture` verifies a selected target's exact BIN size and BIN/XDF SHA-256 before normal read-only preflight. `export-fixture` runs the same gate, then reuses the existing guarded snapshot exporter. Supported JSON schemas are `kingai.exact-pair-fixture-set.v1` and the single `kingai.exact-bin-xdf-fixture.v1`.

```console
kingai-map-editor validate-fixture --fixture exact_pairs.json --target-id synthetic-demo --xdf "definition file.xdf" --bin "original file.bin"
kingai-map-editor export-fixture --fixture exact_pairs.json --target-id synthetic-demo --xdf "definition file.xdf" --bin "original file.bin" --output-dir "review snapshots"
```

The fixture gate proves identity only. No customer or real ECU fixture is distributed in this package.

## Safe first pass: inspect without changing firmware

```console
kingai-map-editor preflight --xdf definition.xdf --bin original.bin
kingai-map-editor list-maps --xdf definition.xdf --bin original.bin
kingai-map-editor show-map --xdf definition.xdf --bin original.bin --map "Example table"
kingai-map-editor show-scalar --xdf definition.xdf --bin original.bin --name "Example scalar"
kingai-map-editor show-flag --xdf definition.xdf --bin original.bin --name "Example flag"
```

The example titles are placeholders: use actual titles returned by `list-maps`. Title matching is exact first, then case-insensitive; **ambiguous duplicate titles are rejected**, not silently resolved to the first match. An ECU model name or similar-sounding map title cannot establish equivalence. When selecting a control, retain its exact XDF/BIN hash and evidence for its code consumers and active selector.

`preflight` reports file/layout inconsistencies and possible overlap, but it cannot determine whether a shared axis is deliberate, whether a parameter is active, or whether a unit conversion is correct. Treat suspicious zero or uniform tables as review signals, not proof that the data or definition is wrong.

## Controlled edits: new BIN only

**Both** the save flag and an explicit output directory are mandatory. `--save` is an alias for `--autosave` on edit commands; it does **not** mean that the separate `save` command is enabled. There is no `.edited.tmp` workflow.

```console
kingai-map-editor edit-scalar --xdf definition.xdf --bin original.bin --name "Example scalar" --value 10 --autosave --output-dir output

kingai-map-editor edit --xdf definition.xdf --bin original.bin --map "Example table" --rows 1-3 --cols 1-2 --value 13.0 --autosave --output-dir output

kingai-map-editor edit --xdf definition.xdf --bin original.bin --map "Example table" --rows 1 --cols 1 --value 132 --raw --autosave --output-dir output

kingai-map-editor edit-flag --xdf definition.xdf --bin original.bin --name "Example flag" --state set --autosave --output-dir output
```

Rows and columns are **1-based**. `--raw` chooses an integer raw target; it **does not bypass** the supported-width, signedness, range, storage-type, stride, equation-scope or output-protection checks. Engineering values may quantize to the nearest representable integer; inspect the redecoded result and exact changed bytes. Only use a verified cell/value and a disposable file.

Each successful edit creates a new timestamped BIN plus a project-owned text `.log` and a separate `_detailed.csv`; existing outputs and source files are not overwritten. The text log **resembles TunerPro's presentation**, but is explicitly identified in the file as a KingAI log, **not a native TunerPro log**. The detailed CSV has these columns:

```csv
TIMESTAMP,MAP_NAME,TYPE,ROW,COLUMN,ADDRESS,FILE_OFFSET,OLD_RAW,NEW_RAW,OLD_HEX,NEW_HEX,OLD_REAL,NEW_REAL,UNIT,SIZE_BITS
```

Saves prepare and fsync all payloads before publication, publish the audit files first and the BIN last, and refuse existing destinations. A handled failure attempts to roll back only outputs owned by that save and retains labelled `.kingai-save-*.incomplete/` staging evidence. This is **not a crash-proof multi-file transaction**. Treat incomplete staging and any output requiring inspection as a failed save, and keep that evidence private.

Use the **actual output filename** printed by the edit command in the subsequent diff. Do not reuse the original input path as an output, and do not assume a particular timestamp.

## Compare and export

```console
kingai-map-editor diff --bin-a original.bin --bin-b edited-copy.bin
kingai-map-editor diff --bin-a original.bin --bin-b edited-copy.bin --xdf definition.xdf --json-out change-report.json --csv-out change-report.csv
kingai-map-editor export --xdf definition.xdf --bin original.bin --output-dir snapshots
```

Reports must use new, distinct paths; `diff` refuses to overwrite existing report files or the input BIN/XDF. The export command creates a **new** timestamped subdirectory inside `snapshots/`; it does not write the snapshot files directly into `snapshots/`. Byte-level changes outside XDF coverage should be reviewed rather than dropped. The optional `--xdf-only` flag explicitly restricts attribution and must not be mistaken for a complete whole-image diff.

## Exact-image raw patch verification

Raw/code patches are a different operation from XDF map edits. The strict manifest format is `kingai.raw-patch.v2`; see [`raw_patch_manifest.py`](raw_patch_manifest.py) for the executable schema and validation requirements. Manifests bind the exact source image, software identity, size, before/after hashes, declared byte changes, immutable ranges and optional **registered** checksum-verifier profiles. The CLI does **not** run arbitrary manifest commands or repair checksums.

```console
kingai-map-editor verify-raw-patch --bin exact-base.bin --manifest exact-patch.json
kingai-map-editor apply-raw-patch --bin exact-base.bin --manifest exact-patch.json --output patched-review.bin
kingai-map-editor verify-raw-patch --reverse --bin patched-review.bin --manifest exact-patch.json
kingai-map-editor apply-raw-patch --reverse --bin patched-review.bin --manifest exact-patch.json --output restored-base.bin
```

Successful verification proves the prescribed **static byte-level transformation**, not ISR timing, firmware control flow, runtime behaviour, recovery or vehicle safety. Even if a patch and its registered checksum verifier pass, **do not flash without separate exact-target hardware, readback and recovery qualification**. No BIN, XDF, patch source, or tuning strategy should be assumed portable solely because two definitions have matching titles.

## Definition compatibility and reverse-engineering use

This code has been exercised in research involving BMW Siemens MS42/MS43/MS45 and Holden Delco definitions, but **supported ECU families are not a product-wide compatibility certification**. The exact OSID/software identity, full-versus-partial image layout, XDF `BASEOFFSET`, endianness, integer type, XDF equation, axis ownership, and call-site/selector evidence must be established for each pairing.

Use the Exporter and Editor as the **review loop**: disassemble or trace candidate code consumers; record source hashes and confidence; create/update a review XDF; inspect parsed tables against the correct BIN; diff with known baselines; then compare against native TunerPro and, separately, validated hardware results. Zero or uniform results do not independently establish an error, and matching names are not evidence of a correct cross-OSID port.

Historical MS42/MS43/VY table counts and the old “410 common name matches” example are archived in the [previous README](https://github.com/KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor/blob/95cc0f9f79bda3f5b17e49c4a3b9b3ea71241b9/README.md). **Name matches are not directly portable maps**, and historic `batch`/`port` test notes do not override the disabled release boundary.

## Example instructions to give an AI coding agent

These are **human requests**, not extra CLI commands. The agent must inspect `--help` and source and only invoke commands actually supported by the package provided.

> “Open this matching XDF and BIN. Run preflight, list all relevant tables, and show me their raw values, units, axes and conversion equations. Keep the originals untouched. Mark uncertain definitions and active selectors as unverified.”

> “Compare these stock and modified BINs. Report every changed byte, which XDF item claims each range, and any unattributed differences. Check for changed protections. Do not write a file.”

> “For the **already verified** table and selected cells, show me the before/after engineering values and exact raw bytes for the value I have approved. Use the guarded Editor to create a new BIN, re-open it and prove no unrelated bytes changed. Report checksum status separately; do not flash.”

> “Check this supplied exact-hash patch manifest against the original image. If the identity, old bytes, immutable regions or registered verifier disagree, stop. If all checks pass, explain the remaining firmware and hardware validation gaps before any application.”

For requests like **“make pops and bangs”** or **“make the limiter bounce”**, there is no generic safe recipe in this software. The AI should first identify the exact code path, requested behaviour, protection interactions and available measurement evidence. If semantics or target pairing are unproven, stop at a research report or simulation. Do not bypass an unsupported write operation with an ad-hoc Python hex edit.

### Reproducible demonstration to prove the tool works

Use a small synthetic XDF/BIN fixture (not a customer ECU image) containing a named, single-variable affine scalar. A coding agent should:

1. Run `--help`, `preflight`, `list-maps` and `show-scalar` on the exact fixture.
2. Record full input SHA-256 digests and the scalar's file byte range, raw value, decoded value and equation.
3. Ask for an explicit fixture-only target value, then use `edit-scalar --autosave --output-dir` to write **a new BIN**.
4. Run `show-scalar` against the new BIN and `diff` against the original. Check the actual output file name and full-image byte delta; verify the input hashes did not change.
5. Deliberately try a wrong file, unsupported expression or duplicate title; confirm the operation **fails closed** and produces no trusted output.

This is a **suggested acceptance scenario**, not a claim that the demonstration has been executed against the new documentation branch. A passing synthetic demo proves the tooling path, **not** engine tuning quality.

## Using with Claude, Codex, or other AI agents

An agent may read and explain outputs, compare exact BIN pairs and prepare a **reviewed proposal**. The agent must not infer an active map from a title, choose an unknown axis convention, bypass a failure, or write to the ECU. For this release:

1. Record the exact XDF and BIN identities, and run `preflight`.
2. Inspect the intended item and verify its address/axis/scaling and actual firmware consumer or an explicit uncertainty/HOLD.
3. Obtain a human-approved target value and choose a supported single edit.
4. Write **only to a new file** with `--autosave --output-dir`.
5. Diff the entire BIN; inspect the detailed CSV, redecoded value, checksum status and any held assumptions.
6. Retain source originals and reports; **no autonomous flashing**.

For potential native TunerPro data bindings and read-only MCP integration, see [`TUNERPRO_API_MCP_CLI_EDITOR_PLAN.md`](TUNERPRO_API_MCP_CLI_EDITOR_PLAN.md). This is an **interface proposal**, not evidence that a TunerPro 6 API currently exists.

## Tests and review acceptance

```console
python -m pip install ".[test]"
python -m pytest -q
```

Keep executable results and failures tied to exact commit and dependency versions. Test a built wheel in an isolated environment outside the source checkout. Preserve golden input snapshots and independently compare supported read/edit behaviour against native TunerPro; do not mistake synthetic test counts for ECU or vehicle proof. Some exact-target fixtures are privately held and are not part of this public repository.

Issues and regression fixtures are welcome for **specific legal XDF/BIN combinations**; remove VINs, immobiliser secrets and customer data before publishing.

## Further documentation

- [AI workflow background](AI_TUNING_PLAN.md)
- [Holden research guide](HOLDEN_AI_TUNING_GUIDE.md)
- [BMW MS42/MS43/MS43X research guide](BMW_MS42_MS43_MS43X_AI_TUNING_GUIDE.md)
- [Legacy patch/formula rebuild register](PATCH_REBUILD_REGISTER.md)
- [Public Universal Exporter](https://github.com/KingAiCodeForge/TunerPro-XDF-BIN-Universal-Exporter)
- [TunerPro official site](https://www.tunerpro.net/)

These guides contain historical research; follow the code and **current branch-specific evidence** when older documents contradict the supported release boundary.

## Licensing

The Editor's [LICENSE](LICENSE) is MIT. Its pinned Universal Exporter dependency has a **separate custom source-available licence**, which the Editor's MIT licence does not override. Review the [Exporter's terms at the pinned commit](https://github.com/KingAiCodeForge/TunerPro-XDF-BIN-Universal-Exporter/blob/f81e0cd6b522b8142e7424774ec068c9bb711792/LICENSE) before redistribution or commercial reuse.

Thanks to Mark Mansur and the TunerPro/XDF community for the format, native editor and contributed definitions. This project is independent of and not endorsed by TunerPro.
