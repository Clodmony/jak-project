# Jak 1 local split-screen co-op: architecture

> Written with AI assistance (AI-assisted). Paths and line numbers were verified against upstream
> commit `efb21c3e` (open-goal/jak-project, 2026-09-30) plus the commits on this branch.

## Requirements this design satisfies

- One `gk` process, one window, one world simulation that advances once per tick.
- Two real `target` processes running the unmodified player code.
- Two cameras, two viewports in one window, one present per frame.
- Single player is unchanged when co-op is off: every hook is a no-op unless co-op was started.

## Core idea: player contexts

The engine has one set of "player globals": `*target*`, `*camera*`, `*camera-combiner*`,
`*math-camera*`, `*hud-parts*`, `*edge-grab-info*`, `*camera-smush-control*`,
`*save-camera-inv-rot*`, `last-try-to-look-at-data`, `*camera-base-mode*`, and the pools that player
processes spawn into. About 1,470 references to `*target*` alone assume "the player".

Instead of rewriting those references, co-op keeps one copy of these values per player and swaps
them as a unit (`coop-switch-context`, `goal_src/jak1/pc/features/splitscreen.gc`). Which context is
active is decided:

| When | Context | Where |
| --- | --- | --- |
| a process runs (trans, code, post, `run-logic?`) | the player that owns it; world processes use the closest player (0.25 m hysteresis), measured from their body or, for world code without a body that a level actor placed (tutorial cameras, task triggers), from the actor's position | `execute-process-tree`, `goal_src/jak1/kernel/gkernel.gc` |
| an event is delivered | the receiver's owner, else the sender's owner, else unchanged. A `touch`/`attack` from a player also latches the world process to that player (until the other player is 4 m closer) | `send-event-function`, `goal_src/jak1/kernel/gstate.gc` |
| a view is rendered | the view's player | `coop-draw-player2-view` |
| `start` / `stop` | always player 1 (session operations) | `logic-target.gc` |

Ownership is a process-mask bit: `player2` (bit 25, `gkernel-h.gc`; `coop-p1`, bit 27, marks what
player 1 spawns into shared pools, e.g. their first-person HUD). `activate` copies the parent's
mask into new processes, so player 2's daxter, HUD and cameras inherit it. Player 1's processes are
recognised by the existing `target`/`sidekick`/`camera` bits. The kernel hooks are function
pointers that stay `#f` until `coop-start`, so the single-player kernel path only pays one `#f` check.

Consequences, by design:
- Target, camera and HUD code runs unchanged for player 2 (it sees its own `*target*`, `*camera*`).
- Enemies and objects target the closest player through their existing `*target*` code.
- Collectables credit whoever triggered them: the `touch` event comes from that player's target.
- Player 2's steering uses player 2's camera (`matrix-local->world` reads `*math-camera*`).

## Player 2

- Own process-tree nodes `*coop-p2-target-pool*` and `*coop-p2-camera-pool*`, linked into
  `*active-pool*` directly after `*target-pool*` and `*camera-pool*`. Update order stays
  entities -> targets -> cameras -> display.
- Own fixed dead pools (target, daxter, camera, camera master), so player 1's pools are untouched.
- Spawned through the normal `init-target` with a player-2 branch: no `set-continue!`, pad
  `*coop* p2-pad`, and the new state `target-coop-spawn` instead of `target-continue` (which rewrites
  load state, the continue point and the camera).
