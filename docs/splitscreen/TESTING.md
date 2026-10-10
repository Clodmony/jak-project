# Jak 1 local split-screen co-op: testing

> Written with AI assistance (AI-assisted).

## What has been verified, and how

The first development round had no game assets: everything in the table below is compilation and
automated tests. A first runtime session followed on 2026-10-10 (see "Runtime results" below):
keyboard only, no controllers, players driven from the REPL. Steps that need two controllers are
still unverified.

| Check | Command | Baseline (`efb21c3e`) | Co-op branch |
| --- | --- | --- | --- |
| C++ build (Linux, clang 18, Release) | `cmake -B build --preset=Release-linux-clang && cmake --build build -j4` | pass | pass, no new warnings |
| All Jak 1 GOAL code | `./build/goalc/goalc --game jak1 --cmd '(make-group "all-code")'` | 519 targets | 522 targets |
| Test suite | `./test.sh` | 1669 passed | 1688 passed |
| Type consistency (Jak 1/2/3/X) | part of `./test.sh` | pass | pass |

The test suite builds the engine and loads it into a real GOAL runtime (`WithGameTests`), which runs
the load-time code of every edited engine file (this caught a load-order crash during development).
It also compiles all Jak 2/3/X code, which caught an edit to a file shared with Jak 2/3.

New unit tests (`build/goalc-test --gtest_filter='CoopSlots*:SplitscreenLayout*:MemcardNamespace*'`):
- `test/test_coop_slots.cpp` (13 tests): default assignment for 0/1/2 controllers, one device can't
  feed two players, identical controllers (same GUID) are separate players, disconnect keeps the
  claim and never moves another player's device, reconnect of the same model (an idle pad of
  the same model can't take over), join flow.
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

