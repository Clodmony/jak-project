# Jak 1 local split-screen co-op: compatibility

> Written with AI assistance (AI-assisted).

Nothing in this table has been playtested yet (no game assets in the development environment).
"Expected" columns are predictions from reading the code, not results.

## Campaign matrix

| Area (level) | Status | Expected issues / special handling |
| --- | --- | --- |
| Geyser Rock (`training`) | untested, first target | Single level, no vehicles. Good first test |
| Sandover Village (`village1`) | untested | NPC talks hold both players; fisherman minigame and boat use pad 0 only |
| Sentinel Beach (`beach`) | untested | Cannon minigame pad 0; seagull/flut scripts |
| Forbidden Jungle (`jungle`, `jungleb`) | untested | Mirror minigame pad 0; plant boss (pad-1 debug skip disabled in co-op) |
| Misty Island (`misty`) | untested | Zoomer section unsupported for player 2; balloon lurkers (pad-1 debug steering disabled in co-op) |
| Fire Canyon (`firecanyon`) | unsupported | Zoomer: vehicle mode not adapted for two players |
| Rock Village (`village2`) | untested | Flut flut (`flut_common`) not adapted; warp gate moves player 1 only |
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
| Water volumes track one occupant | The second player in the same deep water / dark eco / lava volume gets no swim state and no damage | `engine/common-obs/water.gc` `update!` (`water-vol target` is one handle) |
| HUD text and particles in narrow views | HUD is laid out for the full window aspect: squeezed in side-by-side views. HUD particles (health pips, orb sparkles) are drawn in both views and their callbacks read player 1 | `engine/ui/hud-classes.gc`, `engine/gfx/sprite/sprite.gc` |
| Menus are pad 0 | Either player can pause, but only player 1 navigates the pause/progress menu | `engine/ui/progress/progress.gc` |
| Vehicles | Zoomer and flut flut assume one player | `levels/racer_common`, `levels/flut_common` |
| Fuel-cell pickup cutscene | Plays on the player who touched the cell (interaction latch). If both touch it in the same frame, it can play on the second one | `engine/common-obs/collectables.gc`, `coop-context-for-event` |
| Overlapping grabs | One grab pair is tracked; an NPC talk that overlaps an elevator ride may leave the partner held until the next grab/release | `coop-grab-other-player` |
| Shared player tuning objects | `*run-attack-mods*`, `*wade-surface*` and `*target-shadow-control*` are shared: one player's dash or wading depth can affect the other's, and a `shadow` event toggles both shadows | `engine/target/target.gc`, `engine/target/logic-target.gc` |
| Particle callbacks | Run in the display process (player 1's context): effects that track `*target*` (wall-smack sparks, first-person HUD particles) follow player 1 | `engine/target/target-part.gc`, `engine/target/target2.gc` |
| Level streaming | Follows player 1 only; player 2 is kept within 60 m and pulled back if their level is unloaded | `splitscreen.gc` leash, `coop-on-level-leaving` |
| Ambients, sound listener, music | Follow player 1 (hints, ambient sounds, dark areas near player 2 don't trigger) | `engine/game/main.gc` ambients, `engine/sound/gsound.gc` `ear-trans` |
| Saves | Co-op saves go to `saves/coop/`. A co-op session starts from whatever game is loaded, so its progress comes from that single-player save; after "Stop co-op", auto-save stays off until a slot is chosen (so co-op progress isn't auto-saved over a single-player slot). Loading a save while co-op runs is not validated | `game/kernel/common/kmemcard.cpp`, `coop-set-save-folder` |
| Rumble | Target, eco and crate rumble go to the right pad. Still pad 0: orb/fly pickup buzz (`pickup-collectable!`, compiled before the co-op header), yellow eco projectiles, flut flut, zoomer, bouncer | `engine/game/game-info.gc`, `engine/game/projectiles.gc`, `levels/` |
| `ps2-lod-dist?` option | With the original LOD distances enabled, the two views may pick different LODs for the same actor | `engine/draw/drawable.gc` `dma-add-process-drawable` |
| Occlusion culling | Off on split frames (one vis buffer per level) | `OpenGLRenderer::dispatch_jak1_split_views` |
| Touching list | 32 overlap pairs per tick are now shared by two players; overflow drops touches | `engine/collide/collide-touch-h.gc` |

## Unchanged by design

- With co-op never started, the kernel hooks are `#f` and every co-op branch is skipped; rider groups
  now always have room for two riders (behaviour-neutral).
- Jak 2, Jak 3 and Jak X: the shared C++ changes are opt-in (co-op input mode, Jak 1 renderer path).
