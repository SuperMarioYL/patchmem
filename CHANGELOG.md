# Changelog

All notable changes to PatchMem are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to semantic versioning.

## [0.2.0] - 2026-09-11

### Fixed

- `patchmem edit` no longer crashes with a raw traceback when `$EDITOR` /
  `$VISUAL` carries flags (`code --wait`, `vim -f`, …). The editor command is
  now split with `shlex.split`, and an unlaunchable or failing editor reports
  a clean one-line error instead of a `FileNotFoundError` traceback
  (`patchmem/patch.py`).
- `patchmem edit` no longer silently strips `#`-prefixed lines from the
  operator-authored patch body — markdown headings in working-memory patches
  round-trip verbatim, matching the on-disk `patch.md` format
  (`patchmem/patch.py`).
- A transcript line that is valid JSON but not an object now raises a clean
  `TranscriptError` carrying `file:lineno` in every command, instead of an
  `AttributeError` traceback (`patchmem/transcript.py`).
- Altered decisions in `patchmem diff` now render the changed input keys and
  their before/after values; previously an altered decision whose changed key
  was neither `command` nor `path` rendered identical before/after previews
  that hid the change (`patchmem/influence_diff.py`, `patchmem/render_diff.py`).

### Changed

- Version lockstep: `VERSION`, `pyproject.toml`, `patchmem.__version__`, the
  CLI `--version` output, and `web/site.json` `meta.content_version` all
  report 0.2.0, guarded by a new version-consistency test
  (`tests/test_version_lockstep.py`).

## [0.1.0] - 2026-08-16

Initial release.

- `patchmem view` — parentUuid-linked decision tree + working-memory blocks in
  a rich TUI.
- `patchmem edit` — `$EDITOR` patch authoring with anchor verification,
  writes `patch.md`.
- `patchmem diff` — structural patch-influence-diff over two replayed arms
  (`compute_diff`), the owned replay-ablation primitive; gate-3 honesty
  (structural diff only, never model attribution) guarded by tests.
- `patchmem resume` — m2 stub: the runtime adapter shape ships via
  `config.py`; the two-arm replay spawn is on the roadmap.

## [0.3.0] - 2026-10-16

### Fixed

- A malformed or mistyped `~/.patchmem/config.toml` no longer crashes every
  `patchmem` command with a raw `TOMLDecodeError`/`TypeError` traceback — a
  non-parsable file or a non-string `runtime` / `projects_dir` / `runs_dir`
  value now reports a clean one-line `error:` naming the file and cause
  (`patchmem/config.py`, `patchmem/cli.py`).
- `patchmem diff` no longer crashes with an `AttributeError` traceback when a
  replayed arm JSONL contains a line that is valid JSON but not an object —
  corrupt lines are skipped and the diff is computed from the decisions that
  parsed, matching the arm parser's existing corrupt-line contract
  (`patchmem/cli.py`, `patchmem/influence_diff.py`).
- `patchmem diff` no longer crashes with a raw `PatchError` traceback when the
  runs-dir patch metadata file (`runs/<session>/patch.md`) is malformed — it
  warns on stderr and renders the diff without the display-only header
  (`patchmem/cli.py`).
- A transcript containing invalid UTF-8 bytes now raises a clean
  `TranscriptError` carrying the file path instead of a raw
  `UnicodeDecodeError` traceback through every command
  (`patchmem/transcript.py`).

### Changed

- Version lockstep: `VERSION`, `pyproject.toml`, `patchmem.__version__`, the
  CLI `--version` output, and `web/site.json` `meta.content_version` all
  report 0.3.0 (`tests/test_version_lockstep.py`).

[0.3.0]: https://github.com/SuperMarioYL/patchmem/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/SuperMarioYL/patchmem/compare/v0.1.0...v0.2.0
