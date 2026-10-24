# Contributing to KingAI CLI Map Editor

KingAI Pty Ltd welcomes focused pull requests, forks, code review, test cases, documentation corrections, hardware-adapter proposals and constructive technical feedback.

The **KingAI-owned Editor code is MIT licensed**. You may use, fork, modify and redistribute it under the [LICENSE](LICENSE) terms. Contributions to the MIT-licensed Editor should be your own work or material you have permission to contribute on compatible terms. **Third-party TunerPro plugins, DLLs, definitions, hardware drivers, ECU images and other peoples' code are not automatically MIT-licensed**, even when found publicly online.

The project is a **deterministic XDF/BIN inspection and guarded file editor**, designed for humans using AI coding agents or the terminal. It does **not** presently include a live ECU tuner, general checksum repair or flasher. See [README.md](README.md), [AGENTS.md](AGENTS.md), [hardware and checksum adapter roadmap](docs/HARDWARE_CHECKSUM_FLASH_PLUGIN_ROADMAP.md) and [the separate ADX/XDL tuning proposal, PR #11](https://github.com/KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor/pull/11).

## Ways to help

1. **Review an existing PR**, including reported execution evidence and untested assumptions. In particular, [PR #10](https://github.com/KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor/pull/10) is a *draft*, not a released batch implementation.
2. **Open an issue** with a specific reproducible bug, feature proposal, supported platform report or API question. Include the exact current version/branch and expected versus observed behaviour.
3. **Fork and submit a small PR** for one issue: a parser regression, checksum verifier, synthetic fixture, hardware-interface mock, docs/UX improvement or narrowly specified adapter contract. Independent experiments in forks are welcome; do not represent them as official support.
4. **Supply reviewable evidence**: an independently generated synthetic fixture, public-domain/appropriately licensed test vector, native TunerPro comparison, a public build log, or a reproduction that does not expose customer data. Reviews and good questions are as valuable as code.
5. **Contact the maintainer** through a GitHub issue or PR. Commercial partnership and permissioned integration enquiries may be sent to **Jason.king@kingai.com.au** (KingAI Pty Ltd). Do not send confidential ECU files or customer logs without first agreeing on a secure channel.

## Recommended first PR

Choose **one** tested change. Examples:

- A new synthetic golden image and fail-closed regression for one *existing* checksum verification profile.
- A read-only mock interface for a specific transport, with disconnect/reconnect and timeout tests; no actual ECU writes.
- A narrow native TunerPro vs XDF/BIN decoding discrepancy, with clean fixture and exact version identity.
- Documentation describing a particular device DLL ABI and its licence, without uploading the binary.
- Improved JSON receipts, diagnostics or reproducible packaging tests that preserve current fail-closed behavior.

Do not bundle a large “all ECUs supported” feature, generic checksum repair or unreviewed flasher logic into a first PR. Those require target-specific, independently verified evidence.

## Pull request quality bar

Each PR should include:

- **What changes:** the exact feature/bug, affected files and non-goals.
- **Where it applies:** tool version/commit, parser version, OS/runtime, ECU software/hardware IDs if relevant, file size/layout and stated confidence.
- **Provenance:** original source, licence/permission for borrowed or reverse-engineered material and attribution. Publicly viewable is not the same as redistributable. Keep commercial/vendor plugin DLLs external unless their licence explicitly permits bundling.
- **Tests run:** exact commands, versions, counts and output, plus what was not tested. Where applicable, run `python -m pytest -q`, inspect installed-package smoke, and verify an exact synthetic/native fixture. A successful fake-data test is not hardware qualification.
- **Failure cases:** missing/invalid input, mismatched BIN/XDF/log, ambiguous definition, unsupported math, stale source hash, wrong driver/ABI/architecture and interrupted operation where applicable.
- **Boundaries:** avoid claims of universal compatibility, automatic calibration quality, checksum-complete flash readiness or vehicle safety based on local unit tests.
- **Public safety/privacy:** no unlicensed ECU firmware/XDFs, customer datalogs, VINs, immobiliser data, private tokens, absolute local paths, proprietary device drivers, or passwords.

A hardware-writing PR additionally needs a separate design review, target-specific adapter implementation, a read-only/mock qualification track, explicit operator control, verified recovery procedures and independent physical test evidence. A hardware interface or DLL being present is **not proof** the operator or ECU supports a safe write.

## Review procedure

Fork the repository and develop against the current `main` or a specifically named prerequisite PR. Keep unrelated work in separate branches. Do not overwrite other contributors' changes or silently change a published release contract. In the PR description, distinguish **implemented**, **simulated**, **reviewed** and **not yet verified**. Do not merge major hardware or checksum claims without real target-specific evidence.

For correctness, test the **full-image changed-byte diff**, not just the map value shown by an XDF. Reject mismatched source hashes, unsupported storage/math, unexpected edits, unknown checksum layers and incorrect readback. For pure documentation, check internal links and avoid wording that claims a future adapter already ships.

Reviewers are encouraged to identify uncertain assumptions, suggest safer APIs, provide independently verifiable vectors and submit follow-up PRs. Questions and constructive technical criticism are welcome.

## Licence and community boundary

The Editor's [MIT licence](LICENSE) allows forking, commercial and non-commercial use under its notice requirements. It carries **no warranty**. Reusing a separate third-party plugin may require a different licence, architecture, host application or explicit vendor permission. A reverse-engineered implementation still needs provenance and a lawful distribution basis; do not treat it as public domain by default.

Ideas and contributions are welcomed without any implied warranty or promise of integration. **AI-generated design proposals should be visibly marked `ChatGPTz idea 💡`** (or equivalent), stating what inspired them and what is still unproven. Keep community contributions and maintainer-directed features distinguishable.
