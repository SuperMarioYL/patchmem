Output assets/demo.gif
Set FontSize 13
Set Width 980
Set Height 600
Set Padding 12
Set Theme Dracula
Set CursorBlink false
Set Framerate 12

# PatchMem 10-minute happy path: view -> edit -> diff
# Expects `pip install -e .` already done (CI does it; locally run it first).

Type "patchmem --version"
Enter
Sleep 500ms

Type "export PATCHMEM_PROJECTS_DIR=$(pwd)/tests/fixtures"
Enter
Sleep 500ms

# 1. view: render the decision tree + working memory for the fixture session.
Type "patchmem view sample_session"
Enter
Sleep 2s

# 2. author a patch.md by hand (non-interactive), then show it.
Type "cat > demo-patch.md <<'EOF'"
Enter
Type "anchor_uuid: msg-0006"
Enter
Type "rationale: force HS256 not HS384"
Enter
Type "block_type: text"
Enter
Type "---"
Enter
Type "plan: auth check MUST verify HS256 and reject HS384 before issuing a session"
Enter
Type "EOF"
Enter
Sleep 500ms
Type "cat demo-patch.md"
Enter
Sleep 1s

# 3. resume (m2 stub) + diff — surface the m1 scope honestly.
Type "patchmem resume sample_session --patch demo-patch.md"
Enter
Sleep 1s
Type "patchmem diff sample_session"
Enter
Sleep 1s

