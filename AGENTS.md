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

1. Begin with **read-only** inspection, then follow the human's requested scope.
   Use verified platform guidance and exact-target evidence rather than guessing
   from names. A vague goal such as "make it faster" is not a numeric target.
   If asked to figure it out, investigate and propose evidence-backed options;
   say "I don't know yet" when a necessary fact remains unproved.
2. Preserve the original XDF and BIN unmodified, record their SHA-256 hashes,
   sizes, ECU identity and software version where known, and use copied work
   files or a dedicated output directory.
3. Run preflight before selecting maps. Stop and report failures or unresolved
   definition problems. Never bypass validation, silently replace a definition,
   change its addresses, or edit program code merely to force an operation.
4. Show the exact map or scalar title, current converted values, units,
   axes and any uncertainty before proposing an edit.
5. Make a file write within a clear human-directed scope using supported
   objects and evidence-backed target values. A direct request to apply a
   specified edit, or an already agreed plan, does not require a separate
   approval file, signature or repeated confirmation. The human need not know
   an internal map ID: resolve it using verified exact-target guidance and
   show the selection and rationale. Ask if material choices remain unresolved.
   This local unreleased candidate also supports multi-object CSV or hash-pinned
   JSON `batch` plans: run the read-only preview first, then create one new BIN
   using `--autosave --output-dir`. This does not enable batch in an older
   released package or authorize publishing this candidate.
6. Reload the output, run preflight where applicable and compare before and
   after BINs. Confirm the output size, hashes, expected changed bytes and
   audit logs. Report unexpected or unexplained differences.
7. Never claim a modified BIN is ready to flash. ECU-specific checksums,
   signatures, programming procedures, emissions compliance and physical
   testing are separate responsibilities.
8. Do not upload customer files, proprietary definitions or datalogs to a
   third-party service without the file owner's authorisation.
9. Do not use disabled `port` or standalone `save` commands. CSV/JSON `batch`
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
kingai-map-editor batch --xdf definition.xdf --bin original.bin --plan-json exact-pair-edits.json --json
```

All filenames and titles above are placeholders. The tool must be executed
in an environment with terminal and filesystem access. Merely uploading the
source ZIP into a chat does not provide execution.

For **a human-requested scalar edit**, where its XDF structure
and storage meet the supported constraints:

```console
kingai-map-editor edit-scalar --xdf definition.xdf --bin original.bin --name "Exact scalar title" --value 10 --autosave --output-dir reviewed_output
kingai-map-editor diff --bin-a original.bin --bin-b reviewed_output/REPLACE_WITH_ACTUAL_OUTPUT.bin --xdf definition.xdf
```

Batch plans may include exact XDF unique IDs, XDF storage addresses and
expected old raw values to prevent ambiguous or stale edits. The JSON plan
requires exact BIN/XDF SHA-256 values and emits a structured error when
--json is requested. Record the plan SHA-256 too. The pinned Exporter does
not expose flag unique IDs; flags may be selected by title, address and
exact bit mask (flag_mask) when titles and byte addresses collide.

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

If hosted Actions are unavailable, run source tests directly on a terminal
with Python and pytest. For an offline pinned-Exporter wheel, use
run_offline_editor_qualification.py, pass an independently checked wheel hash
and keep the output folder private/outside the Git repository. The runner
does not prove the wheel's source commit by inspection of its metadata; see
docs/BATCH_HARDENING_OFFLINE_20261022.md.

An optional --exporter-source clean exact-pin Git checkout now verifies the
wheel's non-metadata payloads against committed source. Its receipt distinguishes
that provenance from native TunerPro, real ECU and reproducible-build claims;
see docs/REAL_PINNED_EXPORTER_QUALIFICATION_20261024.md.

The README on the checked-out branch governs supported commands. The
transactional batch feature is an unreleased candidate, not part of the
previous published rc2 package. Later historical planning notes do not
supersede verified command status.

## Guided tuning versus research

Follow [the guided workflow](docs/GUIDED_TUNING_AND_RESEARCH.md). Reuse retained
proof for the exact firmware, layout and definition where still applicable;
do not redo disassembly for every established edit. Recheck evidence affected
by changed inputs, definitions, code or selectors. Keep map identification,
file-write correctness and vehicle validation separate. Logs inform behaviour
but do not alone establish a calibration address. Repeating an AI opinion three
times is not three independent checks. These instructions do not bypass tool,
platform or user-specific permissions.
