# Jak 1 local split-screen co-op: compatibility

> Written with AI assistance (AI-assisted).

Known limitations of the co-op, with where they come from in the code. Work on them is tracked in
the fork's GitHub issues (linked per row); test results are in TESTING.md.

## Campaign

Per-area status is tracked in the fork's GitHub issues labelled `co-op: campaign` (#44 Geyser Rock
to #60 final boss). Vehicle sections (zoomer #16, flut flut #17) and bosses (#18-#20) are not
adapted yet; until their issues are closed, player 2's behaviour there is undefined.

## Known gaps (code-level)

| Gap | Effect | Where | Issue |
| --- | --- | --- | --- |
| Vehicles | Zoomer: both players get their own zoomer at a pad, a player who dies goes back to their own last checkpoint alone, a finish pad waits for both, Lava Tube's energy doors stay open until both are through each player gets off on their own when they drive onto a pad, and if the flying lurkers reach the plunger in Mountain Pass the race is lost for both In Precursor Basin either player can fly through the race rings (each player's own path is checked, so switching players can't fake a pass), and the gorge race finishes once both crossed the line. Cinematics that freeze one player freeze both (tested in Fire Canyon, Lava Tube, Precursor Basin and parts of Mountain Pass). The gorge race timer shows in both views. During a cell cinematic on the zoomer or flut flut the other player is hidden and frozen, as on foot. Flut flut not adapted | `levels/racer_common`, `coop-racer-*` in `splitscreen.gc`, `levels/flut_common` | #16, #17 |
| Fuel-cell pickup cutscene | Plays on the player who touched the cell (interaction latch). If both touch it in the same frame, it can play on the second one | `engine/common-obs/collectables.gc`, `coop-context-for-event` | #36 |
| Overlapping grabs | One grab pair is tracked; an NPC talk that overlaps an elevator ride may leave the partner held until the next grab/release | `coop-grab-other-player` | #30 |
| Shared player tuning objects | `*run-attack-mods*`, `*wade-surface*` and `*target-shadow-control*` are shared: one player's dash or wading depth can affect the other's, and a `shadow` event toggles both shadows | `engine/target/target.gc`, `engine/target/logic-target.gc` | #28 |
| Particle callbacks | Run in the display process (player 1's context): effects that track `*target*` (wall-smack sparks, first-person HUD particles) follow player 1 | `engine/target/target-part.gc`, `engine/target/target2.gc` | #26 |
| HUD particles | HUD shapes and text use the view's aspect now; HUD particles (health pips, orb sparkles) still run their callbacks in player 1's context | `engine/ui/hud-classes.gc`, `engine/gfx/sprite/sprite.gc` | #26 |
| Interactions with two players close by | The nearest player (0.25 m margin) uses an object; when both stand at the same spot it's whoever is a little closer to the object's origin | `coop-nearest-player-for`, `target-cpad-idx` | #31 |
| Two identical pads in single player | Upstream maps controllers to ports by model, so only one of two identical pads drives single player. Co-op assigns by device and is not affected | `game/system/hid/input_manager.cpp` `refresh_device_list` | upstream |
| Level streaming | Follows player 1 only; player 2 is kept within 60 m and pulled back if their level is unloaded | `splitscreen.gc` leash, `coop-on-level-leaving` | #23 |
| Ambients, sound listener, music | Follow player 1 (hints, ambient sounds, dark areas near player 2 don't trigger) | `engine/game/main.gc` ambients, `engine/sound/gsound.gc` `ear-trans` | #25 |
| Saves | Co-op saves go to `saves/coop/`. A co-op session starts from whatever game is loaded, so its progress comes from that single-player save; after "Stop co-op", auto-save stays off until a slot is chosen (so co-op progress isn't auto-saved over a single-player slot). Loading a save while co-op runs is not validated | `game/kernel/common/kmemcard.cpp`, `coop-set-save-folder` | #32, #4 |
| Rumble | Target, eco and crate rumble go to the right pad. Still pad 0: orb/fly pickup buzz (`pickup-collectable!`, compiled before the co-op header), yellow eco projectiles, flut flut, zoomer, bouncer | `engine/game/game-info.gc`, `engine/game/projectiles.gc`, `levels/` | #27 |
| `ps2-lod-dist?` option | With the original LOD distances enabled, the two views may pick different LODs for the same actor | `engine/draw/drawable.gc` `dma-add-process-drawable` | #34 |
| Occlusion culling | Off on split frames (one vis buffer per level) | `OpenGLRenderer::dispatch_jak1_split_views` | #34 |
| Touching list | 32 overlap pairs per tick are now shared by two players; overflow drops touches | `engine/collide/collide-touch-h.gc` | #29 |
| Interaction latch on shared objects | A platform both players stand on is latched to whichever touched it last, so its `*target*` can alternate between players | `coop-context-for-event` | #31 |
| Input thread safety | Turning co-op off re-enumerates controllers on the graphics thread while the game thread reads them without a lock (same pattern as upstream hotplug; not observed to crash) | `game/system/hid/input_manager.cpp` | #35 |

## Unchanged by design

- With co-op never started, the kernel hooks are `#f` and every co-op branch is skipped; rider groups
  now always have room for two riders (behaviour-neutral).
- Jak 2, Jak 3 and Jak X: the shared C++ changes are opt-in (co-op input mode, Jak 1 renderer path).
