"""m4 tests — `patchmem edit` editor spawning.

The v0.1.0 defect (verified on tag v0.1.0): `open_editor` passed the whole
`$EDITOR` string as one argv element, so any editor carrying a flag
(``code --wait``, ``vim -f``, ``cat -u``) crashed with a raw
``FileNotFoundError`` traceback. These tests pin the fixed contract:

* a flagged editor command round-trips the buffer (flag = own argv element),
* an unlaunchable editor raises ``PatchError`` (clean CLI error), not
  ``FileNotFoundError``,
* a plain single-word editor keeps working.
"""

from __future__ import annotations

import pytest

from patchmem.patch import PatchError, open_editor


@pytest.fixture(autouse=True)
def _no_visual_env(monkeypatch):
    # VISUAL must not shadow EDITOR in these tests.
    monkeypatch.delenv("VISUAL", raising=False)


def test_open_editor_accepts_editor_command_with_flags(monkeypatch):
    # Fail-before on v0.1.0: FileNotFoundError: 'cat -u' (the whole string
    # was one argv element). After the fix the flag is split off and `cat`
    # runs, leaving the buffer untouched for the round-trip read.
    monkeypatch.setenv("EDITOR", "cat -u")
    assert open_editor("hello\npatchmem buffer\n") == "hello\npatchmem buffer\n"


def test_open_editor_missing_editor_raises_patcherror(monkeypatch):
    monkeypatch.setenv("EDITOR", "patchmem-no-such-editor-xyz")
    with pytest.raises(PatchError, match="patchmem-no-such-editor-xyz"):
        open_editor("buffer")


def test_open_editor_plain_editor_still_works(monkeypatch):
    monkeypatch.setenv("EDITOR", "cat")
    assert open_editor("plain roundtrip") == "plain roundtrip"


def test_open_editor_nonzero_exit_raises_patcherror(monkeypatch):
    # `false` exits 1 without touching the buffer — the operator aborted.
    monkeypatch.setenv("EDITOR", "false")
    with pytest.raises(PatchError, match="exited with status"):
        open_editor("buffer")
