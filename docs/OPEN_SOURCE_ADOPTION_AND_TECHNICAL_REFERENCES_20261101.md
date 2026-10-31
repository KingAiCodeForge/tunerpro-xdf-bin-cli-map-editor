# KingAI Open-Source Adoption and Technical References

**Publisher:** KingAI Pty Ltd / KingAiCodeForge  
**Report date:** 1 November 2026 (Australia/Adelaide)  
**Subject:** TunerPro XDF/BIN CLI Map Editor and TunerPro XDF+BIN Universal Exporter  
**Status:** Public-source evidence register; not a commercial-use, originality or infringement assessment.

**Projects:** [CLI Map Editor](https://github.com/KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor) | [Universal Exporter](https://github.com/KingAiCodeForge/TunerPro-XDF-BIN-Universal-Exporter)

## Executive summary

A review of public GitHub repository metadata, shared commit ancestry and third-party documentation on 1 November 2026 established:

- **Four verified direct GitHub forks** of the KingAI CLI Map Editor.
- **One source-code derivative with substantial additions:** chavezsd92-source's fork adds a JC Tuner GUI, XDF mapping, porting and Ghidra-related modules.
- **One independent comparison report:** FreeBeamer states that it used KingAI Universal Exporter v3.6.0 to validate three synthetic XDF/BIN decoding cases.
- **One technical-methodology citation:** the Shengjia AI calibration-skills project explicitly credits KingAI's porting practices and cites the editor as a source.

These are distinct forms of external attention. A fork is not proof of deployment, technical endorsement or a sale. A citation is not proof of direct code copying. The record does not establish any maintainer's private motivations, commercial licensing, customer usage, revenue or infringement.

GitHub metadata reported **four forks and 18 stars** for the KingAI CLI editor at this review date. These are changeable platform counters, not unique installation or customer counts.

## Source chronology

| Event | Date | Evidence |
| --- | --- | --- |
| Original repository created | 15 March 2026, 15:10:54 UTC (16 March in Adelaide) | [GitHub repository metadata](https://api.github.com/repos/KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor) |
| Initial AI-agent-friendly editor v1.0.0 commit | 15 March 2026, 20:15:38 UTC (16 March in Adelaide) | [Root commit](https://github.com/KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor/commit/911f243c19179b2edecadb3d1816a3cfd7a7fc53) |
| PCM Hacking public forum announcement | 1 July 2026 | [Forum thread 9330](https://pcmhacking.net/forums/viewtopic.php?t=9330) |
| First formal GitHub prerelease, v1.2.0rc1 | 20 October 2026 | [Release](https://github.com/KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor/releases/tag/v1.2.0rc1) |
| Guarded v1.2.0rc2 prerelease | 20 October 2026 | [Release](https://github.com/KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor/releases/tag/v1.2.0rc2) |

Repository creation, public visibility, forum publication and a packaged release are not interchangeable milestones. Repository creation does not prove when public visibility was first enabled.

## Four direct GitHub forks

The following repository API records report GitHub fork status and identify KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor as the **parent and source** repository.

| Fork | Created (UTC) | Observation at review |
| --- | --- | --- |
| [chavezsd92-source](https://github.com/chavezsd92-source/tunerpro-xdf-bin-cli-map-editor) | 16 July 2026, 00:09:48 | One additional source commit; extended derivative below |
| [NetworkDir](https://github.com/NetworkDir/tunerpro-xdf-bin-cli-map-editor) | 19 August 2026, 16:01:45 | Head matched its corresponding historical KingAI commit; zero independent commits in that comparison |
| [eedgurr](https://github.com/eedgurr/tunerpro-xdf-bin-cli-map-editor) | 14 October 2026, 00:31:11 | Head matched its corresponding historical KingAI commit; zero independent commits in that comparison |
| [rollsch](https://github.com/rollsch/tunerpro-xdf-bin-cli-map-editor) | 22 October 2026, 04:26:52 | Head matched its corresponding historical KingAI commit; zero independent commits in that comparison |

An unmodified snapshot is not evidence that an account has performed no private or local development.

### JC Tuner — confirmed extension of the KingAI codebase

On 16 July 2026, the chavezsd92-source fork added a commit titled **first version**, whose parent is KingAI commit 2c2385f44bc5c538b5034dccd7fd0a9c606818e0.

**Primary evidence:** [Derivative commit c639075](https://github.com/chavezsd92-source/tunerpro-xdf-bin-cli-map-editor/commit/c639075a11f07ba857ccc236852c4e26df913597).

Notable additions in that commit include:

| File | Added lines | Declared purpose |
| --- | ---: | --- |
| jc_tuner_gui.py | 3,393 | GUI |
| auto_xdf_mapper.py | 941 | Heuristic BIN/XDF candidate discovery |
| xdf_porting_engine.py | 535 | Candidate ECU calibration porting |
| ghidra_integration.py | 432 | Analysis-script generation |
| safe_tuning_workflow.py | 424 | Tuning workflow wrapper |

The workflow explicitly imports **XDFBinSession from cli_map_editor.py**, directly linking the added layer to the KingAI editor retained in the fork.

This establishes a **code-based derivative**. It does **not** establish that JC Tuner's advertised auto-mapping, porting, Ghidra integration, ECU-specific safety bounds or calibration-writing operations are qualified against real OSIDs or vehicles. Code inspection found placeholder addresses, heuristic assumptions and an apply workflow that may report success without writing a modified BIN. Use those modules for experimental research only until independently tested.

Some newly added modules contain KingAI-branded copyright headers. The headers alone cannot determine who authored those additions or whether any licence term was breached.

## Independent third-party technical references

### FreeBeamer: KingAI exporter used as a reported decoding oracle

**Repository:** [freebeamer/core](https://github.com/freebeamer/core)  
**Report:** [Phase 4 independent decoder validation](https://github.com/freebeamer/core/blob/main/docs/phase4-oracle-validation.md), dated 1 September 2026.

FreeBeamer's documentation says its decoder was compared against **KingAI TunerPro XDF + BIN Universal Exporter v3.6.0**, using [KingAI exporter commit 18697503](https://github.com/KingAiCodeForge/TunerPro-XDF-BIN-Universal-Exporter/commit/18697503fd5b1208045f667affa7c50803f6f894). It reports matching raw interpretations, dimensions, row ordering and converted values for three synthetic cases: 1×1, 1×6 and 6×6. The report explicitly limits its conclusion: absent stock firmware, it did not verify original ECU binary contents or flash readiness.

Their [XDF compatibility notes](https://github.com/freebeamer/core/blob/main/docs/xdf-compatibility.md) also cite the KingAI CLI editor/exporter when discussing XDF axis labels and flag-mask interpretation.

**Evidence classification:** Documented use of KingAI software as an independent technical comparison and reference. **Not evidence of verbatim code porting.**

### Shengjia: explicit methodological attribution

**Repository:** [liushengjia-AAL/shengjia](https://github.com/liushengjia-AAL/shengjia).

The [reference-tune-porting skill](https://github.com/liushengjia-AAL/shengjia/blob/main/reference-tune-porting/SKILL.md) explicitly attributes a porting classification approach to the practices of KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor. The [reverse-engineering discipline reference](https://github.com/liushengjia-AAL/shengjia/blob/main/ecu-calibration-doctrine/references/re-discipline.md) also names the KingAI editor among source repositories.

**Evidence classification:** Explicit technical-methodology reference. **No demonstrated direct code import or partnership.**

## Other editor projects: no copying claim supported

A limited search of public default-branch content for [ZedSuite](https://github.com/LeZed97/ZedSuite), [LibreTune](https://github.com/RallyPat/LibreTune), [Tune Editor](https://github.com/TheFlashBold/tune-editor), [Serpentine](https://github.com/flexadecimal/serpentine) and [Denso ECU Toolkit](https://github.com/PabloSoage/Denso-ECU-Toolkit) found no direct KingAI references in the inspected queries. This is not a complete code-similarity audit across all versions, branches, compiled products or private repositories. It cannot establish either copying or non-use. Feature similarity and publication chronology are not sufficient evidence of copying.

## Licence and attribution boundaries

The original KingAI CLI repository is published under the **MIT licence**, which generally permits copying, modification and redistribution subject to preserving applicable copyright and permission notices. Whether a particular derivative satisfies all obligations requires a specific notice/distribution inspection. This register is **not** an allegation of infringement.

No public evidence examined establishes commercial deployments, paying customers, formal collaborations, private engineering assessments or direct quotations about the developers' motives.

## Recommended externally defensible statement

> KingAI's open-source ECU calibration tools have verifiable external technical references. Four GitHub accounts have forked the CLI Map Editor, including one fork with a substantial JC Tuner GUI and analysis extension. Separately, FreeBeamer documented comparisons against the KingAI Universal Exporter, and Shengjia's AI calibration documentation credits KingAI's porting practices. These references demonstrate publicly documented reuse and technical attention, but do not establish commercial adoption or independently verified ECU safety.

## Verification method and maintenance

- Check GitHub fork/source metadata, commit parents and compare ancestry rather than inferring copying from similar functionality.
- Retain exact repository URLs, commit SHAs, dates and the limitations stated by third-party authors.
- Recheck mutable star/fork counters before quoting them in future marketing.
- Keep third-party safety and OSID-compatibility claims separate from validated KingAI capabilities.
- Record additional independently verifiable customer pilots, licences, external pull requests and deployments only if evidence actually becomes available.

**ChatGPTz idea — evidence maintenance:** Publish a new dated snapshot when meaningful adoption evidence changes, instead of silently rewriting historical counts or extrapolating intention from forks. Inspired by reproducible software provenance and audit-trail practice.

---

**Provenance:** Prepared at the user's request on 1 November 2026 from public GitHub metadata, commit ancestry and linked third-party documents. No private BINs, XDFs, customer files, credentials or machine paths are included.
