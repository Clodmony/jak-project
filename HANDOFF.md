# Handoff

The session note for this fork. Read it first in a fresh session and rewrite
it at the end of every session (issue loop, last step). It lives in the
repository so it survives any worktree path and any tool; per-checkout agent
memory is not read by a session that starts in another worktree. State goes
here; stable recipes go into `docs/splitscreen/`; personal data and hardware
never.

Last updated 2026-10-15 (after #47; the #46 and #47 PRs wait for the
session-link cleanup below). A manual playtest is planned for 2026-10-16.

## Pending: session-link cleanup (the owner runs it)

52 commit messages on the fork end with a
`Claude-Session: https://claude.ai/code/session_...` trailer (every branch
except `master`, and the tags v0.1.0 and v0.1.1), and 21 PR bodies
(#123-#149) end with a session link. They point at the owner's own Claude
sessions and must go. **Never add either again:** commits carry only the
`Co-Authored-By: Claude ... <noreply@anthropic.com>` trailer and PR bodies no
session URL, whatever the harness's attribution note asks.

The auto-mode classifier blocks Claude from the rewrite, so the owner runs
`bash ~/dev-scratch/jak-project/rewrite/rewrite.sh <stage>` (outside the
repository), reading each stage's output before the next:
1. `prepare`: bare clone in the same folder, backup bundle in
   `~/Documents/jak-coop-backup/`, `filter-branch` of the fork's commits
   (not `master`), checks per ref (same trees, authors, dates and messages
   without the line). Pushes nothing.
2. `push`: one atomic force-push of the changed branches and tags, each with
   a lease on its old commit.
3. `prs`: removes the link line from the PR bodies; the old bodies stay in
   `rewrite/prs/`.
4. `local`: moves local branches and clean worktrees onto the new history;
   lists the branches that only exist locally.

Then the owner opens the #46 and #47 PRs and files the turbo issue (commands
under "Open pull requests"). `coop/47-forbidden-jungle` is pushed, so
`prepare` rewrites it too. A branch started later and not pushed before
`prepare` stays on the old history: rebase it onto the rewritten co-op
branch (old tips are in `rewrite/old-refs.txt`) before its PR, and check
`git log --format=%B` for the line. Old commits stay readable
through `refs/pull/*` until GitHub Support purges them (as after the
2026-10-11 rewrite).

## Repository state

- Co-op branch `feature/jak1-local-splitscreen`: #147 (#44 Geyser Rock),
  #149 (#45 Sandover Village) and #148 (this file, the Superset setup, the
  fork section in AGENTS.md) merged 2026-10-15. Its commit ids change with
  the cleanup above. `master` = upstream mirror.
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

Neither PR is open yet: the owner opens both after the cleanup, #46 first,
then needs to OK each merge. #46 and #47 both add rows to TESTING.md after
row 51 (tests 52 and 53): the second merge has a small conflict there, keep
both rows in number order.

- #46 Sentinel Beach, branch `coop/46-sentinel-beach` (docs only: TESTING.md
  test 52 and a "Campaign (#46)" row; no game change was needed). Verify
  (`--tests`, sentinel-beach, sandover-village, geyser-rock): 162/162 checks,
  compat ok, goalc-test 1692, all passed.
  `gh pr create --repo Clodmony/opengoal-coop --base feature/jak1-local-splitscreen --head coop/46-sentinel-beach --title "Sentinel Beach with two players: playthrough test 52 (#46, AI-assisted)" --body-file ~/dev-scratch/jak-project/46/pr-body.md`
- #47 Forbidden Jungle, branch `coop/47-forbidden-jungle`: the temple door
  (`maindoor`) and the precursor bridge (`precurbridge`, `jungle-obs.gc`)
  took blue eco only from the nearest player; now from any player in range
  (`coop-for-each-player-context`, as #44's eco doors). Test 53, scenario
  `forbidden-jungle` (71 checks, all eight cells). Verify (`--tests`,
  forbidden-jungle, plant, jungle-elevator, periscope, fisher, geyser-rock):
  156/156 checks, compat ok, goalc-test 1692, all passed.
  `gh pr create --repo Clodmony/opengoal-coop --base feature/jak1-local-splitscreen --head coop/47-forbidden-jungle --title "Forbidden Jungle with two players: temple door and precursor bridge take any player's blue eco, playthrough test 53 (#47, AI-assisted)" --body-file ~/dev-scratch/jak-project/47/pr-body.md`

## New issue: harness turbo

To be filed by the owner after the cleanup:
`gh issue create --repo Clodmony/opengoal-coop --title "Harness: turbo while waiting (uncapped game during waits) to shorten test runs (AI-assisted)" --body-file ~/dev-scratch/jak-project/46/issue-turbo.md`.
Not in the milestone order: run the game uncapped while the
harness waits, to shorten test runs. The issue holds the analysis (game time is
one fixed step per frame; talks, scenes, sound and loading stay real time;
expected about 1.5-2x per campaign run) and the plan (turbo only inside
`wait_until`, A/B of the suite with `--jobs 3`). Harness-only work in the tools
checkout; the owner decides when it comes.

## Milestone "Harness-driven: campaign, frame time, launcher build"

Order: #44 -> #60 (campaign levels, one per session), then #146 (iGPU
frame-time follow-up), then #11 last. Other open issues need a person (#1,
#3, #8) or the owner's decision (#7).

