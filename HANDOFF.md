# Handoff

The session note for this fork. Read it first in a fresh session and rewrite
it at the end of every session (issue loop, last step). It lives in the
repository so it survives any worktree path and any tool; per-checkout agent
memory is not read by a session that starts in another worktree. State goes
here; stable recipes go into `docs/splitscreen/`; personal data and hardware
never.

Last updated 2026-10-14 (after #44 and the workspace pull request). A manual
playtest is planned for 2026-10-16.

## Repository state

- Co-op branch `feature/jak1-local-splitscreen` at 0034a8cfa (PR #145 / #6
  merged 2026-10-14). `master` = upstream mirror.
- Merge only when the owner says so: locally as Claude with
  `git merge --no-ff -m "Merge pull request #N from Clodmony/<branch> (AI-assisted)"`
  and push, never `gh pr merge`. A worktree cannot check out the co-op branch
  while the main checkout holds it: merge on a detached HEAD at
  `origin/feature/jak1-local-splitscreen` and push `HEAD:feature/jak1-local-splitscreen`.
- `gh` without `--repo Clodmony/opengoal-coop` queries upstream (wrong numbers).

## Open pull requests

- **#147** `coop/44-geyser-rock` @ 50f73b33d, Closes #44, not merged: ask the
  owner. Runtime change: `eco-door` door-closed (`baseplat.gc`) checks every
  player in range for blue eco (`coop-for-each-player-context`); before, only
  the nearest player counted, so player 1 without eco standing closer kept
  the Geyser Rock iris door shut for player 2 with eco. TESTING.md test 50 and
  the "Campaign (#44)" scripted row, an ARCHITECTURE.md bullet. Verify:
  compile ok, 61/61 scenarios (geyser-rock 40, warp, pov-cameras,
  cell-same-frame), compat ok, goalc-test 1692. Media 102/103.
- The workspace pull request (`coop/workspace-handoff`): this file,
  `.superset/`, `CLAUDE.md`, the fork section in AGENTS.md.

## Milestone "Harness-driven: campaign, frame time, launcher build"

Order: #44 -> #60 (campaign levels, one per session), then #146 (iGPU
frame-time follow-up), then #11 last. Other open issues need a person (#1,
#3, #8) or the owner's decision (#7).

## Next issue: #45 Sandover Village (`village1`)

A branch `coop/45-sandover-village` exists in the Superset worktree at the
co-op branch's tip (no commits yet). Follow the `geyser-rock` scenario as the
template (`scenarios.py`, helpers `gr_*`, `chamber_flop` for ground pounds,
`actor_state`, `gr_find`): boot `village1-warp` or `village1-hut`, list
`actors`, drive each piece with both players by turns (NPC talks: sage,
farmer and yakows, explorer, the fisherman's boat to Misty is #48, oracle,
Mayor and uncle, the bird lady, warp gate, orbs, scout flies with ground
pounds), fix or document, test 51. Known from earlier issues: NPC talks with
either player, the boat, swimming, orbs, save and load are tested; Sandover's
farmer hint holds both players about 13 s (teleports during it keep them
held).

Lessons from #44 (harness): steel scout-fly crates break only with a ground
pound beside them; the 7th crate stays in `special-contents-die` for its
animation; collected pills stay as processes in `pickup` state; level hints
(`level-hint-spawn`) do not play under the harness even in single player, so
do not check them; a "could not tell which pad" boot error with `(paused?)`
#t means a controller hotplug paused the game.

## Verify and build

- The verify script and the in-game harness (coop-test MCP server, bridge,
  scenarios) live outside the repository in the owner's
  `~/Documents/jak-coop-tools/coop-test-mcp` checkout:
  `demo/verify.sh [--tests] [--suite] <worktree> [scenario ...]`, run in the
  background with the bridge up; read only `run/verify/<stamp>/summary.txt`.
- Playtest packages: dynamic Linux build in the tools checkout's
  `scratch/build-gk`, then `scripts/coop-mod/package_mod.py --bin-dir <that>
  --allow-dynamic --out-dir <tools>/builds`. The current package
  `builds/jak1-coop.tar.gz` is still 9ffe106a3 (without #142, #144, #147):
  rebuild it from the co-op branch tip for the playtest. `scratch/build-gk`
  must stay while the launcher's mod points at it.

## Worktrees and background processes

- Main checkout on `feature/jak1-local-splitscreen`, clean. One Superset
  worktree on `coop/45-sandover-village`. One scratch worktree on
  `coop/workspace-handoff`. The bridge (`demo/bridge.py serve`, test instance
  3) may still be running from the #44 session; its game was stopped and the
  virtual pads unplugged.

## Cleanup the owner may approve

- In the tools checkout: `scratch/coop-test-mcp-before-rewrite.bundle` and
  coop-test-mcp's `refs/original` and reflog; `coop-test-mcp/wip/`; old probe
  scripts `scratch/p_*.py`, `probe.py`, `b`; `coop-test-mcp/run/verify/` (29
  runs).
- Idle coop-test MCP server processes left by other sessions (instance 0);
  harmless unless they boot.
- Merged local branches were deleted on 2026-10-14; `coop/127-near-textures`,
  `test/playtest-2` and `test/playtest-fixes` remain unmerged.
