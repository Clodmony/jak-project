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
| 2. Two real player actors in one world | implemented, compiles; not playtested |
| 3. Two cameras rendering in one window | implemented, compiles; not playtested |
| 4. Two views don't advance the simulation twice | by construction (render-only pass); counters in the debug overlay; not playtested |

### B. Playable prototype

Implemented (compiles, not playtested): movement/jump/attack per player, independent cameras,
two viewports with per-view aspect, both players visible in both views, shared collectables (pickups
credit the toucher; orbs/cells/flies go to the shared `*game-info*`), per-player health HUD (each
player's HUD in their own view), no friendly fire, distance leash (60 m) plus residency guard,
debug-menu toggle, per-player death/respawn, either player can pause.

Open for B:
1. Playtest in Geyser Rock / Sandover (needs the user's game assets). Suggested area: Geyser Rock
   (training level: small, no vehicles, one level loaded). Then Sandover village and beach.
2. HUD text/particles in narrow views (aspect, ownership of HUD particles, see COMPATIBILITY.md).
3. Water volumes for the second player (deep water, dark eco, lava).

### C. Reliable local sessions

1. Progress-menu entry for co-op (start/stop, layout, device assignment), stored in a separate
   `coop-settings.gc` next to `pc-settings.gc` (never add keys to `pc-settings.gc`: other OpenGOAL
   builds sharing the folder would reject the whole file).
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

## Shipping as a mod (researched, not done)

OpenGOAL has no plugin loader: a launcher "mod" is a complete jak-project build (own `gk`, `goalc`,
`extractor`, `data/`). A fork with C++ changes is a normal mod.

- The OpenGOAL Launcher runs a mod's `gk` with
  `--config-path <install>/features/jak1/mods/<source>/_settings/<mod>`, so the mod gets its own
  settings and saves without code changes, separate from vanilla OpenGOAL.
- The launcher passes no custom arguments, so co-op must be enabled in game (menu or settings file).
- Packaging: copy the release tooling from `OpenGOAL-Mods/OG-Mod-Base` (`cut-release.yaml`,
  `mod-release-pipeline.yml`, `.github/scripts/...`) with `binary_source=build_binaries`. Release
  assets `windows-*.zip`, `linux-*.tar.gz`, `macos-*.tar.gz` with the binaries at the archive root.
- Distribution: "Add from File" in the launcher (keep the archive name fixed, it names the save
  folder), a self-hosted mod-source JSON, or the community list (jakmods.dev).
- New co-op code must write files through `*pc-settings-folder*`, not `*pc-user-dir-base-path*`
  (the latter ignores `--config-path`).
- Not verified end to end (no release run, no launcher install).

Keeping it rebaseable: co-op code lives in new files (`goal_src/jak1/pc/features/splitscreen*.gc`,
`goal_src/jak1/pc/debug/coop-menu.gc`, `game/system/hid/coop_slots.*`,
`game/graphics/opengl_renderer/SplitscreenLayout.h`). Hooks in upstream files are short and marked
`og:preserve-this coop:`; `git grep "coop:"` lists them. Merge `upstream/master` periodically.

## Next concrete task

Run the prototype with real game assets (TESTING.md, "Manual test plan"), starting with steps 1-6,
and fix what breaks before adding features.
