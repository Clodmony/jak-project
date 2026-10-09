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
| an event is delivered | the receiver's owner, else the sender's owner, else unchanged | `send-event-function`, `goal_src/jak1/kernel/gstate.gc` |
| a view is rendered | the view's player | `coop-draw-player2-view` |
| `start` / `stop` | always player 1 (session operations) | `logic-target.gc` |

Ownership is a process-mask bit: `player2` (bit 25, `gkernel-h.gc`). `activate` copies the parent's
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
- Manager process `coop-manager` (default pool, once per tick): player position cache, split decision,
  player 2 respawn next to player 1 after `respawn-delay`, distance leash (`leash-distance`, 60 m).

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
player 1's camera after `update-time-of-day`.

Menus, pause and cutscenes (`movie?`) use one full-screen view of player 1 (`coop-want-split?`).

## Input

`coop::SlotAssigner` (`game/system/hid/coop_slots.h`, SDL-free, unit tested) maps devices to player
slots (pad ports). Controllers are tracked by SDL instance id, not GUID (identical pads share a GUID).
A device feeds at most one slot; assigning another player's device is rejected; a disconnected
slot keeps its claim and reports a failed pad read (GOAL sees neutral input). `InputManager` applies
changes on the graphics thread. GOAL API: `pc-coop-*` in `kernel-defs.gc`.

## Streaming and world simulation

Level loading, vis and the continue point stay driven by player 1 (camera position,
`level-distance`, `*load-boundary-target*`). Jak 1 holds two levels; player 2 can't make the game load
a third. Hence the leash. While co-op runs, actors are spawned and kept running regardless of player
1's vis and distance (`ps2-actor-vis?` treated as off, birth/pause distance 10000 m), without
changing the saved setting.

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
