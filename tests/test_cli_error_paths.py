"""m9-m12 tests — the CLI boundary error contract against corrupt operator state.

Every case here reproduced a raw traceback at v0.2.0 (verified at runtime in
a sandbox HOME). The contract under test: corrupt input state fails with a
clean one-line ``error:``/``warning:`` message and the documented exit code —
never an unhandled exception leaking through the CLI.

Corrupt-state classes covered:
* m9 — a malformed or mistyped ``~/.patchmem/config.toml`` (read by EVERY
  command) reports ``ConfigError`` cleanly instead of a TOMLDecodeError /
  TypeError traceback.
* m10 — a non-object JSON line in a replayed arm is skipped by ``diff``
  instead of AttributeError-crashing.
* m11 — a malformed runs-dir patch metadata file warns and renders instead
  of PatchError-crashing the whole diff.
* m12 — a transcript with invalid UTF-8 bytes raises a clean
  ``TranscriptError`` instead of a UnicodeDecodeError traceback.

All CLI checks run in a sandbox HOME (env redirect) so the real
``~/.patchmem`` is never touched; subprocess style matches
tests/test_transcript_robustness.py.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from patchmem.config import ConfigError, load_config
from patchmem.influence_diff import diff_from_transcripts
from patchmem.models import Patch, TextBlock
from patchmem.transcript import TranscriptError, parse_session

FIXTURE = Path(__file__).parent / "fixtures" / "sample_session.jsonl"
SID = "fixture-0001"


def _assistant_lines() -> list[str]:
    return [
        ln
        for ln in FIXTURE.read_text(encoding="utf-8").splitlines()
        if ln.strip() and json.loads(ln).get("type") == "assistant"
    ]


def _sandbox(tmp_path: Path) -> tuple[Path, Path]:
    """A HOME with the fixture session + valid replay arms; returns (home, runs)."""
    home = tmp_path / "home"
    (home / ".claude" / "projects" / "proj").mkdir(parents=True)
    runs = home / ".patchmem" / "runs" / SID
    runs.mkdir(parents=True)
    shutil.copy(FIXTURE, home / ".claude" / "projects" / "proj" / f"{SID}.jsonl")
    arms = "\n".join(_assistant_lines()) + "\n"
    (runs / "control.jsonl").write_text(arms, encoding="utf-8")
    (runs / "patched.jsonl").write_text(arms, encoding="utf-8")
    return home, runs


def _run_cli(args: list[str], home: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "HOME": str(home)}
    return subprocess.run(
        [sys.executable, "-m", "patchmem.cli", *args],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        check=False,
    )


# --- m9: config.toml crash family ------------------------------------------


def test_load_config_raises_config_error_on_malformed_toml(tmp_path):
    bad = tmp_path / "config.toml"
    bad.write_text("runtime = oops\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_config(bad)


def test_load_config_rejects_non_string_paths(tmp_path):
    bad = tmp_path / "config.toml"
    bad.write_text("projects_dir = 123\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="projects_dir"):
        load_config(bad)


def test_malformed_config_toml_reports_clean_error(tmp_path):
    home, _runs = _sandbox(tmp_path)
    cfg = home / ".patchmem" / "config.toml"
    cfg.write_text("runtime = oops\n", encoding="utf-8")
    result = _run_cli(["view", SID], home)
    assert result.returncode == 1
    assert "error:" in result.stderr
    assert "invalid TOML" in result.stderr
    assert "TOMLDecodeError" not in result.stdout + result.stderr


def test_nonstring_config_value_reports_clean_error(tmp_path):
    home, _runs = _sandbox(tmp_path)
    cfg = home / ".patchmem" / "config.toml"
    cfg.write_text("projects_dir = 123\n", encoding="utf-8")
    result = _run_cli(["view", SID], home)
    assert result.returncode == 1
    assert "error:" in result.stderr
    assert "projects_dir" in result.stderr
    assert "TypeError" not in result.stdout + result.stderr


def test_valid_config_still_loads_and_view_renders(tmp_path):
    home, _runs = _sandbox(tmp_path)
    cfg = home / ".patchmem" / "config.toml"
    cfg.write_text(
        f'projects_dir = "{home / ".claude" / "projects"}"\n',
        encoding="utf-8",
    )
    result = _run_cli(["view", SID], home)
    assert result.returncode == 0
    assert "session" in result.stdout


# --- m10: non-object JSON line in a replayed arm -----------------------------


def test_diff_skips_non_object_arm_lines(tmp_path):
    home, runs = _sandbox(tmp_path)
    with (runs / "control.jsonl").open("a", encoding="utf-8") as fh:
        fh.write("123\n")
        fh.write('"a stray json string"\n')
    result = _run_cli(["diff", SID], home)
    assert result.returncode == 0
    assert "influence-diff" in result.stdout
    assert "AttributeError" not in result.stdout + result.stderr


def test_diff_from_transcripts_skips_non_object_lines():
    line = json.dumps(
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "toolu_1", "name": "Bash", "input": {}}
                ],
            },
        }
    )
    diff = diff_from_transcripts(
        Patch(anchor_uuid="m1", block=TextBlock(text="p")),
        [line, "123", '"stray"'],
        [line],
    )
    # The bare-number/string lines are skipped; the valid decision survives.
    assert [d.id for d in diff.control_decisions] == ["toolu_1"]
    assert [d.id for d in diff.patched_decisions] == ["toolu_1"]
    assert diff.changed == []


# --- m11: malformed runs-dir patch metadata ----------------------------------


def test_diff_warns_and_renders_on_malformed_patch_meta(tmp_path):
    home, runs = _sandbox(tmp_path)
    (runs / "patch.md").write_text(
        "anchor_uuid: \nrationale: x\n---\nbody\n", encoding="utf-8"
    )
    result = _run_cli(["diff", SID], home)
    assert result.returncode == 0
    assert "warning:" in result.stderr
    assert "patch metadata unreadable" in result.stderr
    assert "influence-diff" in result.stdout
    assert "PatchError" not in result.stdout + result.stderr


def test_diff_renders_wellformed_patch_meta(tmp_path):
    home, runs = _sandbox(tmp_path)
    (runs / "patch.md").write_text(
        'anchor_uuid: msg-0002\nrationale: tighten the plan\n---\ncorrected plan\n',
        encoding="utf-8",
    )
    result = _run_cli(["diff", SID], home)
    assert result.returncode == 0
    assert "tighten the plan" in result.stdout


# --- m12: invalid UTF-8 transcript -------------------------------------------


def test_invalid_utf8_transcript_raises_clean_transcript_error(tmp_path):
    p = tmp_path / "bad-utf8.jsonl"
    p.write_bytes(
        b'{"type":"user","parentUuid":null,"message":{"role":"user",'
        b'"content":"\xff\xfe bad"},"uuid":"m1","timestamp":"t"}\n'
    )
    with pytest.raises(TranscriptError, match="not valid UTF-8"):
        parse_session(p)


def test_invalid_utf8_transcript_reports_clean_cli_error(tmp_path):
    home, _runs = _sandbox(tmp_path)
    (home / ".claude" / "projects" / "proj" / "bad-utf8.jsonl").write_bytes(
        b'{"type":"user","message":{"role":"user","content":"\xff"},"uuid":"m1"}\n'
    )
    result = _run_cli(["view", "bad-utf8"], home)
    assert result.returncode == 1
    assert "error:" in result.stderr
    assert "not valid UTF-8" in result.stderr
    assert "UnicodeDecodeError" not in result.stdout + result.stderr
