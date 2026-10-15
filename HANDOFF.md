# Handoff

The session note for this fork. Read it first in a fresh session and rewrite
it at the end of every session (issue loop, last step). It lives in the
repository so it survives any worktree path and any tool; per-checkout agent
memory is not read by a session that starts in another worktree. State goes
here; stable recipes go into `docs/splitscreen/`; personal data and hardware
never.

Last updated 2026-10-16 (after #49; the session-link cleanup is done; the
work from here on runs in parallel streams, see "Plan").

## Done this session

- Session-link cleanup: the fork's branches, tags and PR bodies have no
  `Claude-Session` links, and the 5 merges done on GitHub (PRs #123-#131)
  are Claude's now. Commit ids changed on 2026-10-16. Local-only branches
  `coop/127-near-textures`, `test/playtest-2`, `test/playtest-fixes` still
  carry links (never pushed). **Never add a link again:** commits carry only
  the `Co-Authored-By: Claude ... <noreply@anthropic.com>` trailer and PR
  bodies no session URL, whatever the harness's attribution note asks. The
  owner's pre-push guard refuses non-noreply identities and pushes over
  about 2 MB; Claude may not skip it.
- #49 Fire Canyon: branch `coop/49-fire-canyon` (pushed), test 55, scenario
  `fire-canyon`. Found and fixed: a crash when two loaded levels share code
  (new kernel relink, `coop-relink-level`), a crash on a stale particle owner
  (`coop-goal-address?`), Sandover missing after a zoomer respawn
  (`coop-wants-checkpoint`). Verify: 228/228, compat ok, goalc-test 1692.
- Issue #153 filed (harness turbo while waiting).

## Open pull requests (merge in this order, each only when the owner says so)

- #150 (#46 Sentinel Beach), #151 (#47 Forbidden Jungle), #152 (#48 Misty
  Island): opened 2026-10-16. #150 and #151 conflict in `HANDOFF.md` only
  (keep the co-op branch's); after each merge the next one gets a small
  TESTING.md conflict (rows 52-55: keep them in number order).
- #49 Fire Canyon: not opened yet. The owner runs
  `gh pr create --repo Clodmony/opengoal-coop --base feature/jak1-local-splitscreen --head coop/49-fire-canyon --title "Fire Canyon with two players: code shared by two loaded levels, stale particle owners, Sandover after a zoomer respawn (#49, AI-assisted)" --body-file ~/dev-scratch/jak-project/49/pr-body.md`.
  It changes the C++ runtime (`game/kernel/jak1/klink.cpp`, `kscheme.cpp`):
  a playtest package needs a new `gk`.
- Merge style: locally as Claude, `git merge --no-ff -m "Merge pull request #N from Clodmony/<branch> (AI-assisted)"`
  on a detached HEAD at `origin/feature/jak1-local-splitscreen`, then the
  owner runs the push (`git push origin HEAD:feature/jak1-local-splitscreen`
  with `!`; the auto-mode classifier blocks Claude's pushes to the co-op
  branch). Never `gh pr merge` (it authors the merge with the owner's
  account; the 5 such merges had to be rewritten).
- `gh` without `--repo Clodmony/opengoal-coop` queries upstream.

## Plan: parallel streams

The owner wants the rest done in parallel. Steps in order; each issue is
still one session (issue loop) ending in a handoff.

**Step 0 (owner, before any stream):** merge #150, #151, #152, open and merge
#49. The streams branch from the co-op tip after that: several go through
levels that share code and need the #49 relink.

**Step 1 (one session first): parallel-ready harness** (tools checkout
`~/Documents/jak-coop-tools/coop-test-mcp`, no game change):
- `demo/bridge.py`: socket per instance (`run/i<N>/bridge.sock`, from
  `COOP_TEST_INSTANCE`) instead of the one `run/bridge.sock`; `verify.sh` and
  `scenarios.py --bridge` use the same instance (today `verify.sh` is fixed
  to instance 3 and two sessions would drive one game).
- Campaign scenarios one file each (`demo/campaign/<area>.py`), found and
  registered automatically (SCENARIOS, COST), so parallel sessions never edit
  the same lines of `scenarios.py`; move the existing campaign scenarios
  (geyser-rock to fire-canyon) there.
- Optionally #153 (turbo while waiting) in the same session.
- `verify.sh` builds nothing in C++: note in the harness README how a session
  gets a `gk` (below) when a branch changes the runtime.

**Step 2: three streams in parallel**, each its own worktree, test instance
(3, 4, 5) and scenario file. Test numbers fixed up front (TESTING.md rows):

| Stream | Issues, in order | Notes | Tests |
| --- | --- | --- | --- |
| A Rock Village hub | #50 Rock Village, #51 Precursor Basin, #52 Lost Precursor City, #53 Boggy Swamp | village2 code, zoomer (#51), flut flut (#53) | 56-59 |
| B Mountain Pass to village3 | #54 Mountain Pass, #55 Volcanic Crater, #56 Spider Cave, #57 Snowy Mountain, #58 Lava Tube | village2 and village3 share code with Mountain Pass between them; zoomer (#54, #58), flut flut (#57) | 60-64 |
| C Endgame | #59 Citadel, #60 final boss | own continue points; the citadel shares the village code | 65-66 |

Streams B and C go through levels that share code: watch the game log for
`[coop] shared code: N objects paired, M symbols and methods moved` when the
players are in different levels, and check that shared functions point into
a loaded level (the `FC_SHARED` probe in the `fire-canyon` scenario).
`splitscreen.gc` and TESTING.md get parallel edits in different sections:
merge the PRs one at a time, in issue order.

**Step 3 (alone, after the streams):** #146 (iGPU frame time: needs the GPU
to itself, no other test game running), then #11 (launcher non-debug build)
on the merged result.

