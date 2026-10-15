# Handoff

The session note for this fork. Read it first in a fresh session and rewrite
it at the end of every session (issue loop, last step). It lives in the
repository so it survives any worktree path and any tool; per-checkout agent
memory is not read by a session that starts in another worktree. State goes
here; stable recipes go into `docs/splitscreen/`; personal data and hardware
never.

Last updated 2026-10-15 (after #46; its PR waits for the session-link
cleanup below). A manual playtest is planned for 2026-10-16.

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

Then the owner opens the #46 PR and files the turbo issue (commands under
"Open pull requests"). A branch started before the rewrite (e.g. #47's) and
not pushed before `prepare` stays on the old history: rebase it onto the
rewritten co-op branch (old tips are in `rewrite/old-refs.txt`) before its
PR, and check `git log --format=%B` for the line. Old commits stay readable
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

- #46 Sentinel Beach, branch `coop/46-sentinel-beach` (docs only: TESTING.md
  test 52 and a "Campaign (#46)" row; no game change was needed). Verify
  (`--tests`, sentinel-beach, sandover-village, geyser-rock): 162/162 checks,
  compat ok, goalc-test 1692, all passed. **The PR is not open yet**: the
  owner opens it after the cleanup, with
  `gh pr create --repo Clodmony/opengoal-coop --base feature/jak1-local-splitscreen --head coop/46-sentinel-beach --title "Sentinel Beach with two players: playthrough test 52 (#46, AI-assisted)" --body-file ~/dev-scratch/jak-project/46/pr-body.md`.
  Then it needs the owner's OK to merge.

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

## Next issue: #47 Forbidden Jungle (`jungle`, `jungleb`)

Branch `coop/47-forbidden-jungle` from the co-op branch tip (after the #46
merge, or from the tip if it is still open: #46 only touches TESTING.md).
Templates: the `sentinel-beach` scenario (helpers `sb_*`: `sb_take_cell`
finds the cell nearest a spot or accepts one already taken, `sb_kill`
spin-kicks an enemy until it dies) and the shared `scout_flies(t, task,
taker)`, which picks crates by their task (neighbouring levels' crates are
loaded too). Boot a jungle continue point, list `actors`, and drive each cell
by turns: the mirrors and periscopes (#21), the fisherman (#21), the elevator
(#12), the plant boss (#18, `plant` scenario), the blue eco switch and the
river platforms, the lurker machine tower, the scout flies, orbs. Fix or
document, test 53. Known: the cell cinematic and the dark vines work.

Lessons from #44-#46 (harness): scout-fly crates break only with a ground
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
block: check the count first.

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
  Superset worktree on `coop/46-sentinel-beach` (reuse it for #47 with a new
  branch).
  The scratch worktree `~/dev-scratch/jak-project/wt-workspace` on
  `coop/workspace-handoff` (merged) can be removed. The bridge (`demo/bridge.py serve`, test
  instance 3) is still running; its game was stopped and the virtual pads
  unplugged at the end of the #46 session.
- The harness checkout has the `sentinel-beach` scenario and the shared
  `scout_flies` helper committed (5e35bc0); `wip/` is untracked there as
  before.

## Cleanup the owner may approve

- After the #46 PR and the turbo issue exist: `~/dev-scratch/jak-project/46/`
  and, once the cleanup is pushed and checked, `~/dev-scratch/jak-project/rewrite/`.
- In the tools checkout: `scratch/coop-test-mcp-before-rewrite.bundle` and
  coop-test-mcp's `refs/original` and reflog; `coop-test-mcp/wip/`; old probe
  scripts `scratch/p_*.py`, `probe.py`, `b`; `coop-test-mcp/run/verify/` (29
  runs).
- Idle coop-test MCP server processes left by other sessions (instance 0);
  harmless unless they boot.
- Merged local branches were deleted on 2026-10-14; `coop/127-near-textures`,
  `test/playtest-2` and `test/playtest-fixes` remain unmerged.
