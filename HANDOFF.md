# Handoff

The session note for this fork. Read it first in a fresh session and rewrite
it at the end of every session (issue loop, last step). It lives in the
repository so it survives any worktree path and any tool; per-checkout agent
memory is not read by a session that starts in another worktree. State goes
here; stable recipes go into `docs/splitscreen/`; personal data and hardware
never.

Last updated 2026-10-17 (step 2 of the plan, the three streams, done: #50-#60 merged, plus the
crash triage, #163's scenario and #164; next: step 3, #146 then #11, alone).

## Done this run (step 2, coordinated)

One coordinator session started a fresh worker session per issue (Superset workspaces, one test
instance per stream) and merged each PR when its verify summary passed and the diff held up. All
merged into `feature/jak1-local-splitscreen`, in issue order within a stream:

| PR | Issue | Result |
| --- | --- | --- |
| #159 | #59 Citadel | citadel platforms ride both players (`citb-plat`, `coop-put-onto-platform`) |
| #160 | #54 Mountain Pass | no code change (docs) |
| #161 | #50 Rock Village | a cutscene's level load sets only the scene player's level pair (`coop-want-levels`) |
| #162 | #55 Volcanic Crater | no code change (docs) |
| #165 | crash triage | upstream exit segfault: `gl_exit()` before `SDL_Quit` (C++, `opengl.cpp`) |
| #166 | #51 Precursor Basin | dark eco plant, Gorge HUD event per player |
| #167 | #56 Spider Cave | launcher per player (`generic-obs`), dark crystals |
| #168 | #163 (scenario only) | `sky-beach` scenario, test 67; the black sky is not reproduced, #163 stays open |
| #169 | #164 Respawn camera | camera placed for the respawned player, 3 s invulnerability (`hit-invulnerable-timeout`) |
| #170 | #52 Lost Precursor City | sunken elevator, qbert platforms, tube, helix flood respawn (`coop-flood-at`) |
| #171 | #57 Snowy Mountain | snowballs: per-player hit cooldown |
| #172 | #60 Final boss | eco platforms, the sage's platform, a bomb nobody escaped knocks both out |
| #173 | #53 Boggy Swamp | no code change (docs) |
| #174 | #58 Lava Tube | player 2's view picks its own vis (own or adjacent level's, `coop-view-vis-choose`) |

Each area has a campaign scenario in the tools checkout (`demo/campaign/<area>.py`) and a TESTING.md
row (56-67). Tools README's campaign list names them all.

## Open pull requests

None.

Merge style: locally as Claude,
`git merge --no-ff -m "Merge pull request #N from Clodmony/<branch> (AI-assisted)"`
on a detached HEAD at `origin/feature/jak1-local-splitscreen`, then
`git push origin HEAD:feature/jak1-local-splitscreen`. Only when the owner says so; never
`gh pr merge` (it authors the merge with the owner's account). `gh` without
`--repo Clodmony/opengoal-coop` queries upstream.

## Next

**Step 3 (alone, no other test game running):** #146 (iGPU frame time: needs the GPU to itself),
then #11 (launcher non-debug build) on the merged result.

Open and waiting on the owner:
- **#163 black sky on the beach**: not reproduced by `sky-beach`. Needs the owner's moment (which
  view, does it stay or flicker, time of day, camera direction). Lead: #58 found player 2's view
  drawing a level with the vis player 1's camera picked (sky and black around player 2); that is
  fixed now, so a new playtest from the tip may already answer #163.
- Design defaults the workers took, for the owner to confirm: #164's respawn camera takes the
  partner's direction (not the player's own); #52's Rock Village elevator pulls the partner along
  both ways; #58: a chain mine costs a zoomer rider no health (vanilla, unchanged).
- Issues to file (found, not fixed; the owner decides which): the rock-village gambler intro stalls
  under the harness in 4 of 5 runs (base too); Daxter's `sidekick-clone` read an evicted spool buffer
  (one crash, co-op likely, shared `*art-control*`); flaky `forbidden-jungle` springbox and
  `sentinel-beach` scout fly checks; Boggy Swamp's spike gates stay up after the ambush; the citadel
  elevator button under the harness; the sage's beach intro leaves Sandover's warp gate hidden
  (single player too); swingpole, plat-eco, snow bumper and yeti checks look at the nearest player
  only (low).

