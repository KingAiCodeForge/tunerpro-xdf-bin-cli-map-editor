# Guided AI tuning and reverse-engineering workflow

Updated 23 October 2026 (ACDT). Documentation only; no new CLI capability.

**Operator warning:** AI can select the wrong maps, misinterpret definitions or propose unsuitable values. Do not use this tool for tuning unless you understand the ECU/platform, or are working with a competent tuner who does. Independently verify the exact BIN/XDF pairing, selected controls and resulting changes. A successful edit does not prove calibration safety or flash readiness.

## 1. Human direction, not unnecessary ceremony

The human provides the outcome, vehicle/hardware context, constraints and
allowed scope. The agent translates that into identified controls and supported
file operations. The human does not need to supply internal map IDs when the
agent can resolve them from verified exact-target guidance.

A direct instruction to apply a specified supported change, or an already
agreed change plan, is sufficient direction for that file edit. Do not require
a separate approval document, approval flag in a plan, digital signature, or
repeated confirmation for every cell. Explain the selected controls and why.

If the goal leaves important choices unresolved, ask a focused question.
"Figure it out" authorizes investigation and evidence-backed proposals, not
invented map semantics, arbitrary numeric targets or unrequested flashing.
Respect any additional permissions required by the operating environment.

## 2. Two workflows

### Established tuning

Use applicable platform guides, known control relationships, characterized
hardware data and retained evidence for the exact software/layout/definition.
Reuse established proof; fresh disassembly is not required for every edit.
Check that changed inputs or definitions have not invalidated that proof.

Record the exact input identities, inspect the selected controls, explain
their purpose and relevant dependencies, make only supported requested edits,
then re-read the output and inspect the complete byte difference.

A known map does not by itself determine a suitable value for every engine.
Ask for missing hardware or operating evidence when it affects the decision.

### Reverse engineering

Unknown meanings are normal. Separate observations, hypotheses and confirmed
findings. Use disassembly, code/data references, selectors, controlled edits,
matching exports, native-editor comparisons and suitable logs as appropriate.

Do not label a candidate from a plausible title, table shape or similar OSID
alone. State "I don't know yet" with the exact missing fact and a practical
next test. Preserve research variants rather than presenting them as finished
tuning definitions.

Logs can help validate operating behaviour, but do not alone prove which BIN
address implements it. Static tracing can establish an intermediate operation
without proving final actuator behaviour or every runtime state.

## 3. Three different checks

1. Identification: is this the intended control on this exact target, with
   the correct selector, axes, units and applicable evidence?
2. Editing: were requested values encoded correctly, with supported math,
   storage and bounds, and without unintended byte changes?
3. Vehicle validation: did the intended effect occur under appropriate
   controlled testing without unacceptable side effects?

These are different evidence questions, not three repetitions of an AI answer.
The editor's technical checks do not certify tune safety, physical limits,
map dependencies or hardware suitability.

Keep original files immutable, retain hashes and tool revisions, use new output
files, inspect raw and decoded values, preserve audit records and investigate
unexpected differences. Never bypass unsupported math or a failed guard with
an ad-hoc hex write merely to complete a request.

## 4. Single edits and batch development

At the reviewed main revision 0dda2b9894219a778a296e74ca5c963c35e048e8,
single table/range, scalar and flag edits are supported within the README's
limits. Batch, port and standalone save remain disabled.

[PR #10](https://github.com/KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor/pull/10)
is a separate, unmerged transactional batch candidate. Reviewed head:
5ee15d3ca185c5b684e3baee48d0e033dc7db4ae.
Check its current state before using it; this document does not merge it.

That candidate accepts strict JSON plans and CSV operations. Its JSON plan
binds source BIN and XDF hashes; expected old raw values are currently optional.
It does not implement mandatory human-approval artifacts. Markdown and JSONL
are not batch inputs, and a whole exported snapshot is not an edit plan.
It does not provide an automatic diff-to-copy-selected-maps workflow.

Preferred design for future integrations:
- JSON: authoritative structured edit plan, validated against its actual schema.
- CSV: convenient tabular input translated into the same validated operations.
- Markdown: readable explanation and review report, not executable instructions.
- JSONL: optional event/audit stream, not a currently supported batch input.

These format roles are design guidance, not newly implemented interfaces.
Keep evidence, scope and explanatory metadata in a companion report unless the
actual parser schema permits those fields. Do not add unsupported keys.

Prefer one coherent change set. A single scalar or table can remain one edit;
related changes may need staging and final-image validation together once a
qualified batch implementation is available. Larger batches are not inherently
better. Preserve deterministic checks regardless of whether confirmation is
interactive.

## 5. Comparing and transferring

The released diff tool can compare bytes and optionally attribute changes
through an XDF. Comparing two files does not automatically authorize copying
all differences. Select only intended, identified calibration changes.

A future transfer planner should retain source/target hashes and expected old
values, detect pre-existing target edits, reject conflicts and report unknown
bytes. Similar dimensions or axis values across OSIDs are candidate evidence,
not proof of equivalence. Cross-OSID transfer needs separately verified mapping;
do not copy offsets or code patches merely because names match.

## 6. Completion report

Report what was requested, which controls were selected and why, exact input
and output hashes, tool/dependency revisions, raw and engineering before/after
values, changed offsets, executed checks, failures and unresolved evidence.

Checksum handling, native-editor parity, flashing, recovery and vehicle testing
must be reported separately. Producing a new BIN does not authorize an ECU
write or make it flash-ready. Say explicitly what was not performed.

See [README](../README.md), [AGENTS](../AGENTS.md) and
[the historical implementation roadmap](../AI_TUNING_PLAN.md).
