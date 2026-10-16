# Handoff

The session note for this fork. Read it first in a fresh session and rewrite
it at the end of every session (issue loop, last step). It lives in the
repository so it survives any worktree path and any tool; per-checkout agent
memory is not read by a session that starts in another worktree. State goes
here; stable recipes go into `docs/splitscreen/`; personal data and hardware
never.

Last updated 2026-10-16 (step 1 of the plan, the parallel-ready harness, done: PR #158; next:
step 2, the three streams in parallel; #157 and #153 open, low priority).

## Done this session

- Step 1, parallel-ready harness (no game change). Branch `coop/parallel-harness`, PR #158 (docs:
  TESTING.md's "one test instance per session", `.superset/setup.sh` copies the test binaries and
  game data into a new workspace, this note). No GitHub issue: `gh issue create` was
  blocked by the session's permission rules (the body is in the PR). Harness commits in the tools
  checkout: `02ac235` (campaign files), `2a949e1` (parallel sessions), `83ba543` (worktree setup).
  - Reproduced: a second bridge (instance 2) took over the one `run/bridge.sock`, a `stop-bridge`
    sent as instance 3 stopped instance 2's bridge and orphaned instance 3's; instance 4 stopped at
    start-up (`IndexError` at `PAD_PRODUCTS[INSTANCE]`). Found on the way: editing `verify.sh`
    while it runs breaks the runs in progress (bash reads it as it goes).
  - Fixed: bridge per instance (`run/i<n>/bridge.sock`, `COOP_TEST_INSTANCE` required, `bridge.py
    info`, a lock refuses a second bridge); `verify.sh` per instance (bridge, compile ports 8200+n,
    log folder `<stamp>-i<n>`), starts its instance's bridge when none runs and stops it, refuses
    one serving another worktree, `goalc-test` one at a time (`flock`), checks the worktree's
    binaries, one function (edits can't disturb a run); pad ids for instances 0-7; media numbers
    under a lock; the six campaign scenarios moved unchanged into `demo/campaign/<area>.py`
    (loaded by `scenarios.py`, `--list`); `demo/worktree-setup.sh` (binaries and game data into a
    worktree); `demo/selftest.py` (no game, 15 checks).
  - Results: self-test 15/15 (the old harness fails it). Three `verify.sh` runs started together on
    instances 3, 4, 5 (one worktree, games on ports 8142/8152/8162): `warp deaths-apart` 17/17 each;
    the six moved campaign scenarios two per instance, 111/111, 127/127, 98/98 (336 checks, the counts
    TESTING.md records), with `verify.sh` edited during the runs. A fresh worktree set up only by
    `worktree-setup.sh` passed `warp` on instance 4 while the tip checkout passed it on instance 5
    (the tip build's `gk`); the tip asking for instance 4 while 4 served the other worktree was
    refused. Not run: `--suite`.

## Open pull requests

- #158 `coop/parallel-harness`: docs, `.superset/setup.sh` and this note (the harness itself is the
  local tools checkout, already committed there). Needs: the owner's merge.

Merge style: locally as Claude,
`git merge --no-ff -m "Merge pull request #N from Clodmony/<branch> (AI-assisted)"`
on a detached HEAD at `origin/feature/jak1-local-splitscreen`, then
`git push origin HEAD:feature/jak1-local-splitscreen`. Only when the owner says so; never
`gh pr merge` (it authors the merge with the owner's account). `gh` without
`--repo Clodmony/opengoal-coop` queries upstream.

## Plan: parallel streams

The owner wants the rest done in parallel. Steps in order; each issue is
still one session (issue loop) ending in a handoff.

**Step 0, 1b, 1: done** (cleanup #46-#49; #155; the parallel-ready harness). The streams branch
from the co-op tip.

**Step 2: three streams in parallel**, each its own worktree, test instance and scenario file. Test
numbers fixed up front (TESTING.md rows):

| Stream | Instance | Issues, in order | Notes | Tests |
| --- | --- | --- | --- | --- |
| A Rock Village hub | 3 | #50 Rock Village, #51 Precursor Basin, #52 Lost Precursor City, #53 Boggy Swamp | village2 code, zoomer (#51), flut flut (#53) | 56-59 |
| B Mountain Pass to village3 | 4 | #54 Mountain Pass, #55 Volcanic Crater, #56 Spider Cave, #57 Snowy Mountain, #58 Lava Tube | village2 and village3 share code with Mountain Pass between them; zoomer (#54, #58), flut flut (#57) | 60-64 |
| C Endgame | 5 | #59 Citadel, #60 final boss | own continue points; the citadel shares the village code | 65-66 |

A stream session's first steps:
1. Worktree from the tip: a Superset workspace, or `git worktree add -b coop/<issue>-<topic>
   ~/dev-scratch/jak-project/<issue> origin/feature/jak1-local-splitscreen`; run
   `.superset/setup.sh` in it (after #158 is merged; before, run step 2 by hand).
2. Binaries and game data: `.superset/setup.sh` runs
   `~/Documents/jak-coop-tools/coop-test-mcp/demo/worktree-setup.sh <worktree>`: `gk`, `goalc`,
   `goalc-test` from `~/dev-scratch/jak-project/tip/build` (a build of the tip, a78ec8b9d), the
   game data, `out/jak1` and the goalc user settings from `~/dev-scratch/jak-project/tip/src` (a
   worktree of the tip), as reflinks. A branch that changes C++ builds its own folder and passes
   it (commands at the top of that script).
3. Every bridge and verify call with the stream's instance: `COOP_TEST_INSTANCE=<n> .../verify.sh
   <worktree> <scenarios>`, `COOP_TEST_INSTANCE=<n> ~/Documents/jak-coop-tools/scratch/b <tool> ...`.
   Never the session's own MCP tools for the worktree: they are instance 0 on the main checkout.
4. The area's scenario is a new file `demo/campaign/<area>.py` (copy the header of
   `fire_canyon.py`: `from scenarios import *`, `import scenarios as S`, `SCENARIOS`, `COST`);
   commit only that path in the tools checkout (`git commit -- demo/campaign/<area>.py`). Shared
   helpers (`scenarios.py`'s campaign helpers section, `server.py`, `mcp-helper.gc`) change in a
   small finished commit of their own: the other streams use the same checkout.

Streams B and C go through levels that share code: watch the game log for
`[coop] shared code: N objects paired, M symbols and methods moved` when the
players are in different levels, and check that shared functions point into
a loaded level (the `FC_SHARED` probe in `campaign/fire_canyon.py`).
`splitscreen.gc` and TESTING.md get parallel edits in different sections:
merge the PRs one at a time, in issue order.

**Step 3 (alone, after the streams):** #146 (iGPU frame time: needs the GPU
to itself, no other test game running), then #11 (launcher non-debug build)
on the merged result.

Owner only: #1, #3, #8 (need a person), #7 (decision). Low priority: #157 (listener crash seen
once), #153 (turbo while waiting).

## Verify and build

- The verify script and the in-game harness live outside the repository in
  `~/Documents/jak-coop-tools/coop-test-mcp` (its README: "Parallel sessions", "A worktree's
  binaries"): `COOP_TEST_INSTANCE=<n> demo/verify.sh [--tests] [--suite] <worktree> [scenario ...]`,
  run in the background; read only `run/verify/<stamp>-i<n>/summary.txt`. It starts instance n's
  bridge for the worktree when none runs and stops it afterwards; a bridge of that instance serving
  another worktree is an error. Instance 3 is the default.
- `demo/selftest.py` (about 20 s, no game, instances 6 and 7): run after a change to the bridge or
  the campaign loader.
- A worktree's binaries and data: `demo/worktree-setup.sh` (above, step 2 of a stream's first steps).
- After a `kernel-defs.gc` change: `restart_compiler` before `build`.
- Playtest packages: `scripts/coop-mod/package_mod.py --bin-dir <build>
  --allow-dynamic --out-dir <tools>/builds`. The current package
  (`builds/jak1-coop.tar.gz`, from #48, without #49) is what the owner plays.

## Worktrees and background processes

- Main checkout on `feature/jak1-local-splitscreen` (the owner's; its `build/` is from 2026-10-12,
  older than #49's C++: don't copy binaries from it).
- Superset worktree (the #49/#155/step 1 one): on `coop/parallel-harness`, clean after the commit. Its
  binaries now come from `tip/build` (its `.superset/setup.sh` ran).
- `~/dev-scratch/jak-project/tip/`: `src` (a detached worktree of the tip, a78ec8b9d, with game data
  and a compiled `out/`) and `build` (gk, goalc, goalc-test built from it): the source of every
  stream worktree's binaries and data. Keep it while the streams run; the copied `gk` loads its
  libraries from `tip/build`.
- No bridge or test game running; pads unplugged.
- Pushes: the owner's global push guard (`~/.gitconfig` `hook.push-guard`, pre-push) blocks
  Claude-Session links and secrets on every push; on public pushes also non-noreply emails and a
  failed headless review. Large files (10 MB) only warn. Never `--no-verify`.

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

From #155:
- A crash dump names its GOAL function and callers: read `g_ee_main_mem`, `SymbolTable2`,
  `LastSymbol` from the gk binary whose build id the core lists (`eu-unstrip -n --core`; the
  playtest `gk` in `scratch/build-gk` made older cores), map return addresses on the stack to the
  nearest function/method entry, and to object files through the kernel's `g_coop_linked` records
  (40-byte entries: std::string, base, size). A level's art-group list: `level + 48` (load-dir),
  arrays at `+4`/`+8`, data at `+12`.
- Every level's bsp sphere is zero: never pick "the nearest level" by `bsp bsphere`.
- A REPL form that spins `load-continue` drives a load frame-free (the IOP loads meanwhile): good
  for exact orderings (a load begun during a login); a bounded `dotimes` of 1e8 spins times out the
  listener instead.
- zsh doesn't split an unquoted `$S`: build repeated scenario lists in bash arrays.

From step 1:
- bash reads a script as it runs: an edit to a running script breaks it at the next line it reads
  (`verify.sh` is now one function). The same holds for any shell script another session runs.
- `gh issue create` (and other GitHub writes the owner didn't ask for in so many words) can be
  blocked by the session's permission rules: ask the owner, don't work around it.
- A module run as `__main__` and imported by name is two modules: `scenarios.py` registers itself as
  `scenarios` before loading the campaign files, else they would get a second copy (own `CHECKS`,
  flags never set).

## Cleanup

Done 2026-10-16: step 1's scratch (`~/dev-scratch/jak-project/harness`: probes, the old-harness and
stream-test worktrees). Left: `~/dev-scratch/jak-project/tip/` (above, while the streams run),
`~/dev-scratch/jak-project/49/` (#49's build; no worktree uses it any more: the owner may approve
deleting it), the backup bundle in `~/Documents/jak-coop-backup/`, `scratch/build-gk` (the
playtest's `gk`), the gk core dumps in `coredumpctl` (systemd ages them out), and the test
instances' run folders `run/i<n>/` in the tools checkout (settings copies; 6 and 7 are the
self-test's).
