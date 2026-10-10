#!/usr/bin/env python3
"""
Check that the local co-op change set stays a clean add-on on top of upstream OpenGOAL.
Written with AI assistance (AI-assisted).

Compares HEAD with its merge base on upstream (upstream/master, else master) and checks:

  1. Files other games compile must be identical to upstream:
     - everything under goal_src/ outside goal_src/jak1/ (goal-lib.gc, common/, jak2/, jak3/, jakx/)
     - the Jak 1 files Jak 2/3/X reuse (read from their project-lib.gp: pckernel-h, ...)
  2. Hand edits in decompiled files (files with ";; DECOMP BEGINS") carry an "og:preserve-this"
     marker, so upstream's decompiler tooling keeps them.
  3. Lists the shared C++ runtime files that changed. They are compiled for every game, so co-op code
     there must only run when Jak 1 turns co-op on: review them, this script can't tell.

Exit code 1 if rule 1 or 2 is broken.

  python3 scripts/splitscreen/check_upstream_compat.py [--base <commit>]
"""

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MARKER = "og:preserve-this"
# how far above a changed block a marker comment may be
MARKER_LOOKBACK = 3


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def find_base(explicit):
    if explicit:
        return explicit
    for ref in ("upstream/master", "master"):
        try:
            return git("merge-base", "HEAD", ref).strip()
        except subprocess.CalledProcessError:
            continue
    sys.exit("no upstream/master or master to compare with (git remote add upstream ...)")


def jak1_files_reused_by_other_games():
    """Base names that jak2/jak3/jakx project-lib.gp load from goal_src/jak1."""
    names = set()
    for game in ("jak2", "jak3", "jakx"):
        path = os.path.join(ROOT, "goal_src", game, "lib", "project-lib.gp")
        if os.path.exists(path):
            names.update(re.findall(r'\(eq\? base-name "([^"]+)"\)', open(path).read()))
    files = []
    for dirpath, _, filenames in os.walk(os.path.join(ROOT, "goal_src", "jak1")):
        for f in filenames:
            if f.endswith(".gc") and f[:-3] in names:
                files.append(os.path.relpath(os.path.join(dirpath, f), ROOT))
    return sorted(files)


def changed_files(base):
    out = {}
    for line in git("diff", "--name-status", base, "HEAD").splitlines():
        status, *paths = line.split("\t")
        out[paths[-1]] = status[0]
    return out


def unmarked_hunks(base, path):
    """Added blocks after DECOMP BEGINS without a marker in or just above them."""
    lines = open(os.path.join(ROOT, path)).read().split("\n")
    try:
        decomp_start = next(i for i, l in enumerate(lines) if "DECOMP BEGINS" in l) + 1
    except StopIteration:
        return []
    bad = []
    for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", git("diff", "-U0", base, "HEAD", "--", path), re.M):
        start, count = int(m.group(1)), int(m.group(2) or "1")
        if count == 0 or start <= decomp_start:
            continue  # pure deletion (judged with its replacement) or before the decompiled code
        window = lines[max(0, start - 1 - MARKER_LOOKBACK): start - 1 + count]
        if not any(MARKER in l for l in window):
            bad.append((start, lines[start - 1].strip()))
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", help="commit to compare with (default: merge base with upstream/master)")
    args = ap.parse_args()

    base = find_base(args.base)
    changes = changed_files(base)
    errors = 0
    print(f"base {base[:10]}: {len(changes)} files differ")

    shared_goal = jak1_files_reused_by_other_games()
    for path, status in sorted(changes.items()):
        outside_jak1 = path.startswith("goal_src/") and not path.startswith("goal_src/jak1/")
        if outside_jak1 or path in shared_goal:
            print(f"ERROR shared with other games, must match upstream: {path} ({status})")
            errors += 1

    for path, status in sorted(changes.items()):
        if status == "M" and path.startswith("goal_src/jak1/") and path.endswith(".gc"):
            for line, text in unmarked_hunks(base, path):
                print(f"ERROR {path}:{line}: edit without '{MARKER}': {text[:80]}")
                errors += 1

    runtime = [p for p, s in changes.items() if p.startswith(("game/", "common/", "goalc/", "decompiler/"))
               and not p.startswith(("game/assets/jak1/", "decompiler/config/jak1/"))]
    if runtime:
        print(f"\nreview: {len(runtime)} shared runtime/tool files changed (co-op code must only run when Jak 1 enables it):")
        for p in sorted(runtime):
            print(f"  {changes[p]} {p}")

    print(f"\n{'FAILED' if errors else 'OK'}: {errors} problem(s); shared GOAL files checked: {', '.join(shared_goal)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
