#!/usr/bin/env bash
# Bring the local co-op branch up to date with upstream OpenGOAL and check that it still builds,
# passes the tests and stays a clean add-on. Written with AI assistance (AI-assisted).
#
#   scripts/splitscreen/sync_upstream.sh            merge upstream/master, build, test, check
#   scripts/splitscreen/sync_upstream.sh --preview  only list the files that would conflict
#
# Expects a configured build folder (cmake -B build --preset=Release-linux-clang).

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

UPSTREAM_URL="https://github.com/open-goal/jak-project.git"
git remote get-url upstream >/dev/null 2>&1 || git remote add upstream "$UPSTREAM_URL"
git fetch --quiet upstream master

behind=$(git rev-list --count HEAD..upstream/master)
echo "upstream/master is $behind commit(s) ahead of this branch"

if [ "${1:-}" = "--preview" ]; then
  if git merge-tree --write-tree --name-only HEAD upstream/master >/tmp/coop-merge-preview.txt; then
    echo "merges without conflicts"
  else
    echo "conflicts in:"
    tail -n +2 /tmp/coop-merge-preview.txt | sed -n '/^$/q;p'
  fi
  exit 0
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "commit or stash your changes first" >&2
  exit 1
fi

if [ "$behind" -gt 0 ]; then
  git merge --no-edit upstream/master
fi

cmake --build build --parallel "$(nproc)"
# all Jak 1 code; Jak 2/3/X compile and type checks are part of test.sh
./build/goalc/goalc --game jak1 --cmd '(make-group "all-code")'
./test.sh
python3 scripts/splitscreen/check_upstream_compat.py
echo "done: the branch is on upstream/master and passes. Push it, then rebuild the game ((mi)) to play."
