# Jak 1 local split-screen co-op: compatibility

> Written with AI assistance (AI-assisted).

Nothing in this table has been playtested yet (no game assets in the development environment).
"Expected" columns are predictions from reading the code, not results.

## Campaign matrix

| Area (level) | Status | Expected issues / special handling |
| --- | --- | --- |
| Geyser Rock (`training`) | partial | 2026-10-10: co-op start, swimming, deadly water, deaths/respawn work. Not played through |
| Sandover Village (`village1`) | partial | 2026-10-10: NPC talk (either player, own pad), boat to Misty with both players, swimming, orbs, save/load work. Not played through |
| Sentinel Beach (`beach`) | partial | 2026-10-10: enemies target the closer player, both can kill them, crates. Cannon now reads the user's pad (untested); seagull scripts untested |
| Forbidden Jungle (`jungle`, `jungleb`) | untested | Power cell cinematic and dark vines work for player 2; periscope and fisherman read the user's pad (untested); elevator to the plant boss untested |
| Misty Island (`misty`) | untested | Zoomer section unsupported for player 2; balloon lurkers (pad-1 debug steering disabled in co-op) |
| Fire Canyon (`firecanyon`) | unsupported | Zoomer: vehicle mode not adapted for two players |
| Rock Village (`village2`) | untested | Flut flut (`flut_common`) not adapted; warp gate reads the user's pad but moves player 1's level (untested) |
| Precursor Basin (`rolling`) | unsupported | Zoomer level; lightning mole pad-1 debug disabled in co-op |
| Lost Precursor City (`sunken`) | untested | Water volumes (see below), helix room, tube slides (`target-tube`) |
| Boggy Swamp (`swamp`) | untested | Flut flut; Billy minigame (pad-1 skip disabled in co-op) |
| Mountain Pass (`ogre`) | unsupported | Zoomer + Klaww boss |
| Volcanic Crater (`village3`) | untested | Mine cart / cannons |
| Spider Cave (`maincave`, `darkcave`, `robocave`) | untested | Dark crystals, lights |
| Snowy Mountain (`snow`) | untested | Flut flut, ice, snowball |
| Lava Tube (`lavatube`) | unsupported | Zoomer |
| Gol and Maia's Citadel (`citadel`) | untested | Sage rescue cutscenes, final elevator |
| Final boss (`finalboss`) | unsupported | Scripted boss with camera control, not validated |

Status values: untested, works, partial, unsupported. "Unsupported" means not adapted; the game may
still run but player 2 behaviour there is undefined.

## Known gaps (code-level)

| Gap | Effect | Where |
| --- | --- | --- |
| Vehicles | Zoomer and flut flut assume one player | `levels/racer_common`, `levels/flut_common` |
| Fuel-cell pickup cutscene | Plays on the player who touched the cell (interaction latch). If both touch it in the same frame, it can play on the second one | `engine/common-obs/collectables.gc`, `coop-context-for-event` |
| Overlapping grabs | One grab pair is tracked; an NPC talk that overlaps an elevator ride may leave the partner held until the next grab/release | `coop-grab-other-player` |
| Shared player tuning objects | `*run-attack-mods*`, `*wade-surface*` and `*target-shadow-control*` are shared: one player's dash or wading depth can affect the other's, and a `shadow` event toggles both shadows | `engine/target/target.gc`, `engine/target/logic-target.gc` |
| Particle callbacks | Run in the display process (player 1's context): effects that track `*target*` (wall-smack sparks, first-person HUD particles) follow player 1 | `engine/target/target-part.gc`, `engine/target/target2.gc` |
| HUD particles | HUD shapes and text use the view's aspect now; HUD particles (health pips, orb sparkles) still run their callbacks in player 1's context | `engine/ui/hud-classes.gc`, `engine/gfx/sprite/sprite.gc` |
| Interactions with two players close by | The nearest player (0.25 m margin) uses an object; when both stand at the same spot it's whoever is a little closer to the object's origin | `coop-nearest-player-for`, `target-cpad-idx` |
| Two identical pads in single player | Upstream maps controllers to ports by model, so only one of two identical pads drives single player. Co-op assigns by device and is not affected | `game/system/hid/input_manager.cpp` `refresh_device_list` |
| Level streaming | Follows player 1 only; player 2 is kept within 60 m and pulled back if their level is unloaded | `splitscreen.gc` leash, `coop-on-level-leaving` |
| Ambients, sound listener, music | Follow player 1 (hints, ambient sounds, dark areas near player 2 don't trigger) | `engine/game/main.gc` ambients, `engine/sound/gsound.gc` `ear-trans` |
| Saves | Co-op saves go to `saves/coop/`. A co-op session starts from whatever game is loaded, so its progress comes from that single-player save; after "Stop co-op", auto-save stays off until a slot is chosen (so co-op progress isn't auto-saved over a single-player slot). Loading a save while co-op runs is not validated | `game/kernel/common/kmemcard.cpp`, `coop-set-save-folder` |
| Rumble | Target, eco and crate rumble go to the right pad. Still pad 0: orb/fly pickup buzz (`pickup-collectable!`, compiled before the co-op header), yellow eco projectiles, flut flut, zoomer, bouncer | `engine/game/game-info.gc`, `engine/game/projectiles.gc`, `levels/` |
| `ps2-lod-dist?` option | With the original LOD distances enabled, the two views may pick different LODs for the same actor | `engine/draw/drawable.gc` `dma-add-process-drawable` |
| Occlusion culling | Off on split frames (one vis buffer per level) | `OpenGLRenderer::dispatch_jak1_split_views` |
| Touching list | 32 overlap pairs per tick are now shared by two players; overflow drops touches | `engine/collide/collide-touch-h.gc` |
| Interaction latch on shared objects | A platform both players stand on is latched to whichever touched it last, so its `*target*` can alternate between players | `coop-context-for-event` |
| Input thread safety | Turning co-op off re-enumerates controllers on the graphics thread while the game thread reads them without a lock (same pattern as upstream hotplug; not observed to crash) | `game/system/hid/input_manager.cpp` |

## Unchanged by design

- With co-op never started, the kernel hooks are `#f` and every co-op branch is skipped; rider groups
  now always have room for two riders (behaviour-neutral).
- Jak 2, Jak 3 and Jak X: the shared C++ changes are opt-in (co-op input mode, Jak 1 renderer path).
