# Handoff

The session note for this fork. Read it first in a fresh session and rewrite
it at the end of every session (issue loop, last step). It lives in the
repository so it survives any worktree path and any tool; per-checkout agent
memory is not read by a session that starts in another worktree. State goes
here; stable recipes go into `docs/splitscreen/`; personal data and hardware
never.

Last updated 2026-10-16 (after #155, step 1b of the plan, merged; next: step 1, the parallel-ready
harness, then the streams; #157 is open, low priority).

## Done this session

- #155 (streaming crash): branch `coop/155-art-group-lists`, PR #156, scenario `art-group-lists`
  (harness commits 6a0e2c3 and the README after it). Both dumps showed an 11th entry in
  level-default's art-group list pointing into a reloaded slot heap. The cause: with co-op stopped
  the four slots stay in use, but the one-load-at-a-time guard only applied while co-op ran; a load
  begun during another level's login lost `loading-level` when that login ended. Fixed there, plus
  `coop-forget-art-in-heap` as a safety net. Also fixed: the residency guard used the "nearest
  level", a tie of zero bsp spheres that the first slot won (`streaming` failed every run once the
  beach sat in slot 0). Verify: 20 `streaming` runs in a row passed, 369/370 checks, compat ok,
  goalc-test 1692.
- Seen once in that verify, not explained: a crash in the listener path (`ProcessListenerMessage`
  -> `link_and_exec` with a garbage message, size 0), during `sky-pair`; `sky-pair` alone then passed
  5 of 5. Filed as #157.
- #156 merged into the co-op branch as Claude (owner said merge); #155 closed by it.
- Found by reading only, not fixed: a level discarded while a code object links keeps `linking`, and
  `load-continue` keeps resuming that link on the inactive slot (`level.gc` `unload!`). The owner
  chose not to file it; the safety net drops any art group it could add.

## Open pull requests

None (#156 merged). Merge style: locally as Claude,
`git merge --no-ff -m "Merge pull request #N from Clodmony/<branch> (AI-assisted)"`
on a detached HEAD at `origin/feature/jak1-local-splitscreen`, then
`git push origin HEAD:feature/jak1-local-splitscreen`. Only when the owner says so; never
`gh pr merge` (it authors the merge with the owner's account). `gh` without
`--repo Clodmony/opengoal-coop` queries upstream.

## Plan: parallel streams

The owner wants the rest done in parallel. Steps in order; each issue is
still one session (issue loop) ending in a handoff.

**Step 0: done** (cleanup, #46-#49 merged). The streams branch from the
co-op tip.

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

**Step 1b: done** (#155, PR #156, merged).

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

- Main checkout on `feature/jak1-local-splitscreen` at the merged tip.
  Superset worktree (the #49/#155 one): detached at the merged tip, clean. Its
  `build/game/gk` is the one from `~/dev-scratch/jak-project/49/build` (#155 changed no C++; keep
  that folder while a worktree uses this `gk`).
- The bridge (`demo/bridge.py serve`, instance 3) serves that worktree; its game is stopped and
  the pads unplugged.
- Harness checkout: `art-group-lists` scenario and README row committed (not pushed anywhere).
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

## Cleanup

Done 2026-10-16: #155's scratch (`~/dev-scratch/jak-project/155`, probes and cores). Left:
`~/dev-scratch/jak-project/49/` (the `gk` build the worktree uses), the backup bundle in
`~/Documents/jak-coop-backup/`, `scratch/build-gk` (the playtest's `gk`), and the gk core dumps
in `coredumpctl` (systemd ages them out).
