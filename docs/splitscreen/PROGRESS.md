# Jak 1 local split-screen co-op: progress

> Written with AI assistance (AI-assisted). Newest first.

## 2026-10-10: in-game testing with two virtual pads

Tested in the running game with two virtual gamepads (`scripts/splitscreen/vpad.py`) and the REPL;
results per step in TESTING.md, including a frame-time measurement.

Fixed:
- Crash on a later death/respawn: HUD particles and icons were `'static`, shared by both players'
  HUDs; one player's HUD dying left the other drawing through freed memory. Now per HUD, moved
  in `relocate`.
- A player held during a conversation/cutscene/elevator was never released: the pair's handles
  were stored in symbols (32 bits) and lost their pid. Also moved the respawn timer into a structure.
- Player 2 could not use the pause menu (it reads pad 0): player 2's buttons count in menus.
- Talking, boarding, mounting, warp gates, cannon, periscope, fisherman, yes/no questions read the pad
  of the player the object serves (`target-cpad-idx`), not pad 0. Player 2 can talk to NPCs.
- Player 2 swims: water volumes track both players (side table, decompiled layout unchanged).
- HUD and 2d drawn with the view's aspect ratio in split frames (were squeezed/stretched).
- The pad that is player 1 stays player 1 when co-op starts.
- Nearest-player margin 4 m -> 0.25 m: the closer player could not board the boat.
- German text for the co-op menu entries.

Not tested yet: keyboard steps (5, 27, 28), elevator (22), fisherman minigame (29), stopping co-op
during a respawn (20), a non-debug boot driven end to end (21).

Next: the untested steps above, then the launcher mod packaging.

## 2026-10-10: first runtime session (PAL disc, keyboard only, no controllers)

First time the game ran with co-op. Linux (CachyOS), 1920x1080 window, debug boot (`-boot -fakeiso
-debug`), Jak 1 PAL. Players were moved, damaged and killed through the REPL because no
controllers were connected, so input-driven steps are still open. Results per step are in
TESTING.md.

Works in the running game: split screen in both layouts, two real players, independent cameras,
per-view culling, per-player health HUD inside each view, one sim tick per frame with two views
(sim ticks = view-2 passes = integral frames; game clock at real-time speed), shared orbs and power
cells (one reward when both players touch the same orb in the same frame), player 2 death and
respawn without a world reset, both-down checkpoint reload, 60 m leash, full-screen pause/progress
menu, full-screen power cell cinematic with both views restored afterwards.

Fixed from this session:
- Co-op start paused the game at once when player 2 had no device: the "player 2 controller
  lost" pause fired on the frame pad 1 went from the single-player "always connected" to the
  co-op "no device". It now pauses only when a device assigned to player 2 loses its connection.
- Player 2 spawned exactly inside player 1. Spawns and respawns now step 1.5 m to the side (or
  behind), checked with collision probes for a clear path and ground at the same height; falls back
  to the old spot.
- The idle player stood in the other player's cinematic (power cell victory). During a cinematic
  about one player the other one and their daxter are hidden, and shown again afterwards (also when
  co-op is stopped mid-cinematic).
- Removed `coop-settings frame-views`, a stats field nothing wrote (always 0).

Confirmed known gap: player 2 does not swim (stands on the sea floor in `target-stance`).


## 2026-10-09: saves, in-game toggle, review fixes (compiles, not playtested)

- Co-op saves in their own folder `saves/coop/`; auto-save stays off until a slot is picked.
- In-game options (no debug build needed, so a launcher mod can use it): Misc Options >
  "Local co-op", "Co-op split top/bottom", "Co-op assign devices".
- From an adversarial code review (four reviewers: single-player regressions, context switching,
  GOAL rendering, C++ rendering):
  - grab/release pairs: releasing either player releases both (elevator started by player 2 no
    longer leaves a player stuck);
  - a world process touched/attacked by a player stays with that player (fuel-cell victory plays
    on the collector);
  - the manager also runs while paused, so menus are full screen instead of in player 1's half;
  - player 2's first-person HUD belongs to player 2;
  - target rumble goes to the right pad;
  - stopping co-op while a player waits to respawn no longer leaves an invisible Jak;
  - `*ACTOR-bank*` is restored by "Stop co-op";
  - decompiler reference for the two new target states.
- Second round from the same review (verified findings):
  - input: an unassigned/disconnected slot reports a disconnected pad (it kept its last input
    before), held keys are released when the mapping changes (stuck stick), keyboard hotkeys work
    with two pads, the join key doesn't leak into gameplay, an idle identical pad can't take over a
    disconnected slot, enabling co-op auto-assigns unless devices were chosen;
  - rendering: death dissolve and TIE wind advance once per frame, particles aren't culled against
    one player's camera, distortion tables per view, one shared view framebuffer that is freed after
    split screen ends, small-profiler times add up both views;
  - gameplay: cutscene input freeze only applies to player 2 (fixes a fisherman minigame soft-lock),
    respawn spots use the player's position when the safe-ground point is stale (fixes a leash
    respawn loop after boat/elevator rides), grabbers that end a grab directly free both players.

## 2026-10-09: first prototype (compiles, not playtested)

Implemented:
- Input: explicit device -> player slot assignment (`coop::SlotAssigner`), SDL instance ids,
  disconnect/reconnect rules, `pc-coop-*` GOAL API. Fixed a pre-existing bug where PS3 pressure axes
  from any joystick leaked into every pad.
- Player contexts: kernel hooks switch the player globals per process run and per event delivery;
  world processes use the closest player in play.
- Player 2: own target, daxter, camera rig, HUD, pools; light spawn state; respawn and leash manager.
- Rendering: one chain with a bucket group per view, render-only pass for player 2, per-view
  framebuffers composited into side-by-side or top/bottom rects, per-view aspect.
- Gameplay: no friendly fire (red-eco/flut flop trackers), separate attack-id ranges, cutscenes and
  talks hold both players, platforms carry two riders, either player pauses, player 2 controller
  loss pauses, pad-1 debug binds disabled in co-op.
- Death: one player's death no longer resets the world; respawn next to the other player after 2 s;
  both down -> one checkpoint reload.
- Streaming: player 2's level from its own position, residency guard before a level under player 2
  is unloaded or hidden, level events to both cameras, level timer counted once.
- Debug menu "Local Co-op" with an info overlay (ticks vs. view-2 render passes, device status).

Verified: C++ build, all Jak 1 GOAL code (522 targets), 1685 tests (1669 baseline + 16 new),
type consistency for all games. See TESTING.md.

Not verified: anything at runtime. No game assets, controllers or GPU session were available.

Next: run the manual test plan in TESTING.md with real assets, starting in Geyser Rock.
