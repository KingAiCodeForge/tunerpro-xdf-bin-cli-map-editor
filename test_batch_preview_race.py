"""Read-only batch previews must detect source changes during staging."""
from pathlib import Path

import pytest
import transactional_batch as batch
from test_transactional_batch_unit import FakeSession, setup, ranges, state


@pytest.mark.parametrize('changed_source', ['csv', 'bin', 'xdf'])
def test_preview_rejects_mutated_source_even_without_autosave(tmp_path, monkeypatch, changed_source):
    args, original = setup(tmp_path, [('scalar','MAP Linear','','','3','false')], autosave=False)
    previous = original.read_bytes()
    target = Path(getattr(args, changed_source))
    before = target.read_bytes()
    real_verify = batch._verify_final

    def tamper_after_validation(*params):
        changed = real_verify(*params)
        target.write_bytes(before + b'externally-updated')
        return changed

    monkeypatch.setattr(batch, '_verify_final', tamper_after_validation)
    with pytest.raises(ValueError, match='changed while staging'):
        batch.run_batch(args, FakeSession, ranges, state)
    assert not (tmp_path/'out').exists()
    assert FakeSession.last.changes != []  # staged in memory but never published
    assert Path(args.bin).read_bytes() == (previous if changed_source != 'bin'
                                         else previous + b'externally-updated')
