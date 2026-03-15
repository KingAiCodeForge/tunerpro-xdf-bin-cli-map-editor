# Future Paths and Ideas

Ideas, potential integrations, and directions for this project. Not promises — just documented thinking.

---

## MCP Tool Server

Wrap the CLI commands as an MCP (Model Context Protocol) tool server. Any MCP-compatible agent (VS Code Copilot, Claude Desktop, custom clients) could call `show-map`, `edit`, `port`, etc. as structured tool calls instead of parsing terminal output.

What this needs:
- Thin MCP wrapper around each `cmd_*` function
- JSON output mode (most commands already produce structured text, but native JSON would be cleaner)
- Auth/session management for multi-user setups

## Local LLM Integration

The CLI already works with any agent that has terminal access. But a tighter integration with local models (Ollama, llama.cpp, vLLM) could include:
- A system prompt template that teaches the model the command set
- Example conversation flows for common tuning tasks
- Structured output parsing helpers

No API keys, no cloud dependency. The model runs locally, reads maps, proposes changes, the human approves.

## API Mode

A REST or WebSocket API wrapper for remote access. Fork this, add your own auth, and expose it as a service. Not planned for this repo — this stays as the CLI backbone.

## Datalog-Driven Tuning Loop

Connect datalog analysis to the edit loop:
1. Import datalogs (CSV from TunerPro, HP Tuners, EFILive, or ALDL)
2. Agent analyzes AFR errors, knock events, timing deviations
3. Agent proposes specific cell edits with reasoning
4. Human reviews and approves
5. New BIN is written with full edit log

This is where AI tuning stops being "ChatGPT gives you advice" and becomes "agent reads your data and writes precise corrections."

## Checksum Integration

Currently this tool does NOT compute ECU checksums. Adding checksum correction for specific ECU families:
- Siemens MS41/MS42/MS43/MS45 — known algorithms
- Delco 68HC11 (Holden VN-VY) — known algorithms
- Bosch ME7.x — partially documented

This would close the loop from edit to flashable BIN.

## Cross-Platform Porting Expansion

The `port` command already handles MS42↔MS43 (410 common tables). Expanding to:
- MS42/MS43 → MS45 (M54 engine family)
- Holden VT/VX/VY V6 Enhanced OS cross-porting
- Generic name-matching with configurable mapping CSVs

## A2L/DAMOS Support

BMW ecosystem has A2L (ASAP2) and DAMOS definition files alongside XDFs. Adding A2L import would:
- Allow direct use of OEM calibration definitions
- Enable cross-referencing XDF tables against factory names
- Open up Bosch ECUs that have A2L but no XDF

## WinOLS Map Pack Import

WinOLS `.ols` map pack format is widely used in the tuning community. Importing OLS definitions as an alternative to XDF would dramatically expand the supported ECU base.

---

## Related Projects

| Project | Repo | Relationship |
|---------|------|-------------|
| **TunerPro XDF+BIN Universal Exporter** | [KingAiCodeForge/TunerPro-XDF-BIN-Universal-Exporter](https://github.com/KingAiCodeForge/TunerPro-XDF-BIN-Universal-Exporter) | Upstream parsing engine. This CLI editor's `tunerpro_exporter_for_cli_editor_version.py` is cloned from the exporter. Fixes flow both ways. |
| **VY V6 Assembly Modding** | [KingAiCodeForge/kingaustraliagg-vy-l36-060a-enhanced-asm-patches](https://github.com/KingAiCodeForge/kingaustraliagg-vy-l36-060a-enhanced-asm-patches) | ASM patches for the Enhanced binary. The CLI editor can read/write the maps that these patches modify. |
| **KingAi VY V6 Commo Flasher** | [KingAiCodeForge/KingAi-VY-V6-L36-Commo-Flasher](https://github.com/KingAiCodeForge/KingAi-VY-V6-L36-Commo-Flasher) | Flash tool for the same ECU platform. Future: CLI editor produces BIN → flasher writes it to ECU. |
| **KingAi 68HC11 C Compiler** | [KingAiCodeForge/KingAi_68HC11_C_Compiler](https://github.com/KingAiCodeForge/KingAi_68HC11_C_Compiler) | Cross-compiler and disassembler for the same 68HC11 Delco ECUs. Complementary tooling for firmware-level work vs calibration-level work. |
| **Atlas** | [MOTTechnologies/atlas](https://github.com/MOTTechnologies/atlas) | Open-source GUI tuning software (Java, AGPL-3.0). GUI-based, no CLI. Different approach to the same problem space. |
| **ecushark / xdfbinext** | Various GitHub repos | Read-only XDF parsers. Can extract and display data but cannot write back. |

---

## What This Is Not

- Not a consumer GUI application
- Not a replacement for professional dyno tuning
- Not a checksum calculator (yet)
- Not an ECU flasher — it produces BIN files, it doesn't write them to hardware
- Not responsible for engine damage from untested tunes