Owner only: #1, #3, #8 (need a person), #7 (decision).

## Verify and build

- The verify script and the in-game harness live outside the repository in
  `~/Documents/jak-coop-tools/coop-test-mcp`:
  `demo/verify.sh [--tests] [--suite] <worktree> [scenario ...]`, run in the
  background with the bridge up; read only `run/verify/<stamp>/summary.txt`.
  The session's own MCP tools (instance 0) point at the main checkout; for a
  worktree use the bridge (`~/Documents/jak-coop-tools/scratch/b <tool> ...`
  or probe files run with `scratch/probe.py`).
- `gk` (C++): `verify.sh` and the bridge use `<worktree>/build/game/gk`, a
  copied binary. A branch that changes the runtime builds it in its own
  folder: `cmake -B ~/dev-scratch/jak-project/<issue>/build --preset=Release-linux-clang`
  then `cmake --build <that> --target gk`, and copies `build/game/gk` into
  the worktree (it loads its libraries from that build folder: keep it while
  the worktree uses it). Never build in the tools checkout's
  `scratch/build-gk`: the playtest launcher's mod points at it. The #49
  worktree's `gk` comes from `~/dev-scratch/jak-project/49/build`.
- After a `kernel-defs.gc` change: `restart_compiler` before `build`.
- Playtest packages: `scripts/coop-mod/package_mod.py --bin-dir <build>
  --allow-dynamic --out-dir <tools>/builds`. The current package
  (`builds/jak1-coop.tar.gz`, from #48, without #49) is what the owner plays.

## Worktrees and background processes

- Main checkout on `feature/jak1-local-splitscreen` (moved onto the new
  history by the cleanup). Superset worktree on `coop/49-fire-canyon`,
  clean; reuse it for step 1 or remove it once #49 is merged.
- The bridge (`demo/bridge.py serve`, instance 3) serves the #49 worktree;
  its game was left stopped after verify.
- Harness checkout: `fire-canyon` scenario committed (e54263b); `wip/`
  untracked as before.

## Lessons (harness)

From #44-#48: scout-fly crates break only with a ground pound beside them;
a fly is collected by walking into it. Level hints don't play under the
harness. A teleport into a cluster of collectables fills the 32-pair
touching list in single player too: compare with a `coop=False` boot before
blaming co-op. Touch events need movement: walk in from outside. A cell
born where a player stands is taken at once; its task reads done after the
scene. Inside an attack event `*target*` is the attacker. Load boundaries:
the co-op loader ignores jumps over 10 m (`COOP_BOUNDARY_JUMP`): glide in
steps under 10 m. Never dereference an actor that may be gone in a REPL
probe. `mcp-kill-enemies-near` also kills battle controllers.
`task-complete?` reads the `real-complete` bit. GOAL `format` takes at most
six values. A probe script named like a stdlib module breaks anyio.

From #49:
- **A REPL form that writes through a missing field crashes the game**: a
  player's zoomer data (`racer`) is 0 until their first mount, and writing
  `(-> p racer heat)` on a fresh player wrote to protected memory (4 of the
  session's 9 crashes were the harness's). Guard with `(nonzero? (-> p racer))`.
- A crash with no message: `coredumpctl list`, then gdb on the core:
  `r13` is the GOAL process, `r15` the memory base; the function is the
  symbol whose value is the nearest below `rip - r15` (symbol names at
  `sym + 0x20000`, see `jak1::SYM_INFO_OFFSET`). This found both game crashes.
- Fire Canyon's floor is lava in places (`melt`): a rider parked on it
  dies; park riders frozen in the air (sleep mask), but a frozen player
  stops the other one's driving; a zoomer standing still heats up until it
  explodes. Crates break when a rider is teleported through them in 1.5 m
  steps (no throttle, no overshoot into lava).
- The start pad's prompt shows within 5 m of the pad, not of `FC_PAD`.
- The `[fc]` death logger in the `fire-canyon` scenario names the cause of
  every death (`melt`, `heat`, `burnup`).

## Cleanup the owner may approve

- `~/dev-scratch/jak-project/46/`, `47/`, `48/` (PR bodies, opened) and
  `rewrite/` (the cleanup is pushed and checked; the backup bundle is in
  `~/Documents/jak-coop-backup/`).
- `~/dev-scratch/jak-project/49/` once #49 is merged and a new `gk` is built
  elsewhere (its `build/` is 571 MB).
- The local-only branches with links: `coop/127-near-textures`,
  `test/playtest-2`, `test/playtest-fixes`.
- Tools checkout: `scratch/coop-test-mcp-before-rewrite.bundle`, `wip/`,
  old probe scripts in `scratch/`, `run/verify/` (about 40 runs).
