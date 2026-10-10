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
| a process runs (trans, code, post, `run-logic?`) | the player that owns it; world processes use the closest player (4 m hysteresis) | `execute-process-tree`, `goal_src/jak1/kernel/gkernel.gc` |
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
  cache, player 2 respawn next to player 1 after `respawn-delay`, distance leash
  (`leash-distance`, 60 m).
- In-game options (all builds, so it works for a launcher mod): Options > Game Options > Misc Options
  > "Local co-op" (on/off), "Co-op split top/bottom", "Co-op assign devices", "Co-op: every ring for both" (race rings count only once both players flew through them; off by default), "Co-op: friendly fire" (on by default), "Co-op: tougher bosses" (bosses need 1.5x the hits, `coop-boss-hits`; off by default)
  (`goal_src/jak1/pc/progress-pc.gc`). Co-op is never saved as on: every session starts single player.
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
- each view is copied into its rect of the game framebuffer (`SplitscreenLayout.h`, 2+ px divider);
- the normal present path (pcrtc, brightness, blackout) runs once.
- occlusion vis is ignored on split frames (one vis buffer per level, written by one camera).

Per-view details: `was-drawn` is cleared only in view 0 (so it means "visible in any view"), light
interpolation ramps once per frame, each player's HUD models draw only in their view,
`level-distance`/vis/wind/look-through countdown are updated in view 0 only, and fog is copied from
player 1's camera after `update-time-of-day`. Things that would otherwise run once per view: the
death-dissolve timer (`draw-bones`, skipped when view 0 already drew the object), the TIE wind
springs in the C++ renderer (view 1 sends "paused"). Particle launchers aren't frustum culled while
co-op runs (one camera can't decide for both views). The sprite distortion tables are copied into
the chain instead of referenced, because the second camera regenerates them before the renderer
reads the frame. Both views share one framebuffer (`m_view_fbo`), freed 600 frames after the last
split frame.

Menus, pause and cutscenes (`movie?`) use one full-screen view of player 1 (`coop-want-split?`).

## Input

`coop::SlotAssigner` (`game/system/hid/coop_slots.h`, SDL-free, unit tested) maps devices to player
slots (pad ports). Controllers are tracked by SDL instance id, not GUID (identical pads share a GUID).
A device feeds at most one slot; assigning another player's device is rejected; a disconnected
slot keeps its claim, and only a newly connected pad of the same model refills it. A slot without a
connected device reports a disconnected pad (`scePadGetState`), so GOAL marks it invalid: neutral
input, and losing player 2's pad pauses. `InputManager` applies changes on the graphics thread; held
keyboard/mouse inputs are released on the old port before the mapping changes, keyboard command
binds (fullscreen, screenshot, ImGui) keep working when keyboard/mouse has no player, and the key
used to join is ignored until released. Enabling co-op auto-assigns devices unless the player chose
them. GOAL API: `pc-coop-*` in `kernel-defs.gc`.

## Streaming and world simulation

Level loading, vis and the continue point stay driven by player 1 (camera position,
`level-distance`, `*load-boundary-target*`). Jak 1 holds two levels; player 2 can't make the game load
a third. So:
- distance leash (60 m): player 2 is brought back next to player 1;
- residency guard: right before a level is discarded or hidden (`load-state update!`,
  `level.gc`), `coop-on-level-leaving` brings player 2 to player 1 if player 2 stands in it;
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
- Scripts that send the player to a checkpoint (`'continue`, Klaww's intro) go through
  `coop-continue`: player 1 runs `target-continue`, player 2 is despawned and comes back next to
  player 1.
- `process-grab?`/`process-release?` (cutscenes, talks, elevators) hold and release both players. The
  grab and the release can name different players (the grabber's `*target*` can change in between),
  so the pair is recorded and releasing either player releases both. Only one pair is tracked.
- Rumble from target code, eco and crates goes to the pad of the player involved (`coop-player-cpad`).
- Moving platforms reserve at least two rider slots.
- Pause: right before `determine-pause-mode`, player 2's Start/Select are merged into pad 0, and a
  player 2 controller loss injects a pause (`coop-merge-pause-buttons`).
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
  skipped), and Jak 2/3/X are not affected.
- Files other games compile stay byte-identical to upstream: everything under `goal_src/` outside
  `goal_src/jak1/`, plus the Jak 1 files Jak 2/3/X reuse (`pckernel-h`, `pckernel-common`,
  `pc-debug-common`).
- Every hand edit in a decompiled file carries `og:preserve-this` (upstream's CI then flags any
  regeneration that would drop it).
- Shared C++ runtime changes only take effect when Jak 1 turns co-op on.
- Co-op code writes files through `*pc-settings-folder*`, not `*pc-user-dir-base-path*` (the latter
  ignores the launcher's `--config-path`).

Tools:
- `scripts/splitscreen/check_upstream_compat.py`: checks the file rules against the merge base with
  upstream and lists the shared C++ files to review. Run it before every push.
- `scripts/splitscreen/sync_upstream.sh`: merges `upstream/master`, builds, compiles all Jak 1 code,
  runs `test.sh` (includes the Jak 2/3/X compile and type checks) and the compatibility check.
  `--preview` only lists conflicting files.

Work items are GitHub issues on the fork, not files in this folder.
