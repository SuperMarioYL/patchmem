"""patchmem CLI — the operator surface.

Commands:
    view <session>     m1 — render the decision tree + working memory.
    edit <session>     m1 — open $EDITOR, author a patch, write patch.md.
    resume <session>   m2 — spawn patched + control arms (STUB in v0.1).
    diff <session>     m3 — print the before/after influence tree.

v0.1 fully implements ``view`` and ``edit``. ``resume`` is a clear m2 stub.
``diff`` runs the real ``influence_diff`` primitive when m2's two-arm
replay output exists under ``~/.patchmem/runs/<session>/``; otherwise it
explains m2 must run first. The hosted stub (``--hosted``) points at the
v0.3 managed replay-farm.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console

from . import __version__
from .config import load_config
from .patch import PatchError, author_patch, read_patch_md, write_patch_md
from .transcript import TranscriptError, find_session, parse_session
from .wm_view import view_session

app = typer.Typer(
    name="patchmem",
    help="Patch-as-commit-to-working-memory primitive for coding-agent runs.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
err_console = Console(stderr=True)


def _resolve(session_ref: str):
    cfg = load_config()
    path = find_session(session_ref, cfg.projects_dir)
    messages = parse_session(path)
    return cfg, path, messages


def _session_id_from_path(path: Path) -> str:
    return path.stem


@app.command()
def view(session: str = typer.Argument(..., help="Session id / prefix / path.")) -> None:
    """m1 — render the parentUuid-linked decision tree + working memory."""
    try:
        _cfg, path, messages = _resolve(session)
    except (TranscriptError, FileNotFoundError) as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1)
    if not messages:
        err_console.print("[yellow]no user/assistant messages in session.[/yellow]")
        raise typer.Exit(code=1)
    console.print(
        f"[dim]patchmem v{__version__}[/dim]  session: [bold]{_session_id_from_path(path)}[/bold]"
    )
    view_session(messages, console)


@app.command()
def edit(
    session: str = typer.Argument(..., help="Session id / prefix / path."),
    anchor: str = typer.Option(
        None, "--anchor", "-a", help="Suggested anchor uuid for the insertion."
    ),
    out: Path = typer.Option(
        Path("patch.md"), "--out", "-o", help="Where to write the patch file."
    ),
) -> None:
    """m1 — open $EDITOR, author a working-memory patch, write patch.md."""
    try:
        _cfg, path, messages = _resolve(session)
    except (TranscriptError, FileNotFoundError) as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1)
    if not messages:
        err_console.print("[yellow]no messages to anchor against.[/yellow]")
        raise typer.Exit(code=1)
    try:
        patch = author_patch(messages, anchor_hint=anchor)
    except PatchError as exc:
        err_console.print(f"[red]patch rejected:[/red] {exc}")
        raise typer.Exit(code=1)
    out = write_patch_md(patch, out)
    console.print(
        f"[green]patch written:[/green] {out}\n"
        f"  [dim]anchor_uuid:[/dim] {patch.anchor_uuid}\n"
        f"  [dim]rationale:[/dim] {patch.rationale!r}\n"
        f"  [dim]block:[/dim] {patch.block.text[:60]!r}{'…' if len(patch.block.text) > 60 else ''}"
    )
    console.print(
        "[dim]next:[/dim] patchmem resume "
        f"{_session_id_from_path(path)} --patch {out}  [italic](m2 — stub in v0.1)[/italic]"
    )


@app.command()
def resume(
    session: str = typer.Argument(..., help="Session id / prefix / path."),
    patch: Path = typer.Option(..., "--patch", "-p", help="Patch file from `patchmem edit`."),
    hosted: bool = typer.Option(
        False, "--hosted", help="Use the managed replay-farm (v0.3 stub)."
    ),
) -> None:
    """m2 — spawn patched + control arms via the runtime adapter (STUB in v0.1)."""
    # Local import keeps the m2 surface isolated in v0.1.
    from .runner import RunnerStub, run_resume

    try:
        cfg, path, messages = _resolve(session)
    except (TranscriptError, FileNotFoundError) as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1)
    try:
        patch_obj = read_patch_md(patch)
    except PatchError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1)
    if hosted:
        console.print(
            "[magenta]--hosted[/magenta]: the managed replay-farm lands in the v0.3 "
            "paid tier — it runs the patched + control ablation in parallel on "
            "PatchMem infra and returns the diff in seconds. The local "
            "command surface is identical. [italic]stub in v0.1.[/italic]"
        )
    try:
        run_resume(path, _session_id_from_path(path), patch_obj, cfg, patch)
    except RunnerStub as exc:
        console.print(f"[yellow]m2 stub:[/yellow] {exc}")
        raise typer.Exit(code=0)


@app.command()
def diff(
    session: str = typer.Argument(..., help="Session id / prefix / path."),
    hosted: bool = typer.Option(False, "--hosted", help="v0.3 managed replay-farm stub."),
) -> None:
    """m3 — print the before/after influence tree.

    In v0.1, runs the real ``influence_diff`` primitive if m2's two-arm
    replay output exists under ``~/.patchmem/runs/<session>/``. Otherwise
    explains m2 must run first. The diff algorithm itself is implemented
    (it is the owned primitive) — only the replay that feeds it is m2.
    """
    from .influence_diff import compute_diff
    from .render_diff import render_diff
    from .models import Patch, TextBlock, ToolUse

    try:
        cfg, path, messages = _resolve(session)
    except (TranscriptError, FileNotFoundError) as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1)
    sid = _session_id_from_path(path)
    control_path = cfg.runs_dir / sid / "control.jsonl"
    patched_path = cfg.runs_dir / sid / "patched.jsonl"
    patch_meta_path = cfg.runs_dir / sid / "patch.md"

    if hosted:
        console.print(
            "[magenta]--hosted[/magenta]: managed replay-farm diff (v0.3 paid tier). "
            "Same primitive, compute off your laptop. [italic]stub in v0.1.[/italic]"
        )
        raise typer.Exit(code=0)

    if not (control_path.exists() and patched_path.exists()):
        console.print(
            f"[yellow]m2 not yet run[/yellow] — no replayed arms at\n"
            f"  {control_path}\n  {patched_path}\n"
            f"run [bold]patchmem resume {sid} --patch patch.md[/bold] first "
            "(m2 — stub in v0.1).\n\n"
            "[dim]the influence-diff primitive itself is implemented "
            "(influence_diff.py); it needs two replayed transcripts.[/dim]"
        )
        raise typer.Exit(code=0)

    def _decisions(p: Path) -> list[ToolUse]:
        out: list[ToolUse] = []
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") != "assistant":
                continue
            msg = obj.get("message")
            if not isinstance(msg, dict):
                continue
            for b in msg.get("content", []) or []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    out.append(
                        ToolUse(
                            id=b.get("id", ""),
                            name=b.get("name", ""),
                            input=b.get("input", {}) or {},
                        )
                    )
        return out

    patch_obj = (
        read_patch_md(patch_meta_path) if patch_meta_path.exists() else Patch(
            anchor_uuid="", block=TextBlock(text=""),
            rationale="(patch metadata unavailable)",
        )
    )
    influence = compute_diff(
        patch_obj, _decisions(control_path), _decisions(patched_path)
    )
    render_diff(influence, console)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-V", help="Show patchmem version and exit."
    ),
) -> None:
    """patchmem — patch-as-commit-to-working-memory primitive."""
    if version:
        console.print(f"patchmem {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        console.print("patchmem — patch working memory mid-run, see the decision diff.")
        console.print("Run [bold]patchmem --help[/bold] for commands.")
        raise typer.Exit()


if __name__ == "__main__":  # pragma: no cover
    app()
