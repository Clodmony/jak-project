# Jak 1 local split-screen co-op: testing

> Written with AI assistance (AI-assisted).

## What has been verified, and how

No game assets were available in the development environment (`iso_data/jak1` is empty), so the game
has **not been run or playtested**. Everything below is compilation and automated tests.

| Check | Command | Baseline (`efb21c3e`) | Co-op branch |
| --- | --- | --- | --- |
| C++ build (Linux, clang 18, Release) | `cmake -B build --preset=Release-linux-clang && cmake --build build -j4` | pass | pass, no new warnings |
| All Jak 1 GOAL code | `./build/goalc/goalc --game jak1 --cmd '(make-group "all-code")'` | 519 targets | 522 targets |
| Test suite | `./test.sh` | 1669 passed | 1687 passed |
| Type consistency (Jak 1/2/3/X) | part of `./test.sh` | pass | pass |

The test suite builds the engine and loads it into a real GOAL runtime (`WithGameTests`), which runs
the load-time code of every edited engine file (this caught a load-order crash during development).
It also compiles all Jak 2/3/X code, which caught an edit to a file shared with Jak 2/3.

New unit tests (`build/goalc-test --gtest_filter='CoopSlots*:SplitscreenLayout*:MemcardNamespace*'`):
- `test/test_coop_slots.cpp` (12 tests): default assignment for 0/1/2 controllers, one device can't
  feed two players, identical controllers (same GUID) are separate players, disconnect keeps the
  claim and never moves another player's device, reconnect of the same model, join flow.
- `test/test_splitscreen_layout.cpp` (4 tests): view rects for both layouts, divider, bounds for
  odd and tiny framebuffers.
- `test/test_memcard_namespace.cpp` (2 tests): the co-op save folder name is accepted, path-like
  names (`..`, slashes, too long) are rejected.

## Manual test plan (needs your game files)

Setup, from the repository root:

```sh
cmake -B build --preset=Release-linux-clang && cmake --build build -j8
# put your own Jak 1 disc files in iso_data/jak1, then extract (task extract):
./build/decompiler/decompiler "./decompiler/config/jak1/jak1_config.jsonc" "./iso_data" "./decompiler_out" \
  --version "ntsc_v1" --config-override '{"decompile_code": false, "levels_extract": true, "allowed_objects": []}'
./build/goalc/goalc --game jak1     # then at the g > prompt: (mi)
./build/game/gk -v --game jak1 -- -boot -fakeiso -debug    # task boot-game
```

Start co-op from the pause menu (any build): Options > Game Options > Misc Options > "Local co-op"
on. Or from the debug menu (debug builds: press R3 on player 1's pad, then
"Local Co-op" > "Start co-op"), or from the REPL: run `./build/goalc/goalc --game jak1`, `(lt)` to
connect, then `(coop-start)`. Turn on "Local Co-op" > "Show co-op info" for the on-screen counters.

| # | Step | Expected |
| --- | --- | --- |
| 1 | With co-op never started, play Geyser Rock for a few minutes | Identical to upstream: one view, normal camera, pause, death |
| 2 | Connect two controllers, start co-op in Geyser Rock | Player 2 appears next to player 1 after ~2 s; the window splits side by side; one `gk` process, one window |
| 3 | Move each stick, jump, punch, spin on each pad | Each pad moves only its own Jak; steering is relative to that player's own camera |
| 4 | Move each right stick | Only that player's camera orbits |
| 5 | Keyboard/mouse + one controller: "Auto-assign devices" | Keyboard/mouse drives player 1, the controller player 2 |
| 6 | Info overlay: compare "ticks" with "view-2 passes" over ~10 s | Both grow by one per frame; game speed (timers, animations) matches single player |
| 7 | Walk player 2 away so player 1 can't see an enemy or orb, look at it with player 2 | It renders in player 2's view and is not missing (one view's culling must not hide it in the other) |
| 8 | Both players run to the same orb / fly box | One reward; the orb counter goes up once |
| 9 | Let an enemy attack each player | The enemy goes for the closer player; each player's own health drops; no friendly fire from punches or red-eco ground pound |
| 10 | Kill player 2 (e.g. fall into water/dark eco) | Player 1 keeps playing, world not reset; player 2 respawns next to player 1 after ~2 s |
| 11 | Kill player 1 while player 2 is alive | Same, mirrored |
| 12 | Kill both | One checkpoint reload, then player 2 respawns next to player 1 |
| 13 | Press Start/Select on player 2's pad | The whole session pauses (single full-screen view while paused) |
| 14 | Unplug player 2's controller during play | Session pauses; player 2 gets neutral input; plugging the same pad back in restores it |
| 15 | Walk player 2 more than 60 m from player 1 | Player 2 is brought back next to player 1 |
| 16 | Debug menu: "Top/bottom split", or Misc Options > "Co-op split top/bottom" | Views stack vertically with correct aspect |
| 17 | Talk to an NPC / collect a power cell | Single full-screen view during the cutscene, both players held, both views back afterwards |
| 18 | "Stop co-op" | Player 2 disappears, single view, single-player input mapping back |
| 19 | Save in co-op to a slot, stop co-op, open the load menu | The co-op save is in `<config>/OpenGOAL/jak1/saves/coop/`; the normal `saves/` files are unchanged (compare timestamps); the load menu shows single-player saves again |
| 20 | Die as player 1 while player 2 is alive, then "Stop co-op" before player 1 respawns | Player 1 reappears through the normal checkpoint reload; the game doesn't stay stuck with an invisible Jak |
| 21 | Start co-op from Misc Options > "Local co-op" in a non-debug boot (`gk -boot` without `-debug`) | Same as step 2; the menu shows the three co-op entries and fits on screen. With one controller, keyboard/mouse becomes player 1 and the controller player 2, so the menu is then navigated with the keyboard |
| 22 | Player 2 presses an elevator button (jungle elevator) with both players on it | Both players are held during the ride and both get control back at the top |
| 23 | Player 2 collects a power cell while player 1 stands a few metres away | The victory animation plays on player 2, not player 1 |
| 24 | Pause (Start) while split | The pause menu is one full-screen view, not drawn in player 1's half |
| 25 | Hit player 2 / let player 2 land a big fall | Player 2's controller rumbles, player 1's doesn't |

## Performance measurement (not done)

No measurements exist yet: they need the real game and a GPU. Repeatable scene: Geyser Rock at the
first continue point, camera untouched, co-op info overlay on.

1. Open the imgui debug bar (F1 in debug builds) and enable the profiler / small profiler window.
2. Record the frame time with co-op off for 30 s, then with co-op on (side by side) for 30 s.
3. Report: CPU/GPU model, OS, window and internal resolution, MSAA, vsync/target fps, and the
   GOAL profiler times for `draw-hook` and `coop-view-2`.

Expected cost: GOAL draw work for the second view (background, foreground, bones, merc, sprites)
and GPU work for a second set of buckets. Simulation cost is unchanged. If a frame takes longer than
1.3x the target frame time, Jak 1 switches to a 2x time step (`display-frame-start`), so frame time
directly affects how the game feels.
