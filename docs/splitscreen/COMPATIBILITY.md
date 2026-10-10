# Jak 1 local split-screen co-op: compatibility

> Written with AI assistance (AI-assisted).

Known limitations of the co-op, with where they come from in the code. Work on them is tracked in
the fork's GitHub issues (linked per row); test results are in TESTING.md.

## Campaign

Per-area status is tracked in the fork's GitHub issues labelled `co-op: campaign` (#44 Geyser Rock
to #60 final boss). Bosses (#18-#20) are not adapted yet; until their issues are closed, player 2's
behaviour there is undefined.

## Known gaps (code-level)

| Gap | Effect | Where | Issue |
| --- | --- | --- | --- |
| Zoomer | Both players get their own zoomer at a pad. A player who dies goes back to their own last checkpoint alone, a finish pad waits for both, Lava Tube's energy doors stay open until both are through, each player gets off on their own when they drive onto a pad, and if the flying lurkers reach the plunger in Mountain Pass the race is lost for both. In Precursor Basin either player can fly through the race rings (each player's own path is checked, so switching players can't fake a pass); with the option "Co-op: every ring for both" each ring counts only once both flew through it, and the gorge race finishes once both crossed the line. Cinematics that freeze one player freeze both (tested in Fire Canyon, Lava Tube, Precursor Basin and parts of Mountain Pass). The gorge race timer shows in both views. During a cell cinematic on the zoomer or flut flut the other player is hidden and frozen, as on foot | `levels/racer_common`, `coop-racer-*` in `splitscreen.gc` | #16 |
| Flut flut | Boggy Swamp and Snowy Mountain: either player gets on at the pad and the other gets their own flut flut there. A player who dies on the flut flut comes back alone at the pad they got on at, on a new flut flut; a player who dies on foot while the other still rides comes back next to them, also on a flut flut. The section's power cell (Boggy Swamp's ledge, Snowy's switch) can only be taken once both players are within 30 m of it. Each player gets off on their own at a pad; the pad keeps its walls up (they keep the flut flut in its area) while either player rides, so a player who got off can only get a new flut flut there once both are off. Snowy's elevator up to the fort comes back down for a player below once nobody stands on it. The Rock Village flut flut is an npc (talks as usual) | `levels/flut_common`, `levels/snow/snow-flutflut-obs.gc`, `coop-flut-*` and `coop-racer-*` in `splitscreen.gc` | #17 |
| Jungle elevator | Whoever starts it at the temple top, the other player is put onto it and rides down to the plant boss too (the elevator carries both). It only runs once the temple top task is done, as in single player | `levels/jungle/jungle-elevator.gc`, `coop-bring-onto-platform`, `coop-move-other-rider` | #12 |
| Minigames | Fisherman, Billy's frogs, the jungle periscopes and the Misty cannon: the player who starts one plays it with their own pad, the game (its HUD, camera, questions, rewards) runs for them (`coop-pin-minigame`, also covering the host's child processes), and the other player stays free: they can watch or walk around, can't steer or quit the minigame, and their own talks or cutscenes don't pull the minigame player out of it. If player 2 plays and player 1 wanders past the leash, player 1 is brought back instead. The fisherman's "play again?" screen is full screen for a moment (a look-through camera). Both players touching the cannon or a periscope makes the last one to touch it the user (#31) | `levels/jungle/fisher.gc`, `levels/swamp/billy.gc`, `levels/jungle/jungle-mirrors.gc`, `levels/misty/mistycannon.gc`, `coop-player-in-minigame?` | #12, #21 |
| Fuel-cell pickup cutscene | Plays on the player who took the cell: the cell is pinned to that player for its victory (`coop-pin-to-player`), also when both touch it in the same frame | `engine/common-obs/collectables.gc`, `coop-pin-to-player` | #36 |
| Overlapping grabs | One grab pair is tracked. Once either player of it is no longer held, by whatever path (a release naming either player, a grabber ending a zoomer or flut flut grab with `'end-mode`, a cutscene ending on its own), the other one is released in the same tick, so nobody is left held. A second grab of a player who is already held is ignored by the game (as in single player), so its release also ends the first hold for both | `coop-grab-other-player`, `coop-grab-watch` | #30 |
| Shared player tuning objects | `*run-attack-mods*`, `*wade-surface*` and `*target-shadow-control*` are shared: one player's dash or wading depth can affect the other's, and a `shadow` event toggles both shadows | `engine/target/target.gc`, `engine/target/logic-target.gc` | #28 |
| Particle callbacks | Run in the display process (player 1's context): effects that track `*target*` (wall-smack sparks, first-person HUD particles) follow player 1 | `engine/target/target-part.gc`, `engine/target/target2.gc` | #26 |
| HUD particles | Each view only draws its own player's HUD particles (health, the periscope's binocular mask, the frog game's crosshair; `coop-add-hud-sprite-data`, owner from the launcher's process: player bit or pin); before, both players' HUD particles were drawn in both views. Screen particles of world processes stay in both views. Their callbacks still run in player 1's context | `engine/gfx/sprite/sprite.gc`, `engine/ui/hud-classes.gc` | #26 |
| Interactions with two players close by | The nearest player (0.25 m margin) uses an object; when both stand at the same spot it's whoever is a little closer to the object's origin | `coop-nearest-player-for`, `target-cpad-idx` | #31 |
| Two identical pads in single player | Upstream maps controllers to ports by model, so only one of two identical pads drives single player. Co-op assigns by device and is not affected | `game/system/hid/input_manager.cpp` `refresh_device_list` | upstream |
| Level streaming | Follows player 1 only; player 2 is kept within 60 m and pulled back if their level is unloaded | `splitscreen.gc` leash, `coop-on-level-leaving` | #23 |
| Warp gates | Whoever uses a gate picks the destination; both players jump into it and both come out of the gate at the destination, landing next to each other | `engine/common-obs/basebutton.gc` (warp-gate `use`), `target-coop-spawn` | #22 |
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