Owner only: #1, #3, #8 (need a person), #7 (decision). Low priority: #157 (listener crash seen
once), #153 (turbo while waiting).

## Verify and build

- The verify script and the in-game harness live outside the repository in
  `~/Documents/jak-coop-tools/coop-test-mcp` (its README: "Parallel sessions", "A worktree's
  binaries"): `COOP_TEST_INSTANCE=<n> demo/verify.sh [--tests] [--suite] <worktree> [scenario ...]`,
  run in the background; read only `run/verify/<stamp>-i<n>/summary.txt`. **Flags go before the
  worktree**: after it, `--tests` is read as a scenario name and nothing runs. It starts instance n's
  bridge for the worktree when none runs and stops it afterwards.
- `demo/selftest.py` (about 20 s, no game, instances 6 and 7): run after a change to the bridge or
  the campaign loader.
- A worktree's binaries and data: `demo/worktree-setup.sh <worktree> [<build>]` (reflinks from
  `~/dev-scratch/jak-project/tip/`). `.superset/setup.sh` runs it in a new Superset workspace.
  **`tip/build` predates #165** (the exit fix): rebuild it from the tip before the next worker uses it.
- After a `kernel-defs.gc` change: `restart_compiler` before `build`. Engine (GAME.CGO) or level
  DGO changes need `boot fresh=True`: a warm boot keeps the old code and loaded levels.
