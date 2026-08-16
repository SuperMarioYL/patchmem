# PatchMem — 3-line example
#
# Install once, then view a session and author a working-memory patch.
#   pip install -e .
#   patchmem view <session-id-prefix>          # render decision tree + working memory
#   patchmem edit <session-id-prefix>          # open $EDITOR, write patch.md
#
# The patch.md this generates is the input to `patchmem resume` (m2):
#   patchmem resume <session-id-prefix> --patch patch.md
#   patchmem diff  <session-id-prefix>
#
# Run the fixture-based smoke without any real session on disk:
export PATCHMEM_PROJECTS_DIR="$(dirname "$0")/../tests/fixtures"
patchmem view sample_session
