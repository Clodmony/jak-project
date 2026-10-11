#!/usr/bin/env python3
# Written with AI assistance (AI-assisted).
"""Copy the single-player saves of the official Jak 1 into the co-op mod.

The OpenGOAL Launcher gives every mod its own settings and save folder, so the mod doesn't see the
saves of the Jak 1 you played before. This script copies them over:

    from  <OpenGOAL config>/OpenGOAL/jak1/saves/<save folder>/bank*.bin
          (Linux: ~/.config, or $XDG_CONFIG_HOME; Windows: %APPDATA%; macOS: ~/Library/Application Support)
    to    <launcher install>/features/jak1/mods/<source>/_settings/<mod>/OpenGOAL/jak1/saves/<save folder>/
          (the install folder comes from the launcher's settings.json)

In the mod, load the save from the normal "Load game" menu, then turn co-op on (Options > Game
Options > Misc Options > Local co-op). Co-op saves stay in their own folder (saves/coop/) and are
never touched by this script. Existing saves in the mod are only replaced with --force (the old file
is kept as <name>.bak).

Python 3.9+ and the standard library only. Examples (from the repository root):

    python3 scripts/coop-mod/import_saves.py --dry-run     # show what would be copied
    python3 scripts/coop-mod/import_saves.py               # copy
    python3 scripts/coop-mod/import_saves.py --from-dir <saves folder> --to-dir <mod saves folder>

See docs/splitscreen/MOD.md ("Where settings and saves live").
"""

import argparse
import json
import os
import platform
import shutil
import sys
from pathlib import Path


def config_base() -> Path:
    """The folder OpenGOAL and the launcher keep their settings in (common/util/FileUtil.cpp)."""
    system = platform.system()
    if system == "Windows":
        return Path(os.environ["APPDATA"])
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    return Path(xdg) if xdg else Path.home() / ".config"


def default_from_dir() -> Path:
    return config_base() / "OpenGOAL" / "jak1" / "saves"


def launcher_install_dir() -> Path:
    settings = config_base() / "OpenGOAL-Launcher" / "settings.json"
    if not settings.exists():
        sys.exit(f"Launcher settings not found at {settings}; pass --to-dir (or --install-dir).")
    try:
        install = json.loads(settings.read_text(encoding="utf-8")).get("installationDir")
    except (OSError, ValueError) as ex:
        sys.exit(f"Could not read {settings}: {ex}")
    if not install:
        sys.exit(f"{settings} has no installationDir; pass --to-dir (or --install-dir).")
    return Path(install)


def mod_saves_dir(install: Path, source: str, name: str) -> Path:
    return install / "features" / "jak1" / "mods" / source / "_settings" / name / "OpenGOAL" / "jak1" / "saves"


def save_files(saves_dir: Path) -> list[Path]:
    """Single-player save files: <saves>/<save folder>/bank*.bin, not the co-op folder."""
    if not saves_dir.is_dir():
        return []
    out = []
    for folder in sorted(saves_dir.iterdir()):
        if folder.is_dir() and folder.name != "coop":
            out += sorted(f for f in folder.glob("bank*.bin") if f.is_file())
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--from-dir", type=Path, help="saves folder of the official Jak 1 (default: OpenGOAL's own)")
    ap.add_argument("--to-dir", type=Path, help="saves folder of the mod (default: found through the launcher)")
    ap.add_argument("--install-dir", type=Path, help="launcher installation folder (default: from its settings.json)")
    ap.add_argument("--source", default="_local", help="mod source folder (\"_local\" for Add from File)")
    ap.add_argument("--name", default="jak1-coop", help="mod name (default jak1-coop)")
    ap.add_argument("--force", action="store_true", help="replace saves the mod already has (keeps <file>.bak)")
    ap.add_argument("--dry-run", action="store_true", help="only show what would be copied")
    args = ap.parse_args()

    from_dir = args.from_dir or default_from_dir()
    to_dir = args.to_dir or mod_saves_dir(args.install_dir or launcher_install_dir(), args.source, args.name)
    if from_dir.resolve() == to_dir.resolve():
        sys.exit("The source and the target are the same folder.")

    files = save_files(from_dir)
    if not files:
        sys.exit(f"No single-player saves found in {from_dir}.")
    if not args.to_dir and not to_dir.parent.parent.parent.exists():
        print(f"Note: {to_dir.parent.parent.parent} doesn't exist yet (start the mod once first, or check --name/--source).")

    print(f"From {from_dir}\nTo   {to_dir}")
    copied = skipped = 0
    for f in files:
        dest = to_dir / f.relative_to(from_dir)
        if dest.exists() and not args.force:
            print(f"  skip {f.relative_to(from_dir)} (the mod already has it; --force replaces it)")
            skipped += 1
            continue
        print(f"  {'would copy' if args.dry_run else 'copy'} {f.relative_to(from_dir)}" + (" (replacing it, old one kept as .bak)" if dest.exists() else ""))
        if not args.dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                shutil.copy2(dest, dest.with_name(dest.name + ".bak"))
            shutil.copy2(f, dest)
        copied += 1
    print(f"{copied} file(s) {'to copy' if args.dry_run else 'copied'}, {skipped} skipped."
          + ("" if args.dry_run or not copied else " In the mod: Load game, then Misc Options > Local co-op."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
