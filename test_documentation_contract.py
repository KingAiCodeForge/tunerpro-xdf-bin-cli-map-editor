"""Keep current BMW examples aligned with the executable CLI contract."""
from pathlib import Path
import re
import shlex
import sys

import cli_map_editor as editor


GUIDE = Path(__file__).with_name("BMW_MS42_MS43_MS43X_AI_TUNING_GUIDE.md")


def test_current_bmw_command_examples_parse_without_io(monkeypatch):
    text = GUIDE.read_text(encoding="utf-8")
    section = text.split("## Commands that exist today", 1)[1].split(
        "### XDF edit or direct binary patch?", 1
    )[0]
    examples = [line for line in section.splitlines()
                if line.startswith("python cli_map_editor.py ")]
    assert len(examples) == 9
    invoked = []
    for name in dir(editor):
        if name.startswith("cmd_"):
            monkeypatch.setattr(editor, name, lambda args: invoked.append(args) or 0)
    for line in examples:
        normalized = re.sub(r"<[^>]+>", "1", line)
        monkeypatch.setattr(sys, "argv", shlex.split(normalized)[1:])
        assert editor.main() == 0
    assert len(invoked) == len(examples)
    edits = [args for args in invoked if args.command == "edit"]
    assert len(edits) == 1
    assert edits[0].autosave is True
    assert edits[0].output_dir
    assert not {"batch", "save", "port"}.intersection(
        args.command for args in invoked
    )


def test_bmw_examples_do_not_claim_missing_native_proof():
    text = GUIDE.read_text(encoding="utf-8")
    throttle = text.split("### 1. Throttle-response candidate", 1)[1].split(
        "### 2.", 1
    )[0]
    assert "`CLI_CHECKED`, not flash approval" in throttle
    assert "still needs native TunerPro parity" in throttle
    ds2 = text.split("The preferred first ASM proof", 1)[1].split("### 8.", 1)[0]
    assert "`CLI_CHECKED / BENCH_NEXT`" in ds2
    assert "`STATIC_PROVED` grade defined above is not claimed" in ds2
    assert "The CLI `port` command is disabled." in text
