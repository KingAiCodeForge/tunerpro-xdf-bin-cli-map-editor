# ADX/XDL log-driven corrections and natural-language tuning roadmap

**Date:** 25 October 2026 (ACDT)  
**Status:** Proposed integration, documentation only. This is not a live-tuning feature announcement.

The CLI Editor is a deterministic XDF/BIN file editor, not a real-time ECU interface or flasher. The unreleased 1.3.0a1 source integrates the transactional batch-plan candidate (`kingai.xdf-batch-plan.v1`), mock-only adapter CLI and a separate opt-in exact VY checksum review-copy utility; see [current README](../README.md). This is not a stable release. ADX/XDL import, automated log-to-cell correlation, live communication, general checksum repair and flashing remain unimplemented.

The following wording is preserved **verbatim** as requested, including its conversational phrasing and illustrative value. It describes the intended division of labour, not verified calibration advice or promises of currently implemented features.

## Original design wording (verbatim)

A pr for the CLI editor public repo

Fair point, and I'll give you that one — with one boundary drawn carefully.

**Agreed: the correction brain can live in the chat/agent, not the repo.** Bucketing AFR error per cell, averaging samples, weighting steady-state, proposing a 3% VE correction — that's exactly what an LLM does well from a pasted log, and bolting a heuristic correction module into the repo would just be a dumber version of the same thing. It also fits the project's own philosophy: the tool is a deterministic executor, the AI is the operator. Nobody needs to reimplement judgment in Python.

And for the non-realtime loop you're describing — pull on bin A, log it, correct, flash bin B — that works today with copy-paste, *almost*. The gaps that remain are smaller than "build an analysis module" but they're real:

1. **Log → cell alignment still has to happen somewhere.** If TunerPro exports the log to CSV natively, chat handles the whole thing. If the log is a binary XDL, something has to decode it first — that's a converter script, not a correction module. One-time, per-format plumbing.

2. **The bridge from chat output to bytes.** Chat says "VE cell (3,7) should be 78.4" — the editor turns that into the correct raw value with quantization, neighbor checks, and refuses ambiguity. That's the irreplaceable part: the model is bad at raw-byte conversion math and should never do it by hand. This is exactly what `edit` + the PR #10 plan format (`kingai.xdf-batch-plan.v1`) already provide. Chat writes the plan JSON, editor executes it. That bridge is already built — it just needs to land.

3. **The log has to be bound to the bin it came from.** Your point "the bin is matching the logs" is doing heavy lifting here — the failure mode is a week later, when three logs from three different bins are sitting in a folder and a correction gets applied to the wrong image. The plan format's mandatory BIN/XDF SHA-256 binding solves this *if* the agent habitually records which bin each log belongs to. For your own workflow that discipline is easy; it's the one thing I'd insist on keeping machine-enforced rather than remembered.

4. **Where this breaks down is scale, not feasibility.** One VE table from one pull? Chat handles it beautifully. A full calibration pass — VE, timing, transient enrichments, idle, cold-start — across five pulls with cross-referencing? Pasting that into a chat window becomes the bottleneck, and you drift into wanting the local agent (Claude Code/Codex on the dyno PC) reading logs and BINs off disk directly, with the chat doing reasoning over *files* instead of pasted text. Same brain, better hands.

So the corrected build list for your actual workflow shrinks to: PR #10 landed (plan execution), a log-format converter if your logs are binary XDL, checksum plugin, flasher extension. The correction intelligence stays in the model where it belongs — and honestly, that's the better architecture, because the reasoning layer improves every time the models improve, while the executor just sits there being trustworthy.

The one thing I'd still keep out of pure chat: the **write**. AI proposes values, plan JSON carries them, editor writes bytes, receipt proves what changed. That's the division of labor that makes "ChatGPT can do it" compatible with "it never silently writes the wrong byte."

Also this is a good idea. My cli editor can be extended by ChatGPT itself in your library it has

A new .MD will be made in the next integration for the public. About how to do live tuning and when or how I will implement this, and adx xdl based correction edits for people who want to tune faster with human text based vibe tuning prompts.

---

## Intended operator experience

A user should be able to ask in ordinary language, for example:

> "Read my matching XDF and BIN and this pull's datalog. Explain where the measured operating points land in the verified calibration tables, what is uncertain, and which cells I might review. Produce a proposed edit plan and show the predicted quantized values and changed bytes. Do not write or flash an ECU."

The **agent/chat provides reasoning**: interpretation, uncertainty, and proposed engineering values based on supplied evidence. The **CLI handles determinism**: source identity, permitted file formats, XDF conversion, integer quantization, conflict detection, staged readback, and complete byte-level receipts. The model should not hand-calculate raw ECU bytes, silently fabricate missing channels, or claim a particular map is active merely because its XDF title resembles a logged channel. No generic automatic AFR, VE, spark or knock-retard recipe is proposed for the CLI.

The file-based sequence is **baseline BIN A + its matching XDF → log session → normalize/correlate evidence → agent proposes → reviewed structured plan → new BIN B + receipt → independent checksum/flash validation → separately logged comparison**. Nothing here establishes that an ECU image is flashable or safe to run.

