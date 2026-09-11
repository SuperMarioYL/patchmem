"""m6 tests — transcript robustness against non-object JSONL lines.

The v0.1.0 defect (verified on tag v0.1.0): a transcript line that is valid
JSON but not an object (a bare string / number) crashed every command —
``_iter_jsonl`` only guarded ``json.JSONDecodeError``, so
``parse_session``'s ``obj.get("type")`` raised a raw
``AttributeError: 'str' object has no attribute 'get'`` traceback and the
CLI's friendly ``TranscriptError`` handler never fired.

These tests pin the fixed contract: such a line raises ``TranscriptError``
carrying ``path:lineno``, the CLI prints the clean one-line error, and
well-formed transcripts keep parsing unchanged.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from patchmem.transcript import TranscriptError, parse_session

FIXTURE = Path(__file__).parent / "fixtures" / "sample_session.jsonl"

_WELLFORMED_LINE = json.dumps(
    {
        "type": "user",
        "parentUuid": None,
        "uuid": "u1",
        "message": {"role": "user", "content": "hi"},
    }
)


def _corrupted(tmp_path: Path, bad_line: str) -> Path:
    p = tmp_path / "corrupted.jsonl"
    p.write_text(
        _WELLFORMED_LINE + "\n" + bad_line + "\n" + _WELLFORMED_LINE + "\n",
        encoding="utf-8",
    )
    return p


def test_bare_json_string_line_raises_transcript_error_with_lineno(tmp_path):
    p = _corrupted(tmp_path, '"a stray json string line"')
    with pytest.raises(TranscriptError, match=r"corrupted\.jsonl:2.*not a JSON object"):
        parse_session(p)


def test_bare_json_number_line_raises_transcript_error(tmp_path):
    p = _corrupted(tmp_path, "42")
    with pytest.raises(TranscriptError, match=r":2:"):
        parse_session(p)


def test_invalid_json_still_raises_transcript_error(tmp_path):
    # Regression guard: the pre-existing invalid-JSON path is unchanged.
    p = _corrupted(tmp_path, "{not json")
    with pytest.raises(TranscriptError, match="invalid JSON"):
        parse_session(p)


def test_wellformed_fixture_still_parses():
    messages = parse_session(FIXTURE)
    assert len(messages) == 10


def test_cli_reports_friendly_error_for_corrupted_transcript(tmp_path):
    p = _corrupted(tmp_path, '"a stray json string line"')
    result = subprocess.run(
        [sys.executable, "-m", "patchmem.cli", "view", str(p)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert "Traceback" not in combined
    assert "not a JSON object" in combined
    assert "error:" in combined
