"""m8 tests — version lockstep across every surface.

Every grep-able version surface must report the same version: the VERSION
file, the pyproject manifest, ``patchmem.__version__``, the CLI
``--version`` output, the CHANGELOG sections, and — where the checkout
carries the site — ``web/site.json`` ``meta.content_version``.

The console-script check runs the script installed alongside the current
interpreter (skipped when absent) so environments without the installed
entry point stay green; the in-process CLI check goes through
``sys.executable -m patchmem.cli``.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path
from unittest import skipUnless

import pytest

import patchmem

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "0.2.0"


def test_version_file():
    assert (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip() == EXPECTED


def test_pyproject_version():
    with (REPO_ROOT / "pyproject.toml").open("rb") as fh:
        project = tomllib.load(fh)
    assert project["project"]["version"] == EXPECTED


def test_dunder_version():
    assert patchmem.__version__ == EXPECTED


def test_changelog_has_both_release_sections():
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "[0.1.0]" in changelog
    assert "[0.2.0]" in changelog


def test_cli_dash_version_reports_expected():
    result = subprocess.run(
        [sys.executable, "-m", "patchmem.cli", "--version"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
    assert EXPECTED in result.stdout


# The console script installed alongside the interpreter running the tests
# (CI does `pip install -e .` before pytest, landing `patchmem` in the same
# bin dir as python). Resolving via PATH instead would pick up unrelated
# stale installs on developer machines.
_CONSOLE_SCRIPT = Path(sys.executable).resolve().parent / "patchmem"


@skipUnless(_CONSOLE_SCRIPT.exists(), "patchmem console script not installed in this environment")
def test_console_script_dash_version_reports_expected():
    result = subprocess.run(
        [str(_CONSOLE_SCRIPT), "--version"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
    assert EXPECTED in result.stdout


def test_site_json_content_version():
    site = REPO_ROOT / "web" / "site.json"
    if not site.exists():
        # The site file only exists where the web surface ships (main); it
        # is not part of the v0.1.0-based source tree.
        pytest.skip("web/site.json not present in this checkout")
    meta = json.loads(site.read_text(encoding="utf-8")).get("meta", {})
    assert meta.get("content_version") == EXPECTED