- Own full camera rig (`cam-start #f` in player 2's context). `cam-stop` only kills the current
  player's rig while co-op runs.
- Manager process `coop-manager` (default pool, once per frame, also while paused so menus get a
  single full-screen view): split decision and listener; in game mode also the player position
  cache, player 2's first spawn next to player 1 after `respawn-delay`, the players' level pairs
  (`coop-wants-update`), the distance leash (`leash-distance`, 1000 m, a safety net since #69).
  A player who dies while the other plays on comes back next to the other player, or at the last
  checkpoint when that is nearer to where they died (`target-coop-respawn`; since #110, four level
  slots: the players can be levels apart).
- Title screen (all builds): "Local co-op" > "New co-op game" / "Load co-op game" (`*coop-title-options*`,
  screen `coop-title`, `progress-pc.gc`). Choosing one opens the join screen; its "Start" starts co-op,
  then the normal new game slot choice or load screen follows, so their slots are the co-op ones.
- Join screen (`coop-join`, `*coop-join-options*`): shown before co-op starts, from the title menu and
  from Misc Options > "Local co-op" on. It turns co-op input on with player 1 keeping the device that
  drives port 0 (else keyboard/mouse) and player 2 joining (`pc-coop-prepare-join!`). Each player's
  device is shown by name (`pc-coop-slot-name`, SDL's controller name) or "keyboard and mouse"; "Start"
  is locked until both have a device; "Swap players" swaps the two devices (`pc-coop-swap-players!`);
  Back leaves co-op off and turns co-op input off again (also when the menu closes on that screen).
  Both players' buttons work the join screen (`*coop-join-screen?*` in `coop-merge-menu-buttons`). Back on the title menu (or
  "Quit game") co-op stops again; on the title screen itself no player 2 is spawned and nothing is
  split (`coop-at-title?`; the game's end leads there with co-op still on).
- In-game options (all builds, so it works for a launcher mod): Options > Game Options > Misc Options
  > "Local co-op" (on/off), "Co-op split top/bottom", "Co-op assign devices", "Co-op: every ring for both" (race rings count only once both players flew through them; off by default), "Co-op: friendly fire" (on by default), "Co-op: tougher bosses" (bosses need 1.5x the hits, `coop-boss-hits`; off by default)
  (`goal_src/jak1/pc/progress-pc.gc`). Co-op is never saved as on: every session starts single player.
  The layout and the three co-op options are remembered in `coop-settings.gc` (see "Saves and settings").
- Debug menu "Local Co-op" (`goal_src/jak1/pc/debug/coop-menu.gc`, debug builds only): start/stop,
  layout, device join, respawn, leash, info overlay.
- Processes a player spawns into shared pools (player 2's first-person HUD in `*dproc*`) are marked as
  that player's (`coop-adopt`).

## Rendering

Rendering a second view must not advance the simulation. `real-main-draw-hook` mixes drawing with
simulation (touching events, `actors-update`, time of day, ocean waves, shadow buffer swap, eye
blink), so player 2's view does not call it. Instead:

```
display-loop (main.gc)
  update-camera                    player 1, view aspect on split frames
  *draw-hook*                      player 1's view + all once-per-tick work      -> bucket group 0
  coop-draw-player2-view           player 2's context: update-camera,
                                   coop-draw-view-only (render-only subset)     -> bucket group 1
  ... menus, debug text, depth cue (group 0) ...
  swap-display                     one chain, one send, one vsync
```

One DMA chain per frame, with one group of 70 buckets per view
(`[CALL default-regs][group 0][CALL default-regs][group 1][FLUSHE][END]`,
`coop-frame-start`/`coop-frame-finish` in `splitscreen-h.gc`). Groups are built in chain order
because GOAL's texture residency tracking assumes the renderer replays uploads in build order.
Every DMA insert reads `(-> (current-frame) bucket-group)`; switching that field per view (and per
context during the tick, for HUD text) routes all renderers.

C++ (`OpenGLRenderer::dispatch_buckets`, Jak 1 path only):
- `count_jak1_views` peeks the chain for a second `CALL` header.
- each view renders at the origin of its own framebuffer (`m_view_fbos`), so the GS scissor
  emulation, depth cue, distort sprites and stencil shadows stay inside the view;
- each view is copied into its rect of the game framebuffer (`SplitscreenLayout.h`); with MSAA it
  is resolved straight into its rect of the resolve buffer instead, and pcrtc shows that buffer
  without its own resolve (`m_split_resolved`): copying the multisampled views into the
  multisampled game framebuffer and resolving it again cost a weak GPU more than a whole
  single-player frame at MSAA 16 (#14). The divider between the views (4+ px) is half blue next to
  player 1's view and half orange next to player 2's (`divider_rects`, `kPlayerColors`);
- the normal present path (pcrtc, brightness, blackout) runs once.
- occlusion culling works per view: each view's buckets carry the vis of that view's camera.

Per-view details: `was-drawn` is cleared only in view 0 (so it means "visible in any view"), light
interpolation ramps once per frame, each player's HUD models draw only in their view,
`level-distance`/wind/look-through countdown are updated in view 0 only, and fog is copied from
player 1's camera after `update-time-of-day`. Occlusion vis is kept per view: `update-visible` writes
one camera's vis into the level (vis-bits, bsp leaf, the vis strings loaded, a pending vis string
load), so player 2's pass trades in its own copy of that state per level slot (`coop-view-vis-enter`,
`-exit`; its vis string loads go to its own buffer, `coop-view-vis-buffer` in `update-vis!`) and
updates it for player 2's camera. Actor LOD: on a split frame each view draws the LOD for its own
camera (`dma-add-process-drawable`), never finer than the LOD the joints were computed for, and the
actor keeps the finest LOD of the views for its own logic. Things that would otherwise run once per view: the
death-dissolve timer (`draw-bones`, skipped when view 0 already drew the object), the TIE wind
springs in the C++ renderer (view 1 sends "paused"). Particle launchers aren't frustum culled while
co-op runs (one camera can't decide for both views). The sprite distortion tables are copied into
the chain instead of referenced, because the second camera regenerates them before the renderer
reads the frame. Both views share one framebuffer (`m_view_fbo`), freed 600 frames after the last
split frame.

Menus, pause and cutscenes (`movie?`) use one full-screen view of player 1 (`coop-want-split?`).

Telling the players apart: on split frames each view shows a small "P1" (cyan) or "P2" (orange) in
its bottom right corner, the corner the game's HUD uses least (`coop-draw-player-labels`, drawn
in each player's context so it lands in their view's buckets). The divider uses the same colours.

## Input

`coop::SlotAssigner` (`game/system/hid/coop_slots.h`, SDL-free, unit tested) maps devices to player
slots (pad ports). Controllers are tracked by SDL instance id, not GUID (identical pads share a GUID).
A device feeds at most one slot; assigning another player's device is rejected; a disconnected
slot keeps its claim, and only a newly connected pad of the same model refills it. A slot without a
connected device reports a disconnected pad (`scePadGetState`), so GOAL marks it invalid: neutral
input, and losing player 2's pad pauses. `InputManager` applies changes on the graphics thread, and rebuilds the controller list there (hotplug, co-op turned off) while holding the co-op lock that the game thread's `pc-coop-*` calls take; held
keyboard/mouse inputs are released on the old port before the mapping changes, keyboard command
binds (fullscreen, screenshot, ImGui) keep working when keyboard/mouse has no player, and the key
used to join is ignored until released. Enabling co-op auto-assigns devices unless the player chose
them (the join screen counts as choosing: `SlotAssigner::prepare_join`, `swap_slots`). GOAL API: `pc-coop-*` in `kernel-defs.gc`.

Camera controls are per player (#41). The right stick macros in `pad.gc` (`analog-input-*-first`,
`-third`) and `cam-dist-analog-input` read the inversion of the player whose context runs
(`coop-camera-inverted?`: player 1's are the `*pc-settings*` fields, player 2's are in
`*coop-camera*`) and scale the result by that player's camera speed (`coop-camera-speed`, 50-200 %,
100 = the original game). The first line of Camera Options ("CAMERA OPTIONS: PLAYER 1/2", option type
`coop-player`) picks whose controls the page edits; `coop-camera-menu-sync` points the toggles and the
"Camera speed" slider at that player's settings every frame the page is shown, and "Restore defaults"
resets only that player (`coop-reset-camera`). The global "Analog sensitivity" (C++ `axis_scale`,
both sticks of every pad) stays shared.

## Streaming and world simulation

Jak 1 held two levels; co-op holds four (#110), so each player can stand in their own level and
cross a border at the same time (a player needs at most two: the one they are in and the next one
while crossing). Load boundaries (`load-boundary-data.gc`) switch them as the camera or the player
crosses: `(load a b)`, `(display a on/off)`, `(vis a)`, `(checkpt name)`. With co-op both players
cross them (#69):
- player 1's crossings use the original points in `*load-boundary-target*`; player 2's camera and
  position are checked in a second pass over the boundary list (`coop-check-boundaries-p2`, which
  lends player 2's points to `check-boundary`);
- a move of more than 10 m in one frame (respawn, warp) is not a crossing (`coop-boundary-skip-jumps`);
- every crossing command goes through `coop-boundary-command-ok?`. A load `(load a b)` is the crossing
  player's own pair of levels (`*coop-wants*`); the game's wants become the union of both players'
  pairs, the crossing player's first (`coop-want-levels`, the `want-levels` hook; at most four names,
  so nobody's level goes away for the other player's loads). A script's load (boats, warp gates,
  cutscenes take both players along) sets both pairs. A player who got into a level without crossing
  a boundary (respawned elsewhere, teleported) gets the levels whose boxes hold them as their pair
  (`coop-wants-update`, once per frame). A pair the player's own crossing set stays while it holds
  one of those levels (the boundary named the levels needed there; a teleport, seen by
  `coop-boundary-skip-jumps`, ends that). The pairs are backed up and restored with the load state
  around a cutscene's or checkpoint's commands (`coop-wants-backup`/`-restore`), and a player's
  crossing while a backup is held (an ambient's spooled animation, the sage's lines at his hut) goes
  into the backup too (`coop-crossing-to-backup`), so the restore doesn't switch off a level the
  other player walked into; a checkpoint reload
  gives both players the checkpoint's two levels (`coop-wants-reset`); `coop-stop` leaves player 1's
  pair as the wants. Turning off the display of the other player's level is ignored. Vis
  and checkpoints follow player 1 only;
- the DGO loader, the login state and the loading heap are global, so levels load one at a time:
  with four wants two can be missing at once, and `load-state update!` adds the next one only when no
  slot is loading or logging in (`level-load-in-progress?`; the original never had two missing wants);
- the continue point, `level-distance`, vis, music, ambients and the sound listener stay with player 1;
- sky, fog and lighting blend two levels, as in the original (`update-time-of-day`): the two slots
  nearest player 1's camera, each level keeping its side of the blend while it stays in the pair
  (`blend-slot-a/b`). Only a displayed level with a sky makes sky textures, so when neither of the
  two nearest is one (two loaded neighbours nearer than the displayed level), the nearest displayed
  level with a sky replaces the farther of the two (#142; before, no sky was drawn in either view).
So two players can be anywhere in the loaded levels, each in their own. Safety nets:
- residency guard: right before a level is discarded or hidden (`load-state update!`, `level.gc`),
  `coop-on-level-leaving` brings player 2 to player 1 if player 2 stands in it (scripts like the
  fisherman's boat or a warp gate still switch levels for both);
- distance leash, now 1000 m (`leash-distance`);
- player 2's current level (endless-fall height, level-enter events) comes from its own position
  (`level-get-target-inside`), not from the continue point or player 1's camera;
- `level-activate`/`level-deactivate` events reach both players' cameras and targets.

While co-op runs, actors are spawned and kept running regardless of player 1's vis and distance:
the same behaviour as the existing PC "force actors" option, without changing the saved setting.

## Death, interactions, pause

- `target-death`: if the other player is in play, skip the world freeze, the streamed death movie and
  `initialize! 'dead`; go to `target-coop-respawn` (hidden, no collision, waits `respawn-delay`, then
  respawns at the other player's last safe ground with full health). If both are down, the original
  single checkpoint reload runs once. If co-op is stopped while a player waits to respawn, that
  player finishes the original death (checkpoint reload).
- A death on a zoomer or flut flut is noted (`coop-racer-note-death`) so the respawn puts the player
  back on one. The note belongs to that target: `init-target` drops it (`coop-racer-forget-death`), so
  a reload after both died doesn't leave it for a later death in another level. A zoomer remount with
  no zoomer in the loaded levels keeps the player on foot: the zoomer states live in the zoomer
  levels' heaps and are garbage once such a level is replaced.
- Players collide and can hit each other (`coop-contact-update`, once per tick). While both are in
  play and free (not held, on a zoomer, in a minigame, spawning, warping, hidden for a cinematic or
  frozen), the `target` kind is in the collide-with of each player's root and body spheres: the
  players are solid to each other (blocking, standing on a head), and their overlaps reach each
  other's attack handlers. It only turns on while their bodies don't overlap (after a respawn or a
  cutscene), and turns off when one is put deep inside the other (a script's teleport). A player walking into the other one adds up to 4 m/s to the other's own movement
  (pushing; walls and edges still stop them). The three collide-cache fills skip the probing
  process in the player list (`collide-cache.gc`): many target probes pass `proc #f` and would
  otherwise hit their own body (stuck ducking, edge grabs).
- Friendly fire: `target-send-attack` and the touch-tracker (red eco flop, flut flut flop) send an
  attack meant for the other player to `coop-player-attack`, which hits them like an enemy
  (`'generic`, 2 m back, 1.5 m up, one point of health; a knocked-out player respawns next to the
  other) and returns `'die`, so a punch stops at the victim. Attacking bodies have the higher
  collide offense and pass through softer ones, so collision stays off for 0.6 s after a hit (it
  would block the knockback). Option "Co-op: friendly fire" (`*coop* friendly-fire?`, on by
  default) turns the hits off; collision stays. Player 2's attack ids start at `#x40000000`, so
  enemies that de-duplicate hits by id don't drop one player's hit; hits between players carry no id.
- A boss eating a player (Dark Eco Plant) runs for that player until the scene ends (`coop-boss-eats`,
  a pin that doesn't cover the boss's children, `coop-pin-alone`): the scene's release reaches the
  eaten player. Its othercam is pinned the same way; an othercam pinned alone while the other
  player is in play adds no movie or process-mask setting and its look-through applies only to
  that player's view (`coop-solo-cam-player`). A respawn also restores the player's root joint
  (the eat scene drives it from the plant's joint) and daxter's matrix mode.
- Any other killer is pinned to the dying player the same way until they respawn
  (`coop-death-pin-attacker`, from `target-death`): world processes follow the nearest player in
  play, a dying player isn't one, and a shark's `'end-mode` (which ends its death) would otherwise
  reach the other player and leave the eaten one in `target-death`.
- World code that checks or steers "the player" once per frame can run per player:
  `coop-for-each-player-context` switches to each player in play and back (Gol and Maia's camera
  control, the eye beam and the red shot rings).
- Scripts that send the player to a checkpoint (`'continue`, Klaww's intro) go through
  `coop-continue`: player 1 runs `target-continue`, player 2 is despawned and comes back next to
  player 1.
- `process-grab?`/`process-release?` (cutscenes, talks, elevators) hold and release both players. The
  grab and the release can name different players (the grabber's `*target*` can change in between),
  so the pair is recorded and releasing either player releases both. Only one pair is tracked.
- The Volcanic Crater gondola: its origin stays at the bottom while the car moves, so its idle loop
  checks each player at the car (`coop-for-each-player-context`) and either can start it; the
  gondola is pinned to the player who pressed for the ride, and at the other end the other player
  is put next to them (`coop-put-other-player-near`).
- Lost Precursor City's exit chamber: its origin also stays at the bottom. The button's press pins
  the chamber to the player at the button and puts the other player next to them; while the chamber
  holds its rider in place during the ride, the other one is held 1.5 m beside
  (`coop-carry-other-player`). Its door at the top stays open while either player is near.
- A lightning mole's dive scene freezes the nearest player and wakes `*target*` at its end; the mole
  moves into the hole meanwhile, so the other player can become the nearer one. The dive pins the
  mole to the frozen player (`lightning-mole-dive`), so the end wakes the same player.
- An NPC scene started by an event (`been-kicked`, e.g. the Citadel sages' scenes sent by their fuel
  cell) waits for the previous scene's camera to end before grabbing the player: a held player
  refuses a second grab, so grabbing first could leave both players held for good.
- Rumble goes to the pad of the player it is about: target code, crates and orbs (`coop-player-cpad`); eco pickups, the zoomer and the flut flut use the player's own pad (`control cpad`), yellow and blue eco shots the shooter's (`projectile-owner-cpad`), the jungle bouncer the player who bounced.
- Moving platforms reserve at least two rider slots.
- Pause: right before `determine-pause-mode`, player 2's Start/Select are merged into pad 0, and a
  player 2 controller loss injects a pause (`coop-merge-pause-buttons`; player 1's loss pauses as in
  single player). While a player's controller is disconnected the screen says so ("Player 2 /
  controller disconnected / connect it again to play on"); once it is back, "controller connected"
  shows for 3 s, and with "press start to continue" for as long as the game is still paused
  (`coop-pad-messages`, in that player's view when split). Keyboard/mouse and a slot that never had
  a device get no message.
- Pad 1 debug/cheat binds (Billy skip, plant boss skip, lightning mole, balloon lurker steering,
  retail debug cheats) are disabled while co-op runs, since pad 1 is player 2.

## Saves and settings

- Co-op saves live in their own folder, `saves/coop/` (`mc_set_namespace`, `kmemcard.cpp`;
  GOAL `pc-set-memcard-namespace!`). `coop-start` switches to it and `coop-stop` back. A save or load
  that is running at the switch finishes in the old folder first. Any auto-save process is stopped
  and auto-save stays off until the player picks a slot, because the remembered slot belongs to the
  other folder.
- `coop-start` saves `*ACTOR-bank*` and `coop-stop` restores it, so single player doesn't keep the
  co-op actor distances.
- Nothing is added to `pc-settings.gc` (other builds sharing the folder would reject unknown keys).
  The split layout, the co-op options (every ring for both, friendly fire, tougher bosses) and the
  camera controls per player (player 2's inversions, both players' camera speed) are kept in
  `coop-settings.gc` in the same folder (`coop-save-settings` when one changes in the menu,
  `coop-load-settings` at boot). Its reader skips keys it doesn't know (a newer build's file) and a
  broken file only leaves the defaults. Whether co-op is on is never kept.

## Source map (verified)

| Area | Symbols | Files |
| --- | --- | --- |
| Player spawn | `start`, `stop`, `init-target`, `target-continue` | `engine/target/logic-target.gc:1273-1290`, `engine/target/target-death.gc:34` |
| Player state | `target`, `control-info`, `fact-info-target` | `engine/target/target-h.gc:17`, `engine/collide/collide-target-h.gc:26`, `engine/game/fact-h.gc:107` |
| Steering basis | `read-pad`, `matrix-local->world` | `engine/target/logic-target.gc:271`, `engine/camera/cam-interface.gc:19` |
| Input | `service-cpads`, `*cpad-list*`, `scePadRead`, `InputManager` | `engine/ps2/pad.gc:272`, `game/sce/libpad.cpp:62`, `game/system/hid/input_manager.cpp` |
| Camera | `cam-start`/`cam-stop`, `camera-master`, `camera-combiner`, `update-camera`, `update-math-camera` | `engine/camera/cam-start.gc`, `engine/camera/cam-master.gc`, `engine/camera/cam-update.gc:218`, `engine/gfx/math-camera.gc:54` |
| Scheduling | `kernel-dispatcher`, `execute-process-tree`, pools | `kernel/gkernel.gc:1543-1700`, `kernel/gkernel.gc:2471-2496` |
| Events | `send-event-function` | `kernel/gstate.gc:442` |
| Frame | `display-loop`, `display-frame-start/finish`, `display-sync` | `engine/game/main.gc:351`, `engine/draw/drawable.gc:969-1251` |
| Drawing | `real-main-draw-hook`, `dma-add-process-drawable`, `bones-mtx-calc-execute` | `engine/draw/drawable.gc:740,421`, `engine/gfx/foreground/bones.gc:469` |
| Renderer | `OpenGLRenderer::render`, `dispatch_buckets_jak1`, `do_pcrtc_effects` | `game/graphics/opengl_renderer/OpenGLRenderer.cpp` |
| Present | `render_game_frame`, `gl_send_chain`, `gl_vsync` | `game/graphics/pipelines/opengl.cpp:468,778,749` |
| HUD | `activate-hud`, `*hud-parts*`, `dma-add-process-drawable-hud` | `engine/ui/hud-classes.gc:1416`, `engine/ui/hud-h.gc:118`, `engine/draw/drawable.gc:637` |
| Pause | `toggle-pause`, `determine-pause-mode` | `engine/game/main.gc:141`, `engine/draw/drawable.gc:1151` |
| Death | `target-death`, `initialize!` | `engine/target/target-death.gc:657`, `engine/game/game-info.gc:141` |
| Streaming | `level-update`, `load-boundary`, `actors-update`, `run-logic?` | `engine/level/level.gc:1188`, `engine/level/load-boundary.gc`, `engine/entity/entity.gc:1005-1016` |
| Collectables | `pickup-collectable!` | `engine/game/game-info.gc:383`, `engine/common-obs/collectables.gc` |
| Audio listener | `ear-trans`, `swap-sound-buffers` | `engine/sound/gsound.gc:588`, `engine/game/main.gc:552` |

### State classification

- Shared world: entities, enemies, platforms, particles (`process-particles`), ocean waves, time of
  day, levels and vis, `*game-info*` (orbs, cells, flies, lives, tasks, continue point).
- Per player: target, daxter, health/eco (`fact-info-target`), camera rig, HUD processes,
  edge-grab state, camera shake, pad.
- Per view: math camera (projection, frustum, aspect), bucket group, framebuffer, tie/shrub work
  constants, was-drawn (merged), HUD models.
- Session: pause/master mode, settings, device assignment, split layout, audio listener (player 1),
  level streaming (player 1).

## Staying an add-on

OpenGOAL has no plugin loader, so the co-op ships as a launcher mod: a full build installed next to
the official Jak 1 with its own settings and saves (MOD.md). The code is a change set on top of
upstream OpenGOAL, never a diverging copy:

- Co-op code lives in new files (`goal_src/jak1/pc/features/splitscreen*.gc`,
  `goal_src/jak1/pc/debug/coop-menu.gc`, `game/system/hid/coop_slots.*`,
  `game/graphics/opengl_renderer/SplitscreenLayout.h`). Edits to upstream files are short hooks.
- With co-op off, Jak 1 behaves like upstream (the kernel hooks are `#f`, every co-op branch is
  skipped), apart from the four level slots (#110, see the review below), and Jak 2/3/X are not
  affected.
- Files other games compile stay byte-identical to upstream: everything under `goal_src/` outside
  `goal_src/jak1/`, plus the Jak 1 files Jak 2/3/X reuse (`pckernel-h`, `pckernel-common`,
  `pc-debug-common`).
- Every hand edit in a decompiled file carries `og:preserve-this` (upstream's CI then flags any
  regeneration that would drop it).
- Shared C++ runtime files: compiled for every game, so co-op code there only runs once Jak 1 turns
  co-op on. The exceptions (Jak 1's four level slots, three bug fixes) are listed in the review
  below.
- Co-op code writes files through `*pc-settings-folder*`, not `*pc-user-dir-base-path*` (the latter
  ignores the launcher's `--config-path`).


Tools:
- `scripts/splitscreen/check_upstream_compat.py`: checks the file rules against the merge base with
  upstream and lists the shared C++ files to review. Run it before every push.
- `scripts/splitscreen/sync_upstream.sh`: merges `upstream/master`, builds, compiles all Jak 1 code,
  runs `test.sh` (includes the Jak 2/3/X compile and type checks) and the compatibility check.
  `--preview` only lists conflicting files.
- `.github/workflows/upstream-check.yaml` ("Upstream Check", Mondays and on demand): the same merge,
  build, all-code compile, `test.sh` and compatibility check on GitHub against the latest upstream
  master, without pushing anything. A red run lists the conflicting files in its summary. GitHub
  pauses scheduled workflows after 60 days without repository activity.

Work items are GitHub issues on the fork, not files in this folder.

### Shared C++ runtime review (#6)

`check_upstream_compat.py` lists these files. Each change, what it does when co-op is off, and why
an always-on part stays:

| Files | Change | Without co-op | Verdict |
| --- | --- | --- | --- |
| `common/goal_constants.h`, `game/kernel/jak1/kmachine.cpp` | `jak1::LEVEL_MAX` 2 -> 4; Jak 1's global heap ends at 88 MB (the debug heap is 8 MB smaller); `__pc-set-levels` takes one name per slot; `__pc-get-bucket-draw-order` | Jak 1 always reserves four level heaps. Jak 2/3/X keep their own `LEVEL_MAX` and heaps | Always on in Jak 1, needed for the four level slots (#110) |
| `game/graphics/opengl_renderer/buckets.h`, `OpenGLRenderer.cpp/.h` | Jak 1 bucket set per level slot, drawn in `kBucketDrawOrder`; a frame with more than one bucket group is drawn as split views | Jak 1: a one-view frame takes the old path; per frame the renderer reads a few DMA tags to count the views, and the split framebuffer is freed 600 frames after the last split frame. Jak 2/3: `do_pcrtc_effects` tests one flag that only Jak 1 split frames set | Always on in Jak 1 (bucket layout, #110); split views opt-in |
| `game/mips2c/jak1_functions/sparticle_launcher.cpp` | particles spawned in level slots 3 and 4 get their level flag | Jak 1 only: two more heap range tests per launched particle | Always on in Jak 1 (#110) |
| `game/overlord/jak1/srpc.cpp` | unloading a sound bank clears its name | Jak 1 only. Upstream kept the name, so loading the same bank again was skipped (silent level) | Bug fix, always on; four slots unload and reload banks more often |
| `game/system/hid/devices/game_controller.cpp/.h` | pressure axis events only for the controller that sent them | All games. Every mapped controller sees every SDL event; upstream applied one PS3-style controller's pressure axes to the other's port too. With one controller nothing changes | Bug fix, always on |
| `game/main.cpp`, `game/runtime.cpp`, `game/common/game_common_types.h` | `gk --port` sets the listener port | All games. Upstream declared `--port` as a flag and the listener used a fixed port; without `--port` the port is the same as before. The local test tools use it to run several games | Bug fix, always on |
| `common/util/FileUtil.cpp/.h` | the repository is also found under another folder name: the closest folder above the program with `goal_src/` and `decompiler/config/` | All games and tools, only where upstream found no path (installed games use their data folder before this). This fork's clones and CI checkouts are named `opengoal-coop` | Bug fix, always on |
| `game/kernel/common/kmachine.cpp` | `pc-coop-*` and `pc-set-splitscreen-layout!` | Defined for every game, called only by Jak 1's co-op code | Opt-in |
| `game/kernel/common/kmemcard.cpp/.h`, `game/kernel/jak1/kscheme.cpp` | save subfolder (`pc-set-memcard-namespace!`, defined for Jak 1) | Empty by default, so saves go where upstream puts them; `MC_run` tests one flag | Opt-in |
| `game/graphics/gfx.h`, `game/graphics/pipelines/opengl.cpp`, `SplitscreenLayout.h` | split layout setting handed to the renderer | Only read for frames with more than one view | Opt-in |
| `game/system/hid/input_manager.cpp/.h`, `coop_slots.cpp/.h`, `devices/keyboard.cpp/.h`, `game/CMakeLists.txt` | device to player slot assignment | Two atomic flag tests per SDL event; a controller hotplug also copies the controller list for co-op (under its lock). Keyboard/mouse events go to the same port as before (port 0 always exists), `set_controller_for_port` and `is_keyboard_enabled` are unchanged | Opt-in |
| `game/sce/libpad.cpp` | in co-op a port without a device reads as a disconnected pad | Every port reads as a connected pad, as upstream (scenario `solo-runtime`) | Opt-in |

The compatibility check also fails on line ending or whitespace-only changes in these files (rule 5):
`FileUtil.cpp/.h` had lost upstream's CRLF line endings, which made the whole file one diff.
