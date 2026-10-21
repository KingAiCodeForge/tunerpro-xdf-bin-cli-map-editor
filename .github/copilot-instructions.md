# Agent instructions

Read [AGENTS.md](../AGENTS.md) and the current [README.md](../README.md) before operating the editor. These instructions apply to the unreleased transactional-batch candidate based on 1.2.0rc2.

- Use the installed, exactly pinned MIT Exporter dependency; do not import another parser from a sibling checkout.
- Default to inspection. Record exact input hashes and run preflight. Obtain approval for an exact named object and numeric target before editing a calibration.
- CSV `batch` is enabled on this branch for reviewed table, scalar and flag edits. Its default is a read-only preview; `--autosave --output-dir` creates one new BIN with audits. `port` and standalone `save` remain disabled.
- Integer engineering writes require proven affine math or the narrow supported `K/X` inverse. Nonlinear, scoped and unsupported-stride writes fail closed. There is no numerical-search fallback.
- `validate-fixture` and `export-fixture` verify exact BIN/XDF identity; they do not establish native parity or tuning safety.
- Saves stage all payloads, fsync, publish audit files, and publish BIN last. Interrupted staging is retained in `.kingai-save-*.incomplete/`; it must never be mistaken for a completed output or committed.
- Run source tests, then run tests against isolated installed wheels outside both checkouts. Record skips as missing evidence. See [integration evidence](../docs/INTEGRATION_20261020.md).
- Preserve all original branches and artifacts. Never commit private definitions, firmware, customer files, credentials or unreviewed local-path reports.
- No hardware, flashing, checksum repair or vehicle-safety qualification is provided.

The old batch/port implementation remains historical. The new `transactional_batch.py` is the only enabled multi-edit contract; the legacy porting templates are not enabled.
