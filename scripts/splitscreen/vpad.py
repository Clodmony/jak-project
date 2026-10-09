#!/usr/bin/env python3
"""
Virtual gamepads for testing local co-op without physical controllers (Linux only).
Written with AI assistance (AI-assisted).

Creates Xbox 360 style gamepads with uinput. SDL sees them like real USB pads, so device
hotplug, unplugging and per-pad input go through the same path as real hardware.
Needs write access to /dev/uinput and `python-evdev`.

Run the server, then append commands (one per line) to the command file:

  ./vpad.py serve /tmp/vpad.cmds
  echo "add 0" >> /tmp/vpad.cmds

Commands (pad ids are arbitrary names you choose):
  add <pad> [xbox|ps4]        plug in a pad
  remove <pad>                unplug it
  press <pad> <btn> [ms]      press and release (default 100 ms)
  hold <pad> <btn>            press and keep held
  release <pad> <btn>         release
  stick <pad> <l|r> <x> <y>   stick position, -1..1 (y up is +1)
  neutral <pad>               release everything, center sticks
  sleep <ms>                  delay before the next command
Buttons use PlayStation names: cross circle square triangle l1 r1 l2 r2 l3 r3 select start
up down left right.
"""

import os
import sys
import time

from evdev import AbsInfo, UInput, ecodes as e

MODELS = {
    # vendor, product, name
    "xbox": (0x045E, 0x028E, "Microsoft X-Box 360 pad"),
    "ps4": (0x054C, 0x09CC, "Sony Interactive Entertainment Wireless Controller"),
}

BUTTONS = {
    # the codes the xpad driver sends: X is BTN_X (0x133, aliased BTN_NORTH), Y is BTN_Y (0x134)
    "cross": e.BTN_A,
    "circle": e.BTN_B,
    "square": e.BTN_X,
    "triangle": e.BTN_Y,
    "l1": e.BTN_TL,
    "r1": e.BTN_TR,
    "select": e.BTN_SELECT,
    "start": e.BTN_START,
    "l3": e.BTN_THUMBL,
    "r3": e.BTN_THUMBR,
}
TRIGGERS = {"l2": e.ABS_Z, "r2": e.ABS_RZ}
HAT = {"up": (e.ABS_HAT0Y, -1), "down": (e.ABS_HAT0Y, 1), "left": (e.ABS_HAT0X, -1), "right": (e.ABS_HAT0X, 1)}


class Pad:
    def __init__(self, name, model):
        vendor, product, devname = MODELS[model]
        stick = AbsInfo(value=0, min=-32768, max=32767, fuzz=16, flat=128, resolution=0)
        trigger = AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)
        hat = AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)
        caps = {
            e.EV_KEY: list(BUTTONS.values()) + [e.BTN_MODE],
            e.EV_ABS: [
                (e.ABS_X, stick), (e.ABS_Y, stick), (e.ABS_RX, stick), (e.ABS_RY, stick),
                (e.ABS_Z, trigger), (e.ABS_RZ, trigger),
                (e.ABS_HAT0X, hat), (e.ABS_HAT0Y, hat),
            ],
        }
        self.ui = UInput(caps, name=devname, vendor=vendor, product=product, version=0x110,
                         bustype=e.BUS_USB, phys=f"vpad-{name}")
        self.name = name

    def button(self, btn, down):
        if btn in BUTTONS:
            self.ui.write(e.EV_KEY, BUTTONS[btn], 1 if down else 0)
        elif btn in TRIGGERS:
            self.ui.write(e.EV_ABS, TRIGGERS[btn], 255 if down else 0)
        elif btn in HAT:
            axis, val = HAT[btn]
            self.ui.write(e.EV_ABS, axis, val if down else 0)
        else:
            raise ValueError(f"unknown button {btn}")
        self.ui.syn()

    def stick(self, which, x, y):
        ax, ay = (e.ABS_X, e.ABS_Y) if which == "l" else (e.ABS_RX, e.ABS_RY)
        clamp = lambda v: max(-32768, min(32767, int(v * 32767)))
        self.ui.write(e.EV_ABS, ax, clamp(x))
        self.ui.write(e.EV_ABS, ay, clamp(-y))  # evdev y grows downwards
        self.ui.syn()

    def neutral(self):
        for b in list(BUTTONS) + list(TRIGGERS) + list(HAT):
            self.button(b, False)
        self.stick("l", 0, 0)
        self.stick("r", 0, 0)

    def close(self):
        self.ui.close()


def run(cmd_file):
    pads = {}
    open(cmd_file, "a").close()
    with open(cmd_file) as f:
        f.seek(0, os.SEEK_END)
        print(f"vpad: reading commands from {cmd_file}", flush=True)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.01)
                continue
            words = line.split()
            if not words or words[0].startswith("#"):
                continue
            try:
                op = words[0]
                if op == "add":
                    pads[words[1]] = Pad(words[1], words[2] if len(words) > 2 else "xbox")
                elif op == "remove":
                    pads.pop(words[1]).close()
                elif op == "press":
                    pad = pads[words[1]]
                    pad.button(words[2], True)
                    time.sleep((int(words[3]) if len(words) > 3 else 100) / 1000)
                    pad.button(words[2], False)
                elif op == "hold":
                    pads[words[1]].button(words[2], True)
                elif op == "release":
                    pads[words[1]].button(words[2], False)
                elif op == "stick":
                    pads[words[1]].stick(words[2], float(words[3]), float(words[4]))
                elif op == "neutral":
                    pads[words[1]].neutral()
                elif op == "sleep":
                    time.sleep(int(words[1]) / 1000)
                elif op == "quit":
                    break
                else:
                    raise ValueError(f"unknown command {op}")
                print(f"vpad: ok {line.strip()}", flush=True)
            except Exception as ex:  # keep serving after a bad command
                print(f"vpad: error {line.strip()}: {ex}", flush=True)
    for pad in pads.values():
        pad.close()


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "serve":
        print(__doc__)
        sys.exit(1)
    run(sys.argv[2])
