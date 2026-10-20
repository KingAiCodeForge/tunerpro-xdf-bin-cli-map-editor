# Agent instructions

Read [AGENTS.md](../AGENTS.md) and the current [README.md](../README.md) before operating the editor. These instructions describe 1.2.0rc1, an experimental integration prerelease.

- Use the installed, exactly pinned MIT Exporter dependency; do not import another parser from a sibling checkout.
- Default to inspection. Record exact input hashes and run preflight. Obtain approval for an exact named object and numeric target before editing a calibration.
- `batch`, `port` and standalone `save` remain disabled. One-shot edits require `--autosave --output-dir` and create new outputs.
- Integer engineering writes require proven affine math or the narrow supported `K/X` inverse. Nonlinear, scoped and unsupported-stride writes fail closed. There is no numerical-search fallback.
- `validate-fixture` and `export-fixture` verify exact BIN/XDF identity; they do not establish native parity or tuning safety.
- Saves stage all payloads, fsync, publish audit files, and publish BIN last. Interrupted staging is retained in `.kingai-save-*.incomplete/`; it must never be mistaken for a completed output or committed.
- Run source tests, then run tests against isolated installed wheels outside both checkouts. Record skips as missing evidence. See [integration evidence](../docs/INTEGRATION_20261020.md).
- Preserve all original branches and artifacts. Never commit private definitions, firmware, customer files, credentials or unreviewed local-path reports.
- No hardware, flashing, checksum repair or vehicle-safety qualification is provided.

Historical batch/port architecture is preserved in Git history and `porting_templates.py`; it is not an enabled command contract.
