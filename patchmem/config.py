"""Pluggable runtime adapter config — the resume command is configurable.

Per the m2 spec, the runner that spawns the patched + control arms is a
pluggable adapter behind ``config.py`` so the exact resume command is
configurable, not hardcoded. v0.1 ships a default Claude Code adapter
declared here but not executed (resume is m2); the config surface is real so
m2 only fills in the spawn, not the shape.

Resolution order (first non-empty wins):
    1. ``$PATCHMEM_RUNTIME`` env var (``claude`` | ``claude-code``).
    2. ``runtime`` key in ``~/.patchmem/config.toml``.
    3. default ``claude-code``.

The adapter is selected by name; each adapter contributes a ``resume_argv``
template PatchMem interpolates the session id + resume-point into. v0.1 does
not invoke it — ``runner.run_resume`` is the m2 stub.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib  # stdlib in 3.11+
else:  # pragma: no cover - py3.12+ is the supported floor
    import tomli as tomllib  # type: ignore[no-redef]

PATCHMEM_HOME = Path.home() / ".patchmem"
CONFIG_PATH = PATCHMEM_HOME / "config.toml"

DEFAULT_RUNTIME = "claude-code"


@dataclass
class RuntimeAdapter:
    """A declarative runtime adapter — v0.1 ships the shape, m2 fills spawn."""

    name: str
    resume_cmd: list[str]
    resume_session_flag: str = "--resume"
    resume_continue_flag: str | None = "--continue"
    print_flag: str | None = "-p"
    extra_env: dict[str, str] = field(default_factory=dict)


# Declarative registry of known adapters. m2's runner selects by name and
# builds the resume argv from this template — never hardcoded per-session.
_ADAPTERS: dict[str, RuntimeAdapter] = {
    "claude-code": RuntimeAdapter(
        name="claude-code",
        resume_cmd=["claude"],
        resume_session_flag="--resume",
        resume_continue_flag="--continue",
        print_flag="-p",
    ),
    "claude": RuntimeAdapter(
        name="claude",
        resume_cmd=["claude"],
        resume_session_flag="--resume",
        resume_continue_flag="--continue",
        print_flag="-p",
    ),
    # Stub for post-v0.1 runtimes — herdr / waku land in v0.2+.
    "herdr": RuntimeAdapter(
        name="herdr",
        resume_cmd=["herdr"],
        resume_session_flag="resume",
        resume_continue_flag=None,
        print_flag=None,
    ),
}


@dataclass
class Config:
    runtime: str = DEFAULT_RUNTIME
    projects_dir: Path = field(
        default_factory=lambda: Path.home() / ".claude" / "projects"
    )
    runs_dir: Path = field(default_factory=lambda: PATCHMEM_HOME / "runs")
    hosted: bool = False

    def adapter(self) -> RuntimeAdapter:
        if self.runtime not in _ADAPTERS:
            raise ValueError(
                f"unknown runtime '{self.runtime}'. "
                f"known: {sorted(_ADAPTERS)}"
            )
        return _ADAPTERS[self.runtime]


def load_config(path: Path | None = None) -> Config:
    """Load config from env > toml > defaults (first non-empty wins)."""
    runtime = os.environ.get("PATCHMEM_RUNTIME", "").strip()
    projects_dir_env = os.environ.get("PATCHMEM_PROJECTS_DIR", "").strip()
    runs_dir_env = os.environ.get("PATCHMEM_RUNS_DIR", "").strip()
    hosted_env = os.environ.get("PATCHMEM_HOSTED", "").strip().lower()

    cfg_path = Path(path) if path else CONFIG_PATH
    toml: dict = {}
    if cfg_path.exists():
        with cfg_path.open("rb") as fh:
            toml = tomllib.load(fh)

    runtime = runtime or str(toml.get("runtime", DEFAULT_RUNTIME))
    projects_dir = Path(projects_dir_env) if projects_dir_env else Path(
        toml.get("projects_dir", str(Path.home() / ".claude" / "projects"))
    )
    runs_dir = Path(runs_dir_env) if runs_dir_env else Path(
        toml.get("runs_dir", str(PATCHMEM_HOME / "runs"))
    )
    hosted = (
        hosted_env in ("1", "true", "yes")
        if hosted_env
        else bool(toml.get("hosted", False))
    )

    return Config(
        runtime=runtime,
        projects_dir=projects_dir,
        runs_dir=runs_dir,
        hosted=hosted,
    )