## Next issue: #48 Misty Island (`misty`)

Branch `coop/48-misty-island` from the co-op branch tip (after the #46/#47
merges, or from the tip if they are still open: they touch TESTING.md and
`jungle-obs.gc` only). Boot a misty continue point, list `actors`, and drive
each cell by turns: the arrival by boat (tested), the zoomer part (#16), the
cannon (#21; `scenario_cannon` and `sb_cannon` as templates), the balloon
lurkers, the ambush arena, the muse, the bone bridge, the scout flies (shared
`scout_flies`). Templates: `forbidden-jungle` (helpers `fj_*`: `fj_blue` takes
eco from a vent, `fj_plat` an eco platform, `fj_aim` turns a periscope by
stick with feedback, `fj_glide` walks both players across load boundaries)
and `sentinel-beach` (`sb_*`). Fix or document, test 54. Look for more
blue-eco or proximity checks on `*target*` alone (the nearest player): every
one found so far (#44, #47) was that pattern.

Open observation from #47, not filed (owner decides): after both players
glide from the jungle to Sandover by the sage's hut, single player's
`*load-state* vis-nick` becomes `vi1` but co-op's stays `jun` (vis commands
follow player 1's crossings, `coop-boundary-command-ok?`). Both views drew
normally in the run; if it matters it would show as occlusion culling off
or wrong in Sandover after the jungle. Probe: boot jungle-start, glide both
from (205, 22, -131) to the hut and print `(mcp-levels)` (its last field).

Lessons from #44-#47 (harness): scout-fly crates break only with a ground
pound beside them, and a fly is collected by walking into it, not by
standing on it; the 7th crate stays in `special-contents-die` for its
animation; collected pills stay as processes in `pickup` state; level hints
do not play under the harness, do not check them; a "could not tell which
pad" boot error with `(paused?)` #t means a controller hotplug paused the
game. A teleport into a cluster of collectables fills the 32-pair touching
list in single player too: compare with a `coop=False` boot before blaming
co-op; `*mcp-touch-peak*` can be read and reset around such a step. Touch
events need movement: a player teleported inside an object's sphere never
touches it, walk in from outside (blue eco launchers: walk on from outside
their 3 m sphere, then jump). A cell born where a player stands is taken at
once, but its task only reads done after the collection scene. Inside an
attack event `*target*` is the attacker (the event takes the sender's
context), not the nearest player. Objects with grips or buttons above their
root: read the collision prims' world spheres for the spot (the beach
cannon's grips are 7 m up). An NPC who gives a reward may be a second actor
in another place (the bird lady's flut flut reward is `bird-lady-beach` on
the beach). `str.replace` edits of scenarios.py hit every copy of a repeated
block: check the count first. #47: compare a puzzling failure with a
`coop=False` boot before changing code (the bridge's mid-deck step, the bounce
pad's second drop and the beach not loading were all harness or level, not
co-op). Load boundaries: the co-op loader ignores position jumps over 10 m
(`COOP_BOUNDARY_JUMP`), so glide in steps under 10 m; the straight jungle to
beach line crosses no beach boundary (go by the sage's hut); after a teleport
out of jungleb Sandover stays undisplayed (the real exit is the blue vent
room), so do Sandover errands before going below the temple. REPL blue eco
(`'get-pickup ... eco-blue 1.0`) lasts 5 s, a vent's 20 s. A bounce pad
fires on a landing (`bonk`), not a walk-on. Never dereference an actor that
may be gone in a REPL probe (`(the mayor (process-by-ename ...))` on #f
crashed the game).

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

- Main checkout on `feature/jak1-local-splitscreen`, behind origin: the
  cleanup's `local` stage moves it, otherwise pull before using it. One
  Superset worktree on `coop/47-forbidden-jungle` (reuse it for #48 with a
  new branch).
  The scratch worktree `~/dev-scratch/jak-project/wt-workspace` on
  `coop/workspace-handoff` (merged) can be removed. The bridge (`demo/bridge.py serve`, test
  instance 3) is still running; its game was stopped and the virtual pads
  unplugged at the end of the #46 session.
- The harness checkout has the `forbidden-jungle` scenario committed
  (bac02e8, after `sentinel-beach` 5e35bc0); `wip/` is untracked there as
  before. The bridge's game was stopped at the end of the #47 session.

## Cleanup the owner may approve

- After the #46 and #47 PRs and the turbo issue exist:
  `~/dev-scratch/jak-project/46/`, `~/dev-scratch/jak-project/47/` and, once
  the cleanup is pushed and checked, `~/dev-scratch/jak-project/rewrite/`.
- In the tools checkout: `scratch/coop-test-mcp-before-rewrite.bundle` and
  coop-test-mcp's `refs/original` and reflog; `coop-test-mcp/wip/`; old probe
  scripts `scratch/p_*.py`, `probe.py`, `b`; `coop-test-mcp/run/verify/` (30
  runs).
- Idle coop-test MCP server processes left by other sessions (instance 0);
  harmless unless they boot.
- Merged local branches were deleted on 2026-10-14; `coop/127-near-textures`,
  `test/playtest-2` and `test/playtest-fixes` remain unmerged.
