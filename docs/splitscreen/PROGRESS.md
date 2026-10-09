# Jak 1 local split-screen co-op: progress

> Written with AI assistance (AI-assisted). Newest first.

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
