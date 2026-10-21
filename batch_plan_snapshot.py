"""Read one immutable-on-read batch plan snapshot, independent of XDF parsing.

The plan's recorded hash must describe the **same bytes** used by its parser.
Taking a digest in a separate read after parsing creates a race in which a
reported SHA-256 identifies a different plan than the one actually staged.

A later on-disk rehash is still required before publishing any new BIN.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

MAX_PLAN_BYTES = 32 * 1024 * 1024


def snapshot_plan(path: str | Path, *, limit: int = MAX_PLAN_BYTES) -> tuple[bytes, str]:
    """Return byte-exact plan and its SHA-256, without following a second read.

    The caller must parse ``payload`` rather than reopening ``path``. Require
    a nonempty UTF-8 input in the caller; CSV and JSON have separate grammars.
    ``limit`` bounds memory use and prevents an unbounded initial read.
    """
    if type(limit) is not int or limit < 1:
        raise ValueError('Plan byte limit must be a positive integer')
    with open(path, 'rb') as handle:
        payload = handle.read(limit + 1)
    if len(payload) > limit:
        raise ValueError(f'Batch plan exceeds {limit} byte limit')
    if not payload:
        raise ValueError('Batch plan is empty')
    if b'\x00' in payload:
        raise ValueError('Batch plan contains a NUL byte')
    return payload, hashlib.sha256(payload).hexdigest()
