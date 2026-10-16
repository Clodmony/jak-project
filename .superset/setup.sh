#!/usr/bin/env bash
# Makes a fresh worktree of this fork ready for an agent session. Superset runs
# it on workspace creation (.superset/config.json); run it by hand in any other
# worktree. Idempotent, a few seconds, touches only this checkout's git config,
# the scratch folder and the gitignored test files: the binaries and game data
# the in-game tests need, copied (reflinks) from the tip build and checkout
# named in HANDOFF.md. It does not build: a full build takes long and the
# verify script compiles the GOAL code. Never changes the owner's global git
# identity.
set -uo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

git config user.name Claude
git config user.email noreply@anthropic.com
if ! git remote get-url upstream >/dev/null 2>&1; then
	git remote add upstream https://github.com/open-goal/jak-project.git
fi
git remote set-url --push upstream DISABLED

mkdir -p "$HOME/dev-scratch/jak-project"

for t in cmake ninja clang python3; do
	command -v "$t" >/dev/null || echo "setup: $t missing (build)" >&2
done
command -v task >/dev/null || command -v go-task >/dev/null || echo "setup: no task/go-task (Taskfile.yml commands)" >&2
tools="$HOME/Documents/jak-coop-tools/coop-test-mcp"
[[ -x "$tools/demo/verify.sh" ]] || echo "setup: verify script not found at $tools/demo/verify.sh (see HANDOFF.md)" >&2
if [[ -x "$tools/demo/worktree-setup.sh" ]]; then
	"$tools/demo/worktree-setup.sh" "$root" >/dev/null ||
		echo "setup: no test binaries or game data copied (see HANDOFF.md, a stream's first steps)" >&2
fi

echo "setup: $(git config user.name) <$(git config user.email)>, branch $(git branch --show-current)"
echo "setup: read HANDOFF.md first, then the fork section of AGENTS.md"
