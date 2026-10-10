# Jak 1 local split-screen co-op: plan

> Written with AI assistance (AI-assisted).

## Setup (done)

- Fork: `Clodmony/jak-project` (`origin`), upstream `open-goal/jak-project` (`upstream`).
- Starting upstream commit: `efb21c3e8c5a40a74f2e86510f915da55eaeba34` ("[jak3] polish translation (#4431)").
- Branches: `feature/jak1-local-splitscreen` (requested, co-op development) and
  `feature/jak1-coop-launcher-mod` (launcher mod packaging and releases, see MOD.md). A second
  push branch of the development session held the same commits as the first.
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

## Shipping as a mod (tooling done, not verified end to end)

OpenGOAL has no plugin loader: a launcher "mod" is a complete jak-project build (own `gk`, `goalc`,
`extractor`, `data/`). A fork with C++ changes is a normal mod. Details and steps: MOD.md.

Done on branch `feature/jak1-coop-launcher-mod`:
- Local package: `scripts/coop-mod/package_mod.py` builds the launcher archive from a local build
  (same layout as the release assets, committed git-tracked files only, allow list for every
  entry, custom assets that game.gp builds must be present; refuses binaries older than their
  C/C++ sources and builds that need libraries from the build folder, read from the ELF/PE/Mach-O
  files themselves; prints the minimum glibc/libstdc++ of a Linux build) for "Add from File". Name
  fixed to `jak1-coop` because the launcher uses the file name as the mod name and settings/save
  folder.
- GitHub releases: OG-Mod-Base's `cut-release.yaml` / `mod-release-pipeline.yml` and scripts,
  always building this fork's binaries (`Release-*-clang-static`), releasable from `master` and
  `feature/jak1-coop-launcher-mod` (`releaseBranches`), only when the release commit contains all
  of `feature/jak1-local-splitscreen`; the chosen bump decides the version (passed as
  `custom_tag`). Assets: `windows-<tag>.zip`, `linux-<tag>.tar.gz`, `macos-intel-<tag>.tar.gz`,
  `metadata.json`.
- Settings and saves: the launcher passes
  `--config-path <install>/features/jak1/mods/<source>/_settings/<mod>`, so the mod has its own
  settings and saves (co-op saves in `saves/coop/`), separate from vanilla OpenGOAL.
- The launcher passes no custom arguments, so co-op is enabled in game: Misc Options > "Local co-op"
  (works without `-debug`).
- New co-op code must write files through `*pc-settings-folder*`, not `*pc-user-dir-base-path*`
  (the latter ignores `--config-path`).

Open:
1. Keep merging `feature/jak1-local-splitscreen` into `feature/jak1-coop-launcher-mod` before each
   release (last merged 2026-10-10 at `ee509d24`; MOD.md "Before every release").
2. Install a local package in the launcher and play it (needs the user's game files).
3. Fork setup on GitHub: enable Actions, make `cut-release.yaml` dispatchable (default branch or a
   copy on `master`), then cut the first release.
4. Optional: a self-hosted mod-source JSON (example in MOD.md) or a listing on the community list.

Keeping it rebaseable: co-op code lives in new files (`goal_src/jak1/pc/features/splitscreen*.gc`,
`goal_src/jak1/pc/debug/coop-menu.gc`, `game/system/hid/coop_slots.*`,
`game/graphics/opengl_renderer/SplitscreenLayout.h`). Hooks in upstream files are short and marked
`og:preserve-this coop:`; `git grep "coop:"` lists them. Merge `upstream/master` periodically.

## Next concrete task

Run the prototype with real game assets (TESTING.md, "Manual test plan"), starting with steps 1-6,
and fix what breaks before adding features.