- `goalc-test` leaves a SIGABRT core at exit in `--tests` runs while all tests pass (pre-existing).
- Playtest packages: `scripts/coop-mod/package_mod.py --bin-dir <build> --allow-dynamic --out-dir
  <tools>/builds` (needs `extractor` in the build folder). The last one the owner played:
  `builds/tip-b42798cdf/jak1-coop.tar.gz` (without #60, #165 and later). Its binaries,
  `scratch/build-play`, were since rebuilt with #165.
- Pushes: the owner's global push guard (pre-push) blocks Claude-Session links and secrets, and on
  public pushes runs a headless review. Never `--no-verify`. Its review text comes from `git log -p
  -- .`, which drops a clean `--no-ff` merge whose tree equals the branch's: the review then sees
  nothing and blocks. Push such a merge together with a following commit (e.g. the handoff). The
  review also refused once with no reason and passed on the retry.

## Worktrees and background processes

- Main checkout on `feature/jak1-local-splitscreen` (the owner's; its `build/` is old, don't copy
  binaries from it).
- The coordinator's Superset workspace: detached at the merged tip. The finished workers' Superset
  workspaces (one per issue above) are still there: remove them once the owner agrees.
- `~/dev-scratch/jak-project/tip/` (`src` and `build`, a78ec8b9d): the source of the workspaces'
  binaries and data; `~/dev-scratch/jak-project/streams/`: the coordinator's state, prompts and the
  workers' handoff files.
- No bridge or test game running; pads unplugged.

## Lessons (harness)

Crash dumps (#49, #155, crash triage): `coredumpctl list`, gdb on the core: `r13` is the GOAL process,
`r15` the memory base; the function is the symbol whose value is the nearest below `rip - r15`
(names at `sym + 0x20000`). Read `g_ee_main_mem`, `SymbolTable2`, `LastSymbol` from the gk binary
whose build id the core lists (`eu-unstrip -n --core`), map return addresses on the stack to function
entries, and to object files through `g_coop_linked` (40-byte entries: std::string, base, size).
A crash at exit with a page-aligned rip and no native frames was the upstream exit segfault (#165).

Things that crash the game from the REPL: writing through a field that is still 0 (a player's
`racer` before the first mount: guard with `nonzero?`); walking `(-> l bsp level entity)` of a slot
that isn't `active`; `(go-process ogreboss ogreboss-die)` before clearing `(-> ogreboss boulder)`;
a REPL lambda as a process `trans-hook`; a REPL logger process with `'stack-no-clear` vectors in a
`let` around its loop (use `(new 'global ...)`). Never dereference an actor that may be gone.

Teleports and loads:
- The co-op loader ignores jumps over 10 m: glide in steps under 10 m wherever a boundary matters
  (city, caves, swamp). Boundaries without the `player` flag are crossed by the **camera**: only the
  `teleport` tool brings the camera along; `mcp-glide` leaves it behind. A Python one-off that parses
  `load-boundary-data.gc` lists the boundaries near an area in a minute.
- A level loaded but not displayed: a player put into it falls. Keep players frozen (sleep mask)
  until the level is `active` and displayed; Precursor Basin's village2 shows through short camera
  gates, so ride waypoints through them.
- A teleport doesn't move a held player, and doesn't end an edge grab or a swing pole hang (jump or
  press cross first). A player in an edge grab isn't "ready", so the partner's respawn waits forever.
- A long teleport past a checkpoint boundary leaves the continue point behind.
- In Mountain Pass and Lava Tube a zoomer off the ground and slow for 5 s blows up ("unstuck"); reset
  `(-> p racer unstuck-time)` before waking a frozen rider. Park riders on route points, not off the
  track (pits) or on lava.
- A harness `boot` puts village1 in slot 0; a game started from the title has it in slot 1
  (`sb_start` in `sky_beach.py` gets the owner's order). The harness runs 4:3 side by side; the owner
  plays top-bottom with the window's aspect.

Story state for a later continue point: close the earlier intros through `need-introduction`
(`RV_NEW_GAME`, `PB_INTROS`); tasks that need `real-complete` (flut flut pad, shortcut boulder vents)
don't get it from `close-specific-task!`. Levitator, village3 button: done reads `invalid`; use
`task-closed?`. Rock Village's warp gate exists only when all four levitator stages are closed.

Game behaviour worth knowing: yellow eco shots home in a 45° cone on the target's origin, square in
the air is a ground pound; steel crates need eco, zoomer, flut flut, explosions or a 30 m drop; a
cell born by a scene jumps before it lands (re-find the nearest cell); a cell born where a player
stands is taken at once (check the task); `mcp-kill-enemies-near` wants float arguments and also
kills battle controllers and nav-enemy bosses; idle players in Snowy, the city and on the beach are
killed within a minute (clear the spot first); the respawn rule's distances are horizontal.

Harness mechanics:
- A process or REPL redefinition a scenario starts outlives a warm boot into the next scenario:
  switch it off in a `try`/`finally`, guard counters with a `define-perm` flag, boot `fresh=True`
  after a probe that redefines a function.
- `(movie?)` drops for a moment between a spooled scene's parts; wait for the NPC to enter and leave
  `play-anim`. A cell camera can start and end between two bridge queries: watch it in-game.
- `game_log` hands out each new line once whatever the filter: read once, filter in Python. The
  bridge prints a repl_eval's output after its JSON line (`raw_decode`). `screenshot issue=debug`
  goes to `run/i<n>/shots` only. GOAL `format` takes at most six values.
- The test game runs above 60 fps: bound logger processes by game time, not frames.
- Develop a scenario in scratch with a small runner that imports `scenarios` and loads the file with
  importlib: the shared `demo/campaign/` is imported by every session, so a half-written file there
  breaks the others. A change to a shared harness file is a small finished commit of its own.
- `pkill -f`/`pgrep -f` with a pattern in the shell's own command line matches that shell: bracket a
  letter (`[r]un.py`) or wait on a pid. zsh doesn't split an unquoted `$S`. bash reads a script as it
  runs: never edit a script another session is running.
- A new field in a decompiled type fails goalc-test's type consistency (`all-types.gc` must match);
  the compat check wants `og:preserve-this` on every changed line of a decompiled file.
- Compare against the base with `git worktree add --detach <scratch>/base <sha>` plus
  `worktree-setup.sh` (a minute); compare with a `coop=False` boot before blaming co-op.

Running parallel workers (step 2): one Superset workspace and one test instance per stream, a
fixed TESTING.md row range per stream, merges one at a time in issue order (TESTING.md and
ARCHITECTURE.md conflicts were all "keep both"). Several test games plus compiles at once ran the
machine low on memory once and killed a worker mid-change: close finished workers' terminals.

## Cleanup

Left for the owner to decide: the finished workers' Superset workspaces;
`~/dev-scratch/jak-project/tip/` and `streams/`; `builds/51-precursor-basin-19d75f6a1` (an extra
package); `scratch/build-play` (the last playtest's binaries) and `scratch/build-gk` (the installed
launcher mod's); the backup bundle in `~/Documents/jak-coop-backup/`; gk core dumps (systemd ages
them out); the test instances' run folders `run/i<n>/` in the tools checkout.
