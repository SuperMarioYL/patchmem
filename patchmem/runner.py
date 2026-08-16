"""Resume/replay runner — m2 stub.

Per the mvp_plan §5 m2 spec:

    Done = ``patchmem resume <session> --patch patch.md`` applies the patch
    to a transcript copy, spawns a resumed run for the patched arm AND an
    unpatched control arm through the configured runtime adapter
    (``config.py``), and saves both resulting transcript suffixes to
    ``~/.patchmem/runs/<session>/``.

The runner is a pluggable adapter behind ``config.py`` so the exact resume
command is configurable, not hardcoded.

v0.1 ships the SHAPE of the runner (the adapter selection, the runs-dir
layout, the two-arm contract) but ``run_resume`` raises ``RunnerStub`` so
the m1 build is honest: resume is m2 scope. The CLI ``resume`` command
calls this and surfaces the message to the operator.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .models import Patch


class RunnerStub(RuntimeError):
    """Raised by run_resume in v0.1 — resume lands in m2."""


@dataclass
class ResumeArm:
    """One replayed arm (patched or control)."""

    name: str
    transcript_path: Path
    suffix_lines: list[str]


@dataclass
class ResumeResult:
    """Two-arm replay-ablation output for ``patchmem diff`` (m3)."""

    session_id: str
    control: ResumeArm
    patched: ResumeArm
    runs_dir: Path


def _runs_dir_for(cfg: Config, session_id: str) -> Path:
    d = cfg.runs_dir / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def run_resume(
    session_path: Path,
    session_id: str,
    patch: Patch,
    cfg: Config | None = None,
    patch_path: Path | None = None,
) -> ResumeResult:  # pragma: no cover - m2 scope
    """Spawn the patched + control arms via the configured runtime adapter.

    v0.1: NOT implemented — raises ``RunnerStub``. m2 fills the spawn:
    apply the patch to a transcript copy, run the runtime's resume for both
    arms through ``cfg.adapter()``, capture each arm's transcript suffix,
    write to ``<runs_dir>/{control,patched}.jsonl``.

    The hosted stub (``--hosted``) points at the v0.3 managed replay-farm
    that returns the same two arms in seconds instead of a local re-run.
    """
    raise RunnerStub(
        "patchmem resume lands in milestone m2. v0.1 ships the adapter "
        "shape (config.py) + the influence-diff primitive (influence_diff.py) "
        "so the only missing piece is the runtime spawn. Track m2 on the "
        "roadmap."
    )
