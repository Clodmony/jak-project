# Jak 1 local split-screen co-op: plan

> Written with AI assistance (AI-assisted).

## Setup (done)

- Fork: `Clodmony/jak-project` (`origin`), upstream `open-goal/jak-project` (`upstream`).
- Starting upstream commit: `efb21c3e8c5a40a74f2e86510f915da55eaeba34` ("[jak3] polish translation (#4431)").
- Branches: `feature/jak1-local-splitscreen` (requested) and `claude/friendly-pasteur-ds7949`
  (the session's push branch) point at the same commits.
- Build: `cmake -B build --preset=Release-linux-clang && cmake --build build -j4`
  (the documented `task gen-cmake-release` / `task build-release` run the same commands; `task` is not
  installed in this environment).

## Milestones

### A. Baseline and technical spikes

| Spike | Status |
| --- | --- |
| Baseline build, GOAL compile, test suite | done (see TESTING.md) |
| 1. Two devices feed independent player slots | implemented + unit tested; not run on hardware |
| 2. Two real player actors in one world | verified in game 2026-10-10 (REPL-driven, no controllers) |
| 3. Two cameras rendering in one window | verified in game 2026-10-10, both layouts |
| 4. Two views don't advance the simulation twice | verified in game 2026-10-10 (tick/pass/frame counters, see TESTING.md step 6) |

### B. Playable prototype

Implemented (compiles, not playtested): movement/jump/attack per player, independent cameras,
two viewports with per-view aspect, both players visible in both views, shared collectables (pickups
credit the toucher; orbs/cells/flies go to the shared `*game-info*`), per-player health HUD (each
player's HUD in their own view), no friendly fire, distance leash (60 m) plus residency guard,
debug-menu toggle, per-player death/respawn, either player can pause.

Done for B (2026-10-10, tested in game, see TESTING.md): playtest in Sandover/beach/jungle with two
virtual pads, HUD and 2d proportions in split views, water volumes for the second player, player 2
in menus and NPC conversations.

Open for B: HUD particle callbacks (player 1's context), keyboard steps of the test plan.

### C. Reliable local sessions

1. Done (compiles, not playtested): Misc Options entries for co-op on/off, layout and automatic
   device assignment. Open: a join screen ("press a button on the pad for player 2") and remembering
   the layout in a separate `coop-settings.gc` next to `pc-settings.gc` (never add keys to
   `pc-settings.gc`: other OpenGOAL builds sharing the folder would reject the whole file).
2. Done (compiles and unit tested, not playtested): separate co-op save folder `saves/coop/`
   (`mc_set_namespace` in `game/kernel/common/kmemcard.cpp`), switched in `coop-start`/`coop-stop`,
   auto-save off until a slot is chosen in the save menu.
3. Device disconnection UI (the slot status already reports "disconnected").
4. Cutscene entry/exit validation per cutscene type (pov-camera, process-taskable, fuel cell).
5. Level transitions (warp gates, elevators) with both players.
6. Menu navigation by the player who paused.

### D. Campaign compatibility

Area by area, see COMPATIBILITY.md. Vehicles (zoomer, flut flut), bosses and minigames need individual
work; until validated they are listed as unsupported.

## Shipping as a mod

OpenGOAL has no plugin loader: a launcher "mod" is a complete jak-project build (own `gk`, `goalc`,
`extractor`, `data/`). A fork with C++ changes is a normal mod.

- The OpenGOAL Launcher runs a mod's `gk` with
  `--config-path <install>/features/jak1/mods/<source>/_settings/<mod>`, so the mod gets its own
  settings and saves without code changes, separate from vanilla OpenGOAL.
- The launcher passes no custom arguments, so co-op is enabled in game: Misc Options > "Local co-op"
  (works without `-debug`).
- Packaging: copy the release tooling from `OpenGOAL-Mods/OG-Mod-Base` (`cut-release.yaml`,
  `mod-release-pipeline.yml`, `.github/scripts/...`) with `binary_source=build_binaries`. Release
  assets `windows-*.zip`, `linux-*.tar.gz`, `macos-*.tar.gz` with the binaries at the archive root.
- Distribution: "Add from File" in the launcher (keep the archive name fixed, it names the save
  folder), a self-hosted mod-source JSON, or the community list (jakmods.dev).
- New co-op code must write files through `*pc-settings-folder*`, not `*pc-user-dir-base-path*`
  (the latter ignores `--config-path`).
- Not verified end to end (no release run, no launcher install).

## Staying an add-on

The co-op is maintained as a change set on top of upstream OpenGOAL, never a diverging copy:

- Co-op code lives in new files (`goal_src/jak1/pc/features/splitscreen*.gc`,
  `goal_src/jak1/pc/debug/coop-menu.gc`, `game/system/hid/coop_slots.*`,
  `game/graphics/opengl_renderer/SplitscreenLayout.h`). Edits to upstream files are short hooks.
- With co-op off, Jak 1 behaves like upstream (the kernel hooks are `#f`, every co-op branch is
  skipped), and Jak 2/3/X are not affected at all.
- Files other games compile stay byte-identical to upstream: everything under `goal_src/` outside
  `goal_src/jak1/`, plus the Jak 1 files Jak 2/3/X reuse (`pckernel-h`, `pckernel-common`,
  `pc-debug-common`).
- Every hand edit in a decompiled file carries `og:preserve-this` (upstream's CI then flags any
  regeneration that would drop it).
- Shared C++ runtime changes only take effect when Jak 1 turns co-op on.

Tools:
- `scripts/splitscreen/check_upstream_compat.py`: checks the first two file rules against the merge
  base with upstream and lists the shared C++ files to review. Run it before every push.
- `scripts/splitscreen/sync_upstream.sh`: merges `upstream/master`, builds, compiles all Jak 1 code,
  runs `test.sh` (includes the Jak 2/3/X compile and type checks) and the compatibility check.
  `--preview` only lists conflicting files.

## Next concrete task

Tracked as GitHub issues on the fork, not in these files.
