#!/usr/bin/env python3
"""
Check that the local co-op change set stays a clean add-on on top of upstream OpenGOAL.
Written with AI assistance (AI-assisted).

Compares the working tree (committed or not) with its merge base on upstream (upstream/master,
else master) and checks:

  1. Files other games compile must be identical to upstream:
     - everything under goal_src/ outside goal_src/jak1/ (goal-lib.gc, common/, jak2/, jak3/, jakx/)
     - the Jak 1 files Jak 2/3/X reuse (read from their project-lib.gp: pckernel-h, ...)
  2. Hand edits in decompiled files (files with ";; DECOMP BEGINS") carry an "og:preserve-this"
     marker, so upstream's decompiler tooling keeps them.
  3. Lists the shared C++ runtime files that changed. They are compiled for every game, so co-op code
     there must only run when Jak 1 turns co-op on: review them, this script can't tell.
  4. Level slots (#110): a loop over (-> *level* length) must reach the levels through level-slot,
     never (-> *level* level i): the array index of a slot skips level-default (0 1 3 4).
  5. Changed shared C++/tool files keep upstream's formatting (#6): the same line endings, and no
     hunk that only changes whitespace. Either would conflict with every upstream edit nearby.

Exit code 1 if rule 1, 2, 4 or 5 is broken.

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
    for line in git("diff", "--name-status", base).splitlines():
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
    for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", git("diff", "-U0", base, "--", path), re.M):
        start, count = int(m.group(1)), int(m.group(2) or "1")
        if count == 0 or start <= decomp_start:
            continue  # pure deletion (judged with its replacement) or before the decompiled code
        window = lines[max(0, start - 1 - MARKER_LOOKBACK): start - 1 + count]
        if not any(MARKER in l for l in window):
            bad.append((start, lines[start - 1].strip()))
    return bad


LEVEL_LOOP_RE = re.compile(r"\((?:dotimes|countdown) \(([a-z][a-z0-9-]*) \(-> (?:\*level\*|this|levels|lev-group) length\)\)")
LEVEL_INDEX_RE = re.compile(r"\(-> (?:\*level\*|levels|lev-group) (?:level|data) ([a-z][a-z0-9-]*)[ )]|\(-> this level ([a-z][a-z0-9-]*)[ )]")


def level_slot_misuse(path):
    """(-> *level* level i) with i a loop variable over (-> *level* length): the slot's array index is
    (level-slot-index i), not i (array index 2 is level-default). A loop variable counts while the
    lines are indented deeper than the loop's (the pretty-printed code's form)."""
    bad = []
    loop_vars = {}  # var -> indentation of its loop line
    for n, line in enumerate(open(os.path.join(ROOT, path)).read().split("\n"), 1):
        if not line.strip() or line.lstrip().startswith(";"):
            continue
        indent = len(line) - len(line.lstrip())
        loop_vars = {v: i for v, i in loop_vars.items() if indent > i}
        for m in LEVEL_INDEX_RE.finditer(line):
            var = m.group(1) or m.group(2)
            if var in loop_vars:
                bad.append((n, var))
        for m in LEVEL_LOOP_RE.finditer(line):
            loop_vars[m.group(1)] = indent
    return bad


def level_slot_misuse_in_tree():
    """Rule 4 over all of goal_src/jak1 (not only changed files: an old loop breaks with four slots too)."""
    bad = []
    for root, _dirs, files in os.walk(os.path.join(ROOT, "goal_src", "jak1")):
        for f in files:
            if not f.endswith(".gc"):
                continue
            path = os.path.relpath(os.path.join(root, f), ROOT)
            for line, var in level_slot_misuse(path):
                bad.append((path, line, var))
    return bad


def whitespace_only_hunks(base, path):
    """Hunks whose removed and added lines are the same text once all whitespace is dropped."""
    bad = []
    hunk = None
    for line in git("diff", "-U0", base, "--", path).split("\n") + ["@@"]:
        if line.startswith("@@"):
            if hunk and hunk["-"] and hunk["+"] and \
                    "".join("".join(hunk["-"]).split()) == "".join("".join(hunk["+"]).split()):
                bad.append((hunk["start"], hunk["+"][0].strip()))
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", line)
            hunk = {"start": int(m.group(1)), "-": [], "+": []} if m else None
        elif hunk is not None and line[:1] in ("-", "+") and not line.startswith(("---", "+++")):
            hunk[line[0]].append(line[1:])
    return bad


def line_endings_changed(base, path):
    """True if the file has CRLF line endings upstream and not now, or the other way round."""
    upstream = subprocess.run(["git", "cat-file", "blob", f"{base}:{path}"], cwd=ROOT, check=True,
                              capture_output=True).stdout
    now = open(os.path.join(ROOT, path), "rb").read()
    return (b"\r\n" in upstream) != (b"\r\n" in now)


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

    for path, line, var in level_slot_misuse_in_tree():
        print(f"ERROR {path}:{line}: (-> *level* level {var}) in a loop over the level slots, use (level-slot {var})")
        errors += 1

    runtime = [p for p, s in changes.items() if p.startswith(("game/", "common/", "goalc/", "decompiler/"))
               and not p.startswith(("game/assets/jak1/", "decompiler/config/jak1/"))]
    if runtime:
        print(f"\nreview: {len(runtime)} shared runtime/tool files changed (co-op code must only run when Jak 1 enables it):")
        for p in sorted(runtime):
            print(f"  {changes[p]} {p}")
        for p in sorted(runtime):
            if changes[p] != "M":
                continue
            if line_endings_changed(base, p):
                print(f"ERROR {p}: line endings differ from upstream (whole-file diff)")
                errors += 1
            for line, text in whitespace_only_hunks(base, p):
                print(f"ERROR {p}:{line}: whitespace-only change: {text[:80]}")
                errors += 1

    print(f"\n{'FAILED' if errors else 'OK'}: {errors} problem(s); shared GOAL files checked: {', '.join(shared_goal)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