## Integration stages and acceptance criteria

1. **Land and qualify the batch executor (dependency).** Bring PR #10 through the remaining pinned-Exporter, installed-package, native TunerPro and exact-target gates before documenting `batch --plan-json` as supported on `main`. Preserve the existing safe single-edit path. Keep model-produced plans declarative and deterministic; avoid embedding agent correction heuristics in the engine.
2. **ADX-aware CSV import (first datalog milestone).** Accept already-exported CSV and optionally an ADX channel definition. Preserve raw column names, units, timestamps, sensor/conversion provenance and missing values; normalize to a documented machine-readable representation. Fail closed on ambiguous channels, clocks, endian conversions and incompatible units. This is ingestion, not auto-tuning.
3. **XDL conversion (format-qualified milestone).** Add a read-only TunerPro XDL decoder only after obtaining lawful format/version evidence and synthetic plus permissioned reference fixtures. Pair any ADX metadata needed to interpret channels; compare decoded samples to native TunerPro exports. Reject unknown encodings and incomplete streams instead of guessing. A CSV export remains the fallback.
4. **Bind every log session to its source files.** Capture immutable SHA-256 for the datalog(s), baseline BIN and XDF, plus the ADX hash when applicable; record ECU/OSID and tool/adapter metadata when known. Reject a plan-to-session mismatch before edits. **PR #10's plan binds the source BIN/XDF, not the datalog**: log-to-BIN provenance requires a separate manifest or a deliberately versioned extension, not invented extra fields in `kingai.xdf-batch-plan.v1`.
5. **Evidence alignment and prompts.** Correlate logged RPM/load/channel samples to *verified* XDF axes and item identities with explicit interpolation/axis assumptions. Present sample counts, transients, closed/open-loop state when known, unit conversions and uncertainties for agent review. The agent proposes a bounded edit plan; it must not infer a confirmed causal ECU control from observed agreement alone. An on-disk coding agent should be able to read several logs without manual chat copy/paste, subject to file-owner permission.
6. **Execute plans and inspect receipts.** Preview first. With a supported executor and a sufficiently specified user-directed change, validate expected source hashes, exact XDF identity/selector, `expected_raw` when available, storage/math support, overlapping edits, quantization and final-image readback; then write only a new BIN and its audit artifacts. Compare all changed bytes and retain the original. Do not pass log-session metadata as unsupported batch-plan keys.
7. **Checksum and flasher adapters (separate qualifications).** Introduce ECU-family-specific checksum/signature handling only with independent golden fixtures and validation. Treat flashing as a separate explicit operation requiring compatible hardware, vehicle-specific recovery procedures and operator control. An editor-generated BIN or valid diff is not a flash authorization.
8. **Live tuning (later, independently gated).** First add a **read-only** acquisition/telemetry adapter with confirmed protocol, timing, fault, disconnect and replay behavior. Define whether a target truly supports online calibration writes rather than offline flash cycles. Any later write-capable mode needs platform-specific validation, bounded state changes, concurrency control, verified readback, safe stop/recovery and supervised bench/dyno testing; it must never be implied by ADX/XDL ingestion alone. No automatic live writes or flashes from unconstrained chat prompts.

No dates are promised for these stages. Each milestone is accepted only with documented fixture results, failure-path tests and clear operator guidance. This proposal should stay separate from PR #10's implementation and should not change current CLI behavior.

## ChatGPTz idea 💡 — session provenance sidecar

**AI-generated extension; inspired by** PR #10's mandatory BIN/XDF hashes and the risk of accidentally pairing a datalog with the wrong calibration image: use an immutable `kingai.log-session.v1` sidecar **proposal** to link logs, ADX, software identity, baseline BIN/XDF, operator-supplied setup and acquisition timestamps. Use content hashes for all attached source files and require explicit equality checks before any planned edit. This schema is **not implemented** or accepted by the current CLI.

The reason for a sidecar rather than silently extending the PR #10 JSON plan is schema integrity: an existing strict parser should continue to reject unknown keys. The sidecar also permits multiple logs from the same source BIN without misrepresenting the source of each pull.

## Scope, safety and privacy

This project edits **copies of files** only, within the documented current limits. Incorrect XDF mappings, AFR/wideband calibration, unit conversions, transient behavior, injector data, hardware faults, offsets, interpolated axes or model reasoning can make a mathematically precise edit wrong for the vehicle. Log correlation alone does not prove an active firmware control, causal effect or physical safety. Review and validate each change with appropriate platform expertise and controlled conditions.

Keep customer firmware, datalogs, device IDs and proprietary definitions local unless the owner explicitly permits disclosure; public regressions should use synthetic or licensed, non-sensitive fixtures. A chat interface never substitutes for checksum validation, recovery planning, legal/emissions compliance or independent controlled vehicle tests.

Related: [README](../README.md), [guided workflow](GUIDED_TUNING_AND_RESEARCH.md), [historical tuning plan](../AI_TUNING_PLAN.md), and [draft batch PR #10](https://github.com/KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor/pull/10).
