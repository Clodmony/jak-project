# Jak 1 local split-screen co-op: progress

> Written with AI assistance (AI-assisted). Newest first.

## 2026-10-10: launcher mod packaging, review fixes (branch `feature/jak1-coop-launcher-mod`)

- `package_mod.py` now refuses (each with an `--allow-...` override): binaries older than their
  C/C++ sources; staged-but-uncommitted, untracked or deleted files in the packaged folders;
  archives missing custom assets that game.gp builds. Linking is judged from the binaries (ELF
  libraries and RUNPATH, PE imports including delay-loaded DLLs, Mach-O dylibs), not from
  CMakeCache; Linux builds report their minimum glibc/libstdc++ (this machine's build needs glibc
  2.38 and `GLIBCXX_3.4.32`, more than Ubuntu 22.04 has). More game disc names are denied;
  `--check` reports a corrupt archive instead of a Python traceback.
- Cut Mod Release: refuses a release that misses commits of `feature/jak1-local-splitscreen`, and
  computes the version from the chosen bump (passed as `custom_tag`, so commit messages no longer
  override it).
- Not done: merging `feature/jak1-local-splitscreen` (10 commits ahead, including the respawn HUD
  crash fix) into this branch; steps in MOD.md.

## 2026-10-09: launcher mod packaging (branch `feature/jak1-coop-launcher-mod`)

- `scripts/coop-mod/package_mod.py`: packages a local build as an OpenGOAL Launcher mod for
  "Add from File" (`build/coop-mod/jak1-coop.tar.gz`, `.zip` on Windows). Same layout as the
  release assets; only git-tracked files; every entry checked against an allow list before and
  after writing (no `iso_data`, `decompiler_out`, `out`, saves, settings, game file types, symlinks,
  keys); refuses dynamically linked builds unless `--allow-dynamic` (Linux/macOS only);
  `--check` verifies any archive, including downloaded release assets.
- GitHub release tooling from OpenGOAL-Mods/OG-Mod-Base (ISC): "Cut Mod Release" workflow, mod
  release pipeline, bundling scripts, metadata schema. Always builds this fork's binaries; releases
  only from `master` and `feature/jak1-coop-launcher-mod` (otherwise the tag action would make
  `v0.0.1-<branch>.N` pre-release tags). Shared build workflows unchanged.
- Docs: MOD.md (build, package, Add from File, release setup, settings/save paths, updating).

Verified (Linux): the package from a static build and from the dynamic `build/` has exactly the
paths and modes of the official `extract_mod_build_unix.sh` output, identical `data/`; extracted
binaries run (`gk --version`, `--help`, launcher-style `gk` arguments); forbidden content is
rejected; archives are reproducible; workflows pass PyYAML and actionlint (only template
warnings left in the copied pipeline); `metadata.json` validates with ajv-cli and jsonschema.

Not verified: a release run on GitHub, an install in the launcher, Windows packaging with real
binaries, the game itself.

## 2026-10-09: saves, in-game toggle, review fixes (compiles, not playtested)

- Co-op saves in their own folder `saves/coop/`; auto-save stays off until a slot is picked.
- In-game options (no debug build needed, so a launcher mod can use it): Misc Options >
  "Local co-op", "Co-op split top/bottom", "Co-op assign devices".
- From an adversarial code review (four reviewers: single-player regressions, context switching,
  GOAL rendering, C++ rendering):
  - grab/release pairs: releasing either player releases both (elevator started by player 2 no
    longer leaves a player stuck);
  - a world process touched/attacked by a player stays with that player (fuel-cell victory plays
    on the collector);
  - the manager also runs while paused, so menus are full screen instead of in player 1's half;
  - player 2's first-person HUD belongs to player 2;
  - target rumble goes to the right pad;
  - stopping co-op while a player waits to respawn no longer leaves an invisible Jak;
  - `*ACTOR-bank*` is restored by "Stop co-op";
  - decompiler reference for the two new target states.
- Second round from the same review (verified findings):
  - input: an unassigned/disconnected slot reports a disconnected pad (it kept its last input
    before), held keys are released when the mapping changes (stuck stick), keyboard hotkeys work
    with two pads, the join key doesn't leak into gameplay, an idle identical pad can't take over a
    disconnected slot, enabling co-op auto-assigns unless devices were chosen;
  - rendering: death dissolve and TIE wind advance once per frame, particles aren't culled against
    one player's camera, distortion tables per view, one shared view framebuffer that is freed after
    split screen ends, small-profiler times add up both views;
  - gameplay: cutscene input freeze only applies to player 2 (fixes a fisherman minigame soft-lock),
    respawn spots use the player's position when the safe-ground point is stale (fixes a leash
    respawn loop after boat/elevator rides), grabbers that end a grab directly free both players.

## 2026-10-09: first prototype (compiles, not playtested)

Implemented:
- Input: explicit device -> player slot assignment (`coop::SlotAssigner`), SDL instance ids,
  disconnect/reconnect rules, `pc-coop-*` GOAL API. Fixed a pre-existing bug where PS3 pressure axes
  from any joystick leaked into every pad.
- Player contexts: kernel hooks switch the player globals per process run and per event delivery;
  world processes use the closest player in play.
- Player 2: own target, daxter, camera rig, HUD, pools; light spawn state; respawn and leash manager.
- Rendering: one chain with a bucket group per view, render-only pass for player 2, per-view
  framebuffers composited into side-by-side or top/bottom rects, per-view aspect.
- Gameplay: no friendly fire (red-eco/flut flop trackers), separate attack-id ranges, cutscenes and
  talks hold both players, platforms carry two riders, either player pauses, player 2 controller
  loss pauses, pad-1 debug binds disabled in co-op.
- Death: one player's death no longer resets the world; respawn next to the other player after 2 s;
  both down -> one checkpoint reload.
- Streaming: player 2's level from its own position, residency guard before a level under player 2
  is unloaded or hidden, level events to both cameras, level timer counted once.
- Debug menu "Local Co-op" with an info overlay (ticks vs. view-2 render passes, device status).

Verified: C++ build, all Jak 1 GOAL code (522 targets), 1685 tests (1669 baseline + 16 new),
type consistency for all games. See TESTING.md.

Not verified: anything at runtime. No game assets, controllers or GPU session were available.

Next: run the manual test plan in TESTING.md with real assets, starting in Geyser Rock.
