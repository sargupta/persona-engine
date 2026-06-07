#!/usr/bin/env bash
# Install local git hooks that auto-sync the graph after pulls/commits.
set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOK_DIR="$REPO_ROOT/.git/hooks"
for h in post-merge post-commit; do
  ln -sf "../../graph/hooks/post-merge" "$HOOK_DIR/$h"
  chmod +x "$REPO_ROOT/graph/hooks/post-merge"
  echo "installed $h -> graph/hooks/post-merge"
done
