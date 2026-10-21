# Agent instructions for KingAI CLI Map Editor

These instructions apply to coding agents such as Codex, Claude Code, and
terminal-enabled assistants working in this repository.

## Purpose and boundaries

This project operates on local ECU calibration files using a TunerPro XDF
definition and a corresponding raw BIN. The CLI is a file inspection and
bounded editing tool. It is not an ECU flasher, checksum repair tool,
calibration correctness guarantee, or engine safety certification.

A matching file name, ECU family, or successful parse is **not** proof that
a particular XDF correctly describes the BIN. Treat addresses, units,
scaling, labels, and table semantics as hypotheses until verified against
the exact software identity and independent evidence.

## Agent operating rules

1. Default to **read-only** inspection. Never infer a tuning value from a
   vague request such as "make it faster" or "make it safe."
2. Preserve the original XDF and BIN unmodified, record their SHA-256 hashes,
   sizes, ECU identity and software version where known, and use copied work
   files or a dedicated output directory.
3. Run preflight before selecting maps. Stop and report failures or unresolved
   definition problems. Never bypass validation, silently replace a definition,
   change its addresses, or edit program code merely to force an operation.
4. Show the exact map or scalar title, current converted values, units,
   axes and any uncertainty before proposing an edit.
5. Make a file write only when the user explicitly specifies named supported
   objects and desired values and approves a reviewable change. Single edits
   and multi-object CSV `batch` plans are supported: run a read-only batch
   preview first, then publish one new BIN using `--autosave --output-dir`.
6. Reload the output, run preflight where applicable and compare before and
   after BINs. Confirm the output size, hashes, expected changed bytes and
   audit logs. Report unexpected or unexplained differences.
7. Never claim a modified BIN is ready to flash. ECU-specific checksums,
   signatures, programming procedures, emissions compliance and physical
   testing are separate responsibilities.
8. Do not upload customer files, proprietary definitions or datalogs to a
   third-party service without the file owner's authorisation.
9. Do not use disabled `port` or standalone `save` commands. CSV `batch`
   stages multiple edits, detects byte conflicts and validates every edited
   object against the final image before saving. Engineering inverses remain
   limited to proven affine and narrow `K/X` forms.
   Other nonlinear inverses, floats, unsupported layouts and scoped math
   writes fail closed; do not bypass those restrictions.

## Installation and inspection

Requires Python 3.10 or later and Git for the pinned exporter dependency.

```console
python -m pip install .
kingai-map-editor --help
kingai-map-editor preflight --xdf definition.xdf --bin original.bin
kingai-map-editor list-maps --xdf definition.xdf --bin original.bin
kingai-map-editor show-map --xdf definition.xdf --bin original.bin --map "Exact table title"
kingai-map-editor show-scalar --xdf definition.xdf --bin original.bin --name "Exact scalar title"
kingai-map-editor export --xdf definition.xdf --bin original.bin --output-dir inspection
kingai-map-editor batch --xdf definition.xdf --bin original.bin --csv reviewed-edits.csv
```

All filenames and titles above are placeholders. The tool must be executed
in an environment with terminal and filesystem access. Merely uploading the
source ZIP into a chat does not provide execution.

For **a separately approved scalar edit**, where its XDF structure
and storage meet the supported constraints:

```console
kingai-map-editor edit-scalar --xdf definition.xdf --bin original.bin --name "Exact scalar title" --value 10 --autosave --output-dir reviewed_output
kingai-map-editor diff --bin-a original.bin --bin-b reviewed_output/REPLACE_WITH_ACTUAL_OUTPUT.bin --xdf definition.xdf
```

Discover the actual output filename from the CLI response; do not assume it
matches the placeholder. Review rounding, quantisation, offsets, log files
and changed bytes against the requested edit. Do not apply the change to
a vehicle on the strength of a successful CLI operation.

## Required handoff report

Provide exact input hashes, tool revision, exporter revision, XDF and BIN
identity, named objects inspected, units and conversions, preflight results,
requested value, stored value, output hash and changed offsets, plus remaining
checks and unknowns. If a step was not executed or independently verified,
say so explicitly.

## Verification before changing software

When editing this repository, keep software changes separate from calibration
changes. At minimum run relevant unit tests and the installed-package smoke
check. Validate representative, permissioned real XDF/BIN pairs against native
TunerPro before any compatibility or release claims. No private firmware,
customer data or proprietary XDFs should be committed to this repository.

The README on the checked-out branch governs supported commands. The
transactional batch feature is an unreleased candidate, not part of the
previous published rc2 package. Later historical planning notes do not
supersede verified command status.