PAL (or another non-NTSC) disc: the decompiler config and the folder names differ.
`goalc --cmd` ignores `goal_src/user/<name>/repl-config.json`, and the test-zone custom level
always looks in `iso_data/jak1` and assumes NTSC unless the disc folder has a `buildinfo.json`
(written by the launcher's extractor, not by `task extract`). What worked with the disc in
`iso_data/jak1_pal`:

```sh
./build/decompiler/decompiler ./decompiler/config/jak1/jak1_config.jsonc ./iso_data ./decompiler_out \
  --version pal --config-override '{"decompile_code": false, "levels_extract": true, "allowed_objects": []}'
# buildinfo.json: serial and xxhash64 of the ELF (SCES_503.61), as the launcher extractor writes it
echo '(mi)' | ./build/goalc/goalc --game jak1 --user <you> --iso-path iso_data/jak1_pal
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
| 26 | Unplug player 2's pad while holding the stick forward | Player 2's Jak stops (neutral input) and the game pauses |
| 27 | Two pads in co-op: press Alt+Enter / F2 | Fullscreen toggles / screenshot is taken (keyboard hotkeys still work) |
| 28 | Keyboard player 1 holds W, plug player 2's pad out and back in | Player 1 keeps walking forward and stops when W is released (no stuck stick) |
| 29 | Fisherman minigame: lose, then answer "play again?" | The question can be answered (pad 0 isn't frozen) |
| 30 | Ride the fisherman's boat to Misty with both players | Both are released at the end; player 2 is brought to player 1 once, not every frame |
| 31 | Kill an enemy visible in both views | Its death dissolve plays at normal speed |
| 32 | Stand in foliage (jungle) with the split on and off | Plants sway at the same speed in both cases |
| 33 | Player 2 hits a dark vine 40+ m from player 1 with player 1's camera turned away | The puff appears in player 2's view |

## Runtime results

2026-10-10, CachyOS Linux, KDE Wayland, 1920x1080 window (internal 2560x1440, MSAA 8), Jak 1 PAL,
debug boot (starts in Sandover, not Geyser Rock).

How: two virtual gamepads (`scripts/splitscreen/vpad.py`, Xbox 360 type, same model so they share
a GUID) feed real SDL input; game state was read and set from the REPL (`goalc` + `(lt)`), and
pictures taken with `(pc-screen-shot)`. Teleports (`move-to-point!`), `'attack` events and task flags
were used to set scenes up quickly; the actions under test (moving, attacking, talking, boarding,
menus, unplugging) went through the pads. No keyboard input was injected: the desktop was in use.

| # | Result |
| --- | --- |
| 1 | Pass: single player with a pad: walk, jump, punch, spin. Note (upstream): with two pads of the same model only one drives single player, the port mapping is per model |
| 2 | Pass after fixes: two pads, co-op starts, player 2 appears 1.5 m beside player 1, window splits, one `gk` process |
| 3 | Pass: pad A moves/jumps/attacks only player 1, pad B only player 2 |
| 4 | Pass: right stick of pad A turns only camera 1 (yaw 154 -> -42), pad B only camera 2 |
| 5 | Not tested (keyboard), #9 |
| 6 | Pass: over 10.5 s, sim ticks +1579, view-2 passes +1579, frames +1579, game clock +10.5 s |
| 7 | Pass: player 2 25 m away sees houses and water player 1 can't |
| 8 | Pass: both players on one orb in the same frame -> one orb |
| 9 | Pass: an enemy (lurker puppy) chases and hits the closer player, each player's own health drops, player 2's attacks kill enemies and break crates, point-blank punches/spins between players do nothing |
| 10, 11 | Pass: either player dies -> respawns beside the other with full health, the other is unaffected, no world reset. 12 death/respawn cycles without a crash (after the HUD fix) |
| 12 | Pass: both dead -> one checkpoint reload, player 2 respawns beside player 1, shared orbs kept |
| 13 | Pass: player 2's Start opens the shared menu, Select pauses; after the fix player 2 can also navigate the menu |
| 14, 26 | Pass: unplugging player 2's pad while walking pauses the session, player 2 stops (neutral input), slot 2 keeps its claim; plugging the same model back in gives player 2 control again |
| 15 | Pass: player 2 70 m away -> brought back beside player 1 |
| 16 | Pass: top/bottom layout, correct proportions, HUD correct after the fix |
| 17, 23 | Pass after fix: power cell collected by player 2 -> victory on player 2, one full-screen view, player 1 hidden for the cinematic, both views back afterwards |
| 18 | Pass: "Stop co-op" -> single view, player 1 only |
| 19 | Pass: a co-op save goes to `saves/coop/`; loading it restores the shared progress; after stopping co-op the save slots show the single-player save again; the single-player save files are byte-identical before and after |
| 20 | Not run, #10 |
| 21 | Partly: the menu flow (Options > Game Options > Misc Options > Local co-op / layout / assign devices) works with the pad in a debug boot and fits on screen; a non-debug boot has no REPL, so it was not driven (#11). A packaged mod, installed the way the launcher does it, boots to the title screen without `-debug` and keeps its settings in its own config folder |
| 22 | Not completed: the jungle elevator to the plant boss needs that level loaded; the test setup didn't trigger it, #12 |
| 24 | Pass: pause/progress menu is one full-screen view |
| 25 | Pass: hitting player 2 buzzes only pad 1, hitting player 1 only pad 0 (game side; the virtual pads have no motors) |
| 27, 28 | Not tested (keyboard), #9 |
| 29 | Not run (fisherman minigame), #12 |
| 30 | Pass after fix: both on the fisherman's boat, player 1 boards, the ride plays full-screen with player 2 held, both are free at Misty, player 2 brought over once |
| 31 | Not conclusive: REPL sampling too coarse to time the death dissolve; code review only, #13 |
| 32 | Code review only (second view doesn't integrate the wind), #13 |
| 33 | Partly: player 2's hit on a dark vine 55 m from player 1 registers; the puff is not clearly visible in a still screenshot, #13 |
| Water | Pass after fix: player 2 swims, both players in one water volume, leaving clears only that player, deadly water kills player 2 and not player 1 |
| NPCs | Pass after fix: player 2 talks to an NPC with their own pad, the prompt shows in player 2's view, player 1's button doesn't trigger it, both are released afterwards |
| Zoomer (#16) | Fire Canyon: either player mounting at the pad gives both their own zoomer (own pad, camera, speed/heat HUD); a zoomer death sends only that player back to the checkpoint onto a new zoomer, also when both die a few seconds apart; both dead in the same moment reloads the checkpoint; the end pad's power cell appears only once both are within 30 m; taking it plays the cinematic and both get off. Driving back to the start pad gets both off. Lava Tube: both mount at the start pad; each player keeps the last checkpoint they drove past (player 2 died after lavatube-middle and came back there while player 1 came back at the start), and a respawn next to a pad gets onto that pad; energy door 4 stayed open while only one player was through, shut once both were, and opened again for a player who respawned before it; the end pad's cell waited for both, then both got off. Fire Canyon again: a player who drives back onto the start pad gets off alone, the other keeps racing (no leash); the one on foot dying comes back on foot at the checkpoint, the one on the zoomer dying comes back on a zoomer. Mountain Pass: the flying-lurker intro holds both players; when the lurkers reach the plunger both players are held for the cinematic, both die and the checkpoint reloads; the bridge builds for either player's blue eco (not run); the end pad's cell waited for both. Precursor Basin: both mount at the entrance pad; with the players on both sides of the active ring and the nearest player switching back and forth, the ring stayed active (before: a false pass); a real pass by either player moved the chain on; the whole ring chain run through ends in the cell cinematic with both players frozen and released afterwards; in the gorge race the race kept running while player 2 still stood at the start after player 1 left (it now also starts when the player who leaves isn't the nearer one: found by the regression scenarios), and it finished only once both had crossed the finish line. Robbers: caught by both players on zoomers; the cell flight holds both, then the player who got the cell plays the cinematic while the other is hidden and frozen in place; both drive on afterwards. The gorge race timer shows in both views. Option "every ring for both" (menu toggle checked): a ring stayed lit after one player flew through and moved on once the other did too, for 15 rings in a row. Not tested: winning the Mountain Pass race by driving (needs real steering), lightning moles |
| Death edge cases (#33) | Scripted with the coop-test scenarios (`deaths-apart`, `death-water`, `death-cutscene`, `death-fall`, `death-platform`): both players dying 5 or 40 frames apart, in either order, reload the checkpoint once with both players next to each other; a player who dies while the other swims respawns next to the swimmer and lives; while the survivor talks to an npc the dead player waits and appears after the talk, visible; player 1 falling below the level's death height dies and respawns next to player 2, player 2 falling there is brought back by the leash first; a respawn next to a player on a floating platform (Misty bone platform) lands on it. A respawn where the 1.5 m probes find no ground (water, small platform) puts the player on the survivor's own spot. Vehicle sections: see the zoomer row |

## Performance

Same machine: AMD Ryzen 7 7700X, Radeon RX 7900 XT (Mesa 26.2.4, radeonsi), CachyOS. Internal
resolution 2560x1440, MSAA 8, vsync off, frame limit raised to 1000 for the measurement, Sandover at
the debug start point, camera untouched, 10 s per case, real frames drawn per wall-clock second:

| Case | fps | ms/frame |
| --- | --- | --- |
| Single player | 721 | 1.39 |
| Co-op side by side | 674 | 1.48 |
| Co-op top/bottom | 674 | 1.48 |

The second view costs about 0.09 ms per frame in this scene. Busier areas (jungle, many actors) were
not measured (#14).

Expected cost: GOAL draw work for the second view (background, foreground, bones, merc, sprites)
and GPU work for a second set of buckets. Simulation cost is unchanged. If a frame takes longer than
1.3x the target frame time, Jak 1 switches to a 2x time step (`display-frame-start`), so frame time
directly affects how the game feels.
