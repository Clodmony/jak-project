# Handoff

The session note for this fork. Read it first in a fresh session and rewrite
it at the end of every session (issue loop, last step). It lives in the
repository so it survives any worktree path and any tool; per-checkout agent
memory is not read by a session that starts in another worktree. State goes
here; stable recipes go into `docs/splitscreen/`; personal data and hardware
never.

Last updated 2026-10-15 (after #45 and the merges of #147, #148, #149). A manual playtest is planned for
2026-10-16.

## Repository state

- Co-op branch `feature/jak1-local-splitscreen` at 65c531c11: #147 (#44
  Geyser Rock), #149 (#45 Sandover Village) and #148 (this file, the
  Superset setup, the fork section in AGENTS.md) merged 2026-10-15.
  `master` = upstream mirror.
- Merge only when the owner says so: locally as Claude with
  `git merge --no-ff -m "Merge pull request #N from Clodmony/<branch> (AI-assisted)"`
  and push, never `gh pr merge`. A worktree cannot check out the co-op branch
  while the main checkout holds it: merge on a detached HEAD at
  `origin/feature/jak1-local-splitscreen` and push `HEAD:feature/jak1-local-splitscreen`.
  The auto-mode classifier blocks Claude's merge into the co-op branch even
  after the owner said "merge": hand the owner the merge command to run
  with `!`.
- `gh` without `--repo Clodmony/opengoal-coop` queries upstream (wrong numbers).

## Open pull requests

None.

## Milestone "Harness-driven: campaign, frame time, launcher build"

Order: #44 -> #60 (campaign levels, one per session), then #146 (iGPU
frame-time follow-up), then #11 last. Other open issues need a person (#1,
#3, #8) or the owner's decision (#7).

## Next issue: #46 Sentinel Beach (`beach`)

Branch `coop/46-sentinel-beach` from the co-op branch tip. Template: the `sandover-village` scenario (helpers
`sv_*`: `sv_scene` tries four sides until a talk starts, `sv_talks`,
`sv_flop_at`, `sv_kick_at`, `sv_park`). Boot `village1-hut` and walk player 2
to the beach (the `sandover-village` scenario does), or a beach continue
point; list `actors`; drive each cell with both players by turns (the seagulls,
the cannon (#21), the sentinels/eco vents, the lurker puppy and the grotto,
the flut-flut egg, the pelican, the scout flies, orbs), fix or document,
test 52. Known: enemies target the closer player, both can kill them,
crates.

Lessons from #44 and #45 (harness): scout-fly crates break only with a
ground pound beside them, and a fly is collected by walking into it, not by
standing on it; the 7th crate stays in `special-contents-die` for its
animation; collected pills stay as processes in `pickup` state; level hints
do not play under the harness, do not check them; a "could not tell which
pad" boot error with `(paused?)` #t means a controller hotplug paused the
game. A teleport into a cluster of collectables (the orb cache's falling
column) fills the 32-pair touching list in single player too: compare with
a `coop=False` boot before blaming co-op; `*mcp-touch-peak*` can be read
and reset around such a step. `*target* fact buzzer` (player 1's own fly
count) only decides when to pre-load the 7th fly's animation, nothing else.

## Verify and build

- The verify script and the in-game harness (coop-test MCP server, bridge,
  scenarios) live outside the repository in the owner's
  `~/Documents/jak-coop-tools/coop-test-mcp` checkout:
  `demo/verify.sh [--tests] [--suite] <worktree> [scenario ...]`, run in the
  background with the bridge up; read only `run/verify/<stamp>/summary.txt`.
- Playtest packages: dynamic Linux build in the tools checkout's
  `scratch/build-gk`, then `scripts/coop-mod/package_mod.py --bin-dir <that>
  --allow-dynamic --out-dir <tools>/builds`. The current package
  `builds/jak1-coop.tar.gz` is still 9ffe106a3 (without #142, #144, #147, #149):
  rebuild it from the co-op branch tip for the playtest. `scratch/build-gk`
  must stay while the launcher's mod points at it.

## Worktrees and background processes

- Main checkout on `feature/jak1-local-splitscreen`, behind origin (at
  c461511c1): pull before using it. One Superset worktree on
  `coop/45-sandover-village` (merged; reuse it for #46 with a new branch).
  The scratch worktree `~/dev-scratch/jak-project/wt-workspace` on
  `coop/workspace-handoff` (merged) can be removed. The bridge (`demo/bridge.py serve`, test
  instance 3) is still running; its game was stopped and the virtual pads
  unplugged at the end of the #45 session.
- The harness checkout has the `sandover-village` scenario committed
  (34c4fc0); `wip/` is untracked there as before.

## Cleanup the owner may approve

- In the tools checkout: `scratch/coop-test-mcp-before-rewrite.bundle` and
  coop-test-mcp's `refs/original` and reflog; `coop-test-mcp/wip/`; old probe
  scripts `scratch/p_*.py`, `probe.py`, `b`; `coop-test-mcp/run/verify/` (29
  runs).
- Idle coop-test MCP server processes left by other sessions (instance 0);
  harmless unless they boot.
- Merged local branches were deleted on 2026-10-14; `coop/127-near-textures`,
  `test/playtest-2` and `test/playtest-fixes` remain unmerged.
