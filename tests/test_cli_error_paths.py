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


# --- v0.4.0 m1: non-UTF-8 patch metadata -------------------------------------


def _non_utf8_patch(path: Path) -> None:
    path.write_bytes(
        b"anchor_uuid: msg-0002\nrationale: \xd6\xd0\xce\xc4\n---\nbody\n"
    )


def test_read_patch_md_rejects_non_utf8(tmp_path):
    from patchmem.patch import PatchError, read_patch_md

    bad = tmp_path / "patch.md"
    _non_utf8_patch(bad)
    with pytest.raises(PatchError, match="not valid UTF-8"):
        read_patch_md(bad)


def test_diff_warns_and_renders_on_non_utf8_patch_meta(tmp_path):
    home, runs = _sandbox(tmp_path)
    _non_utf8_patch(runs / "patch.md")
    result = _run_cli(["diff", SID], home)
    assert result.returncode == 0
    assert "warning:" in result.stderr
    assert "patch metadata unreadable" in result.stderr
    assert "influence-diff" in result.stdout
    assert "UnicodeDecodeError" not in result.stdout + result.stderr


def test_resume_rejects_non_utf8_patch_cleanly(tmp_path):
    home, _runs = _sandbox(tmp_path)
    bad = tmp_path / "patch.md"
    _non_utf8_patch(bad)
    result = _run_cli(["resume", SID, "--patch", str(bad)], home)
    assert result.returncode == 1
    assert "error:" in result.stderr
    assert "not valid UTF-8" in result.stderr
    assert "UnicodeDecodeError" not in result.stdout + result.stderr


# --- v0.4.0 m2: empty evidence must not read as "patch was inert" ------------


def test_diff_refuses_inert_verdict_on_empty_arms(tmp_path):
    home, runs = _sandbox(tmp_path)
    (runs / "control.jsonl").write_text("", encoding="utf-8")
    (runs / "patched.jsonl").write_text("", encoding="utf-8")
    result = _run_cli(["diff", SID], home)
    assert result.returncode == 1
    assert "error:" in result.stderr
    assert "no tool_use decisions" in result.stderr
    assert "patch was inert" not in result.stdout


def test_diff_refuses_inert_verdict_when_both_arms_are_corrupt(tmp_path):
    home, runs = _sandbox(tmp_path)
    garbage = '{"type":"system"}\n123\n"stray"\n'
    (runs / "control.jsonl").write_text(garbage, encoding="utf-8")
    (runs / "patched.jsonl").write_text(garbage, encoding="utf-8")
    result = _run_cli(["diff", SID], home)
    assert result.returncode == 1
    assert "no tool_use decisions" in result.stderr
    assert "patch was inert" not in result.stdout


def test_diff_still_reports_inert_for_identical_valid_arms(tmp_path):
    home, _runs = _sandbox(tmp_path)
    result = _run_cli(["diff", SID], home)
    assert result.returncode == 0
    assert "patch was inert" in result.stdout


# --- v0.4.0 m3: no silent exit 0 after doing nothing -------------------------


def _valid_patch(path: Path) -> None:
    path.write_text(
        "anchor_uuid: msg-0002\nrationale: tighten plan\n---\ncorrected plan\n",
        encoding="utf-8",
    )


def test_resume_stub_exits_nonzero(tmp_path):
    home, _runs = _sandbox(tmp_path)
    patch = tmp_path / "patch.md"
    _valid_patch(patch)
    result = _run_cli(["resume", SID, "--patch", str(patch)], home)
    assert result.returncode == 1
    assert "m2 stub" in result.stdout


def test_diff_missing_arms_exits_nonzero(tmp_path):
    home, runs = _sandbox(tmp_path)
    shutil.rmtree(runs)
    result = _run_cli(["diff", SID], home)
    assert result.returncode == 1
    assert "m2 not yet run" in result.stdout


def test_diff_hosted_stub_exits_nonzero(tmp_path):
    home, _runs = _sandbox(tmp_path)
    result = _run_cli(["diff", SID, "--hosted"], home)
    assert result.returncode == 1
    assert "--hosted" in result.stdout


# --- v0.4.0 m5: explicit control/patched arm files ---------------------------


def _arm_line(uuid: str, tool_id: str, path: str) -> str:
    return json.dumps(
        {
            "type": "assistant",
            "uuid": uuid,
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": tool_id, "name": "Read", "input": {"path": path}}
                ],
            },
        }
    )


def test_diff_explicit_arm_pair(tmp_path):
    home, _runs = _sandbox(tmp_path)
    control = tmp_path / "control.jsonl"
    patched = tmp_path / "patched.jsonl"
    control.write_text(_arm_line("m1", "tool-1", "old.yaml") + "\n", encoding="utf-8")
    patched.write_text(
        _arm_line("m1", "tool-1", "new.yaml") + "\n"
        + _arm_line("m2", "tool-2", "policy.yaml") + "\n",
        encoding="utf-8",
    )
    result = _run_cli(
        ["diff", SID, "--control", str(control), "--patched", str(patched)], home
    )
    assert result.returncode == 0
    assert "altered (1)" in result.stdout
    assert "added   (1)" in result.stdout


def test_diff_explicit_arms_require_both(tmp_path):
    home, _runs = _sandbox(tmp_path)
    control = tmp_path / "control.jsonl"
    control.write_text(_arm_line("m1", "tool-1", "a.yaml") + "\n", encoding="utf-8")
    result = _run_cli(["diff", SID, "--control", str(control)], home)
    assert result.returncode == 1
    assert "must be given together" in result.stderr


def test_diff_explicit_arm_missing_file(tmp_path):
    home, _runs = _sandbox(tmp_path)
    patched = tmp_path / "patched.jsonl"
    patched.write_text(_arm_line("m1", "tool-1", "a.yaml") + "\n", encoding="utf-8")
    missing = tmp_path / "nope.jsonl"
    result = _run_cli(
        ["diff", SID, "--control", str(missing), "--patched", str(patched)], home
    )
    assert result.returncode == 1
    assert "arm file not found" in result.stderr
    assert "nope.jsonl" in result.stderr


def test_diff_explicit_patch_md_renders_header(tmp_path):
    home, _runs = _sandbox(tmp_path)
    control = tmp_path / "control.jsonl"
    patched = tmp_path / "patched.jsonl"
    line = _arm_line("m1", "tool-1", "a.yaml") + "\n"
    control.write_text(line, encoding="utf-8")
    patched.write_text(line, encoding="utf-8")
    meta = tmp_path / "patch.md"
    meta.write_text(
        "anchor_uuid: m1\nrationale: explicit arms note\n---\nbody\n", encoding="utf-8"
    )
    result = _run_cli(
        [
            "diff",
            SID,
            "--control",
            str(control),
            "--patched",
            str(patched),
            "--patch-md",
            str(meta),
        ],
        home,
    )
    assert result.returncode == 0
    assert "explicit arms note" in result.stdout
