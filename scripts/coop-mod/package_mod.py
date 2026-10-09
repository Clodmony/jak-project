#!/usr/bin/env python3
# Written with AI assistance (AI-assisted).
"""Package a local build of this fork as an OpenGOAL Launcher mod ("Add from File").

The archive has the same layout as the GitHub release assets made by
.github/workflows/mod-release-pipeline.yml with .github/scripts/releases/extract_mod_build_*.sh:

    gk, goalc, extractor                    (gk.exe, goalc.exe, extractor.exe on Windows)
    data/launcher/error-code-metadata.json
    data/decompiler/config/...
    data/goal_src/...
    data/game/assets/...
    data/game/graphics/opengl_renderer/shaders/...
    data/custom_assets/...
    data/log/                               (empty)

Differences from the CI scripts, all on the safe side:
  - Only files tracked by git are packaged (contents are read from the working tree, so local edits
    to tracked files are included). Untracked and ignored files such as goal_src/user/*,
    custom_assets/*/texture_replacements/* or anything extracted from a disc never are.
  - Every entry is checked against an allow list before and after writing; disc images, extracted
    game files, compiled output, saves and settings are refused.
  - A build that only runs on this machine (dynamically linked against libraries in the build
    folder) is refused unless --allow-dynamic is given (Linux and macOS only).

Python 3.9+ and the standard library only. Examples (from the repository root):

    python3 scripts/coop-mod/package_mod.py                 # auto-detect the build, write the archive
    python3 scripts/coop-mod/package_mod.py --dry-run       # checks only
    python scripts/coop-mod/package_mod.py --bin-dir out/build/Release/bin     # Windows
    python3 scripts/coop-mod/package_mod.py --check build/coop-mod/jak1-coop.tar.gz

See docs/splitscreen/MOD.md.
"""

import argparse
import datetime
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import stat
import struct
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path

# --------------------------------------------------------------------------------------------------
# Layout (keep in sync with .github/scripts/releases/extract_mod_build_unix.sh, lines 23-35)
# --------------------------------------------------------------------------------------------------

# (path in the repository, path in the archive); only git-tracked files below these are packaged
DATA_TREES = [
    ("decompiler/config", "data/decompiler/config"),
    ("goal_src", "data/goal_src"),
    ("game/assets", "data/game/assets"),
    ("game/graphics/opengl_renderer/shaders", "data/game/graphics/opengl_renderer/shaders"),
    ("custom_assets", "data/custom_assets"),
]
DATA_FILES = [
    (".github/scripts/releases/error-code-metadata.json", "data/launcher/error-code-metadata.json"),
]
EMPTY_DIRS = ["data/log"]

BINARIES = ["gk", "goalc", "extractor"]
# where CMake puts each binary when it does not use a flat bin/ folder (Linux, macOS)
BINARY_SUBDIR = {"gk": "game", "goalc": "goalc", "extractor": "decompiler"}

PLATFORMS = {
    # name: (executable suffix, archive extension, expected binary format)
    "linux": ("", ".tar.gz", "elf-x86_64"),
    "windows": (".exe", ".zip", "pe-x86_64"),
    "macos-intel": ("", ".tar.gz", "macho-x86_64"),
    # not produced by the GitHub pipeline; for a local Apple Silicon build only
    "macos-arm": ("", ".tar.gz", "macho-arm64"),
}

# how to make a portable build in the folder that the auto-detection looks at first
STATIC_BUILD_HINT = {
    "linux": "cmake --preset=Release-linux-clang-static && cmake --build build/Release/bin",
    "windows": "cmake --preset=Release-windows-clang-static && cmake --build out/build/Release",
    "macos-intel": "cmake --preset=Release-macos-x86_64-clang-static && cmake --build build/Release/bin",
    "macos-arm": "cmake --preset=Release-macos-arm64-clang-static && cmake --build build/Release/bin",
}

SUPPORTED_GAMES = ["jak1", "jak2", "jak3", "jakx"]
DEFAULT_NAME = "jak1-coop"
METADATA_SCHEMA_VERSION = "0.1.0"  # as in mod-release-pipeline.yml
MAX_DATA_FILE_SIZE = 20 * 1024 * 1024  # the largest tracked data file today is a 5.5 MB font

# directory names that never belong in a mod archive (compared case-insensitively)
FORBIDDEN_COMPONENTS = {
    "iso_data", "decompiler_out", "out", "texture_replacements", "merc_replacements",
    "game_config", "saves", "savestate_out", "savestate-out", "ci-artifacts", ".git",
    "node_modules", "__pycache__",
}
# extensions of disc images, game archives, compiled objects, audio and save files
FORBIDDEN_EXTENSIONS = {
    ".iso", ".img", ".cue", ".bin", ".cgo", ".dgo", ".go", ".o", ".str", ".vag", ".sbk", ".mus",
    ".p2s", ".sav", ".gci", ".mcd", ".ps2",
}
# goal_src/user is for personal REPL files; only these two tracked files may be packaged
ALLOWED_USER_FILES = {"data/goal_src/user/.gitignore", "data/goal_src/user/readme.md"}

CREDENTIAL_RE = re.compile(
    rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"
    rb"|gh[pousr]_[A-Za-z0-9]{36}"
    rb"|github_pat_[A-Za-z0-9_]{22,}"
    rb"|AKIA[0-9A-Z]{16}"
    rb"|xox[baprs]-[A-Za-z0-9-]{10,}"
)

# from .github/schemas/mods/v2/mod-schema.v2.json
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

VERSION_PLACEHOLDER = "%MODVERSIONPLACEHOLDER%"  # see replace-mod-version-timestamp.py


class PackageError(Exception):
    pass


def info(msg=""):
    print(msg, flush=True)


def warn(msg):
    print("WARNING: " + msg, flush=True)


# --------------------------------------------------------------------------------------------------
# Allow list
# --------------------------------------------------------------------------------------------------


def _allowed_dirs():
    """The folders above the packaged trees and files, e.g. data/game/graphics."""
    dirs = {"data"}
    for _, dst in DATA_TREES + DATA_FILES:
        parts = dst.split("/")
        for i in range(1, len(parts) + 1):
            dirs.add("/".join(parts[:i]))
    for _, dst in DATA_FILES:
        dirs.discard(dst)
    dirs.update(EMPTY_DIRS)
    return dirs


ALLOWED_DIRS = _allowed_dirs()


def check_entry(name, is_dir, platform):
    """Return None if `name` (relative, '/'-separated, no './' prefix) may be in the archive,
    otherwise the reason it may not."""
    exe = PLATFORMS[platform][0]
    if not name or name.startswith("/") or "\\" in name or re.match(r"^[A-Za-z]:", name):
        return "absolute or malformed path"
    parts = name.split("/")
    if any(p in ("", ".", "..") for p in parts):
        return "path with empty, '.' or '..' component"
    lower = name.lower()
    lower_parts = lower.split("/")
    for p in lower_parts[:-1] if not is_dir else lower_parts:
        if p in FORBIDDEN_COMPONENTS:
            return "forbidden directory '{}'".format(p)
    if "log" in lower_parts and lower != "data/log":
        return "log folder"
    if lower.startswith("data/goal_src/user/") and lower not in ALLOWED_USER_FILES:
        return "personal file in goal_src/user"
    if not is_dir:
        ext = os.path.splitext(lower_parts[-1])[1]
        if ext in FORBIDDEN_EXTENSIONS:
            return "forbidden file type '{}'".format(ext)
    # allow list
    if is_dir:
        if name in ALLOWED_DIRS:
            return None
    else:
        if "/" not in name:
            if name in [b + exe for b in BINARIES]:
                return None
            return "unexpected file at the archive root"
        if name in [dst for _, dst in DATA_FILES]:
            return None
    for _, dst in DATA_TREES:
        if name.startswith(dst + "/"):
            return None
    return "not in the allow list"


# --------------------------------------------------------------------------------------------------
# git
# --------------------------------------------------------------------------------------------------


def git(repo, *args, check=True):
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo)] + list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        raise PackageError("git was not found on PATH; it is needed to list the tracked files")
    if check and proc.returncode != 0:
        raise PackageError(
            "git {} failed: {}".format(" ".join(args), proc.stderr.decode(errors="replace").strip())
        )
    return proc


def find_repo(arg):
    start = Path(arg) if arg else Path(__file__).resolve().parent
    proc = git(start, "rev-parse", "--show-toplevel", check=False)
    if proc.returncode != 0:
        raise PackageError("{} is not inside a git checkout of jak-project".format(start))
    repo = Path(proc.stdout.decode().strip())
    if not (repo / "goal_src").is_dir() or not (repo / "decompiler" / "config").is_dir():
        raise PackageError("{} does not look like a jak-project checkout".format(repo))
    return repo


def tracked_files(repo, tree):
    """(path, mode) of every file git tracks below `tree`."""
    out = git(repo, "ls-files", "-z", "-s", "--", tree).stdout.decode("utf-8")
    result = []
    for rec in out.split("\0"):
        if not rec:
            continue
        meta, path = rec.split("\t", 1)
        mode = meta.split(" ")[0]
        result.append((path, mode))
    return result


def git_head_info(repo):
    sha = git(repo, "rev-parse", "--short", "HEAD").stdout.decode().strip()
    epoch = int(git(repo, "log", "-1", "--format=%ct", "HEAD").stdout.decode().strip())
    tag = git(repo, "describe", "--tags", "--exact-match", "HEAD", check=False)
    tag = tag.stdout.decode().strip() if tag.returncode == 0 else ""
    return sha, epoch, tag


def git_status(repo, paths):
    out = git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", *paths)
    entries = []
    recs = out.stdout.decode("utf-8").split("\0")
    i = 0
    while i < len(recs):
        rec = recs[i]
        i += 1
        if not rec:
            continue
        code, path = rec[:2], rec[3:]
        if code[0] in "RC":
            i += 1  # the original path of a rename follows
        entries.append((code, path))
    return entries


# --------------------------------------------------------------------------------------------------
# Binaries
# --------------------------------------------------------------------------------------------------


def find_binary(bin_dir, name, exe):
    for cand in (bin_dir / BINARY_SUBDIR[name] / (name + exe), bin_dir / (name + exe)):
        if cand.is_file():
            return cand
    return None


def read_cmake_cache(bin_dir):
    for cand in (bin_dir / "CMakeCache.txt", bin_dir.parent / "CMakeCache.txt"):
        if cand.is_file():
            values = {}
            with open(cand, encoding="utf-8", errors="replace") as f:
                for line in f:
                    m = re.match(r"^([A-Za-z0-9_]+):[A-Z]+=(.*)$", line.rstrip("\r\n"))
                    if m:
                        values[m.group(1)] = m.group(2)
            return cand, values
    return None, {}


def cmake_bool(value):
    if value is None:
        return None
    return value.strip().upper() in ("1", "ON", "YES", "TRUE", "Y")


def candidate_bin_dirs(repo, platform):
    if platform == "windows":
        # CMake presets (task build-release) and the CI layout (cmake -B build)
        return [repo / "out" / "build" / "Release" / "bin", repo / "build" / "bin"]
    # preset binaryDir (cmake --preset ...) and the Taskfile / CI layout (cmake -B build)
    return [repo / "build" / "Release" / "bin", repo / "build"]


def detect_bin_dir(repo, platform):
    exe = PLATFORMS[platform][0]
    found = []
    for cand in candidate_bin_dirs(repo, platform):
        if cand.is_dir() and find_binary(cand, "gk", exe):
            _, cache = read_cmake_cache(cand)
            found.append((cand, cmake_bool(cache.get("STATICALLY_LINK"))))
    if not found:
        raise PackageError(
            "no build found in {}; build first or pass --bin-dir".format(
                ", ".join(str(c) for c in candidate_bin_dirs(repo, platform))
            )
        )
    for cand, static in found:
        if static:
            return cand
    return found[0][0]


def binary_format(path):
    """Describe the executable format of `path`, e.g. 'elf-x86_64', 'pe-x86_64', 'macho-arm64'."""
    with open(path, "rb") as f:
        return binary_format_bytes(f.read(4096))


def binary_format_bytes(head):
    if len(head) < 64:
        return "unknown"
    if head[:4] == b"\x7fELF":
        if head[4] != 2 or head[5] != 1:
            return "elf-other"
        machine = struct.unpack_from("<H", head, 18)[0]
        return {0x3E: "elf-x86_64", 0xB7: "elf-aarch64"}.get(machine, "elf-other")
    if head[:2] == b"MZ" and len(head) >= 0x40:
        pe = struct.unpack_from("<I", head, 0x3C)[0]
        if pe + 6 <= len(head) and head[pe:pe + 4] == b"PE\0\0":
            machine = struct.unpack_from("<H", head, pe + 4)[0]
            return {0x8664: "pe-x86_64", 0xAA64: "pe-arm64"}.get(machine, "pe-other")
        return "pe-other"
    cpu_names = {0x01000007: "x86_64", 0x0100000C: "arm64"}
    if head[:4] == b"\xcf\xfa\xed\xfe":
        cpu = struct.unpack_from("<I", head, 4)[0]
        return "macho-" + cpu_names.get(cpu, "other")
    if head[:4] == b"\xca\xfe\xba\xbe":
        count = struct.unpack_from(">I", head, 4)[0]
        cpus = []
        for i in range(min(count, 16)):
            cpu = struct.unpack_from(">I", head, 8 + 20 * i)[0]
            cpus.append(cpu_names.get(cpu, "other"))
        return "macho-fat-" + "+".join(sorted(cpus))
    return "unknown"


def format_matches(fmt, expected):
    if fmt == expected:
        return True
    # a universal macOS binary is fine if it contains the expected architecture
    if fmt.startswith("macho-fat-") and expected.startswith("macho-"):
        return expected[len("macho-"):] in fmt[len("macho-fat-"):].split("+")
    return False


def elf_dynamic_info(path):
    """(needed libraries, runpath entries) of a 64-bit little-endian ELF file."""
    with open(path, "rb") as f:
        hdr = f.read(64)
        phoff = struct.unpack_from("<Q", hdr, 32)[0]
        phentsize, phnum = struct.unpack_from("<HH", hdr, 54)
        f.seek(phoff)
        phdrs = f.read(phentsize * phnum)
        loads, dynamic = [], None
        for i in range(phnum):
            p_type, _, p_offset, p_vaddr, _, p_filesz = struct.unpack_from(
                "<IIQQQQ", phdrs, i * phentsize
            )
            if p_type == 1:
                loads.append((p_vaddr, p_offset, p_filesz))
            elif p_type == 2:
                dynamic = (p_offset, p_filesz)
        if dynamic is None:
            return [], []  # fully static
        f.seek(dynamic[0])
        dyn = f.read(dynamic[1])
        needed, runpaths, strtab = [], [], None
        for off in range(0, len(dyn) - 15, 16):
            tag, val = struct.unpack_from("<qQ", dyn, off)
            if tag == 0:
                break
            if tag == 1:
                needed.append(val)
            elif tag in (15, 29):  # DT_RPATH, DT_RUNPATH
                runpaths.append(val)
            elif tag == 5:
                strtab = val
        if strtab is None:
            return [], []
        strtab_off = None
        for vaddr, offset, size in loads:
            if vaddr <= strtab < vaddr + size:
                strtab_off = strtab - vaddr + offset
        if strtab_off is None:
            return [], []

        def read_str(index):
            f.seek(strtab_off + index)
            buf = b""
            while b"\0" not in buf and len(buf) < 4096:
                chunk = f.read(256)
                if not chunk:
                    break
                buf += chunk
            return buf.split(b"\0", 1)[0].decode("utf-8", errors="replace")

        rp = []
        for v in runpaths:
            rp.extend(x for x in read_str(v).split(":") if x)
        return [read_str(v) for v in needed], rp


# libraries every Linux desktop has; anything else would have to ship next to the binaries.
# (A static build still links these dynamically; gk also needs libz when CMake found a system zlib.)
SYSTEM_LIB_RE = re.compile(
    r"^(libc|libm|libdl|librt|libpthread|libresolv|libutil|libz|libstdc\+\+|libgcc_s)\.so(\.\d+)*$"
    r"|^ld-linux[-\w.]*\.so(\.\d+)*$"
)


def shorten(items, keep=3):
    if len(items) <= keep:
        return ", ".join(items)
    return "{} and {} more".format(", ".join(items[:keep]), len(items) - keep)


def assess_portability(platform, bin_dir, binaries):
    """Return (verdict, notes): verdict is 'static', 'dynamic' or 'unknown'."""
    notes = []
    cache_path, cache = read_cmake_cache(bin_dir)
    static = cmake_bool(cache.get("STATICALLY_LINK"))
    if cache_path:
        notes.append(
            "CMake cache {}: STATICALLY_LINK={}, CMAKE_BUILD_TYPE={}".format(
                cache_path, cache.get("STATICALLY_LINK", "?"), cache.get("CMAKE_BUILD_TYPE", "?")
            )
        )
    verdict = {True: "static", False: "dynamic", None: "unknown"}[static]

    if platform == "linux":
        for name, path in binaries.items():
            needed, runpath = elf_dynamic_info(path)
            odd = [lib for lib in needed if not SYSTEM_LIB_RE.match(lib)]
            abs_rp = [r for r in runpath if not r.startswith("$ORIGIN")]
            if odd or abs_rp:
                verdict = "dynamic"
                notes.append(
                    "{} needs {} (RUNPATH {})".format(
                        name, shorten(odd) or "only system libraries", shorten(abs_rp) or "none"
                    )
                )
            elif verdict == "unknown":
                verdict = "static"
    elif platform == "windows":
        dlls = sorted({p.name for b in binaries.values() for p in b.parent.glob("*.dll")})
        if dlls:
            notes.append("DLLs next to the binaries: " + ", ".join(dlls[:8]))
            if static is not True:
                verdict = "dynamic"
    return verdict, notes


def maybe_strip(binaries, platform, mode, tmpdir):
    """Strip copies of the binaries (never the originals), like the CI 'Prepare artifacts' step."""
    if mode == "off" or platform == "windows":
        return binaries
    host_ok = (platform == "linux" and sys.platform.startswith("linux")) or (
        platform.startswith("macos") and sys.platform == "darwin"
    )
    strip = shutil.which("strip")
    if not host_ok or not strip:
        if mode == "on":
            raise PackageError("--strip on: no usable 'strip' for {} on this host".format(platform))
        return binaries
    out = {}
    for name, path in binaries.items():
        dst = Path(tmpdir) / name
        shutil.copy2(path, dst)
        proc = subprocess.run([strip, str(dst)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            if mode == "on":
                raise PackageError("strip failed for {}: {}".format(path, proc.stderr.decode().strip()))
            warn("strip failed for {}, packaging it unstripped".format(path))
            out[name] = path
        else:
            out[name] = dst
    return out


# --------------------------------------------------------------------------------------------------
# Plan
# --------------------------------------------------------------------------------------------------


class Entry:
    __slots__ = ("name", "is_dir", "source", "data", "mode")

    def __init__(self, name, is_dir=False, source=None, data=None, mode=0o644):
        self.name, self.is_dir, self.source, self.data, self.mode = name, is_dir, source, data, mode

    def size(self):
        if self.is_dir:
            return 0
        if self.data is not None:
            return len(self.data)
        return self.source.stat().st_size

    def read(self, limit=None):
        if self.data is not None:
            return self.data[:limit]
        with open(self.source, "rb") as f:
            return f.read(-1 if limit is None else limit)


def sort_key(name):
    return name.split("/")


def build_plan(repo, platform, binaries, version, timestamp):
    errors, entries = [], []
    exe = PLATFORMS[platform][0]
    for name in BINARIES:
        entries.append(Entry(name + exe, source=binaries[name], mode=0o755))

    files = []
    for src_tree, dst_tree in DATA_TREES:
        listed = tracked_files(repo, src_tree)
        if not listed:
            errors.append("git tracks no files in {}".format(src_tree))
        for path, mode in listed:
            files.append((path, mode, dst_tree + path[len(src_tree):]))
    for src, dst in DATA_FILES:
        listed = tracked_files(repo, src)
        if not listed:
            errors.append("{} is not tracked by git".format(src))
        for path, mode in listed:
            files.append((path, mode, dst))

    missing = []
    for path, mode, dst in files:
        if mode in ("120000", "160000"):
            errors.append("{} is a symlink or submodule in git".format(path))
            continue
        full = repo / path
        if not full.exists():
            missing.append(path)
            continue
        if full.is_symlink() or not full.is_file():
            errors.append("{} is not a regular file".format(path))
            continue
        entry = Entry(dst, source=full)
        if full.name == "mod-settings.gc":
            text = full.read_text(encoding="utf-8")
            if VERSION_PLACEHOLDER in text:
                stamp = "{} {}".format(version, timestamp)
                entry.data = text.replace(VERSION_PLACEHOLDER, stamp).encode("utf-8")
                info("Replaced {} in {} with '{}'".format(VERSION_PLACEHOLDER, path, stamp))
        entries.append(entry)
    if missing:
        warn(
            "{} tracked file(s) are deleted in the working tree and are left out, e.g. {}".format(
                len(missing), ", ".join(missing[:3])
            )
        )

    dirs = set(EMPTY_DIRS)
    for e in entries:
        parts = e.name.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            dirs.add("/".join(parts[:i]))
    entries.extend(Entry(d, is_dir=True, mode=0o755) for d in dirs)
    entries.sort(key=lambda e: sort_key(e.name))
    return entries, errors


# --------------------------------------------------------------------------------------------------
# Checks (shared by the plan and by archives read back from disk)
# --------------------------------------------------------------------------------------------------


def check_entries(records, platform, games, content_reader=None):
    """records: list of (name, kind, mode, size) with kind in file/dir/symlink/link/other and
    mode None when unknown. content_reader(name, limit) -> the first `limit` bytes (all if None)
    of a file, for the content checks. Returns a list of errors."""
    errors = []
    exe = PLATFORMS[platform][0]
    seen = set()
    by_name = {}
    for name, kind, mode, size in records:
        if name in seen:
            errors.append("duplicate entry: " + name)
        seen.add(name)
        by_name[name] = (kind, mode, size)
        if kind not in ("file", "dir"):
            errors.append("{}: {} entries are not allowed".format(name, kind))
            continue
        reason = check_entry(name, kind == "dir", platform)
        if reason:
            errors.append("{}: {}".format(name, reason))
        if kind == "file" and "/" in name and size > MAX_DATA_FILE_SIZE:
            errors.append("{}: {} MB is too large for a data file".format(name, size // (1 << 20)))

    for b in BINARIES:
        kind, mode, _ = by_name.get(b + exe, (None, None, None))
        if kind != "file":
            errors.append("missing binary at the archive root: " + b + exe)
        elif platform != "windows" and mode is not None and (mode & 0o111) != 0o111:
            errors.append("{} is not executable in the archive (mode {:o})".format(b + exe, mode))
    required = ["data/launcher/error-code-metadata.json"]
    for g in games:
        required += [
            "data/goal_src/{}/game.gp".format(g),
            "data/decompiler/config/{}/{}_config.jsonc".format(g, g),
        ]
    for r in required:
        if by_name.get(r, (None,))[0] != "file":
            errors.append("missing required file: " + r)
    for d in ["data", "data/log", "data/game/assets", "data/game/graphics/opengl_renderer/shaders"]:
        if d not in by_name:
            errors.append("missing directory: " + d)

    if content_reader is not None:
        fmt_expected = PLATFORMS[platform][2]
        for name, kind, _, _ in records:
            if kind != "file":
                continue
            if name in [b + exe for b in BINARIES]:
                fmt = binary_format_bytes(content_reader(name, 4096))
                if not format_matches(fmt, fmt_expected):
                    errors.append("{}: {} binary, expected {}".format(name, fmt, fmt_expected))
            elif CREDENTIAL_RE.search(content_reader(name, None)):
                errors.append("{}: looks like it contains a credential or private key".format(name))
    return errors


def plan_records(entries):
    return [(e.name, "dir" if e.is_dir else "file", e.mode, e.size()) for e in entries]


# --------------------------------------------------------------------------------------------------
# Writing and reading archives
# --------------------------------------------------------------------------------------------------


def write_tar_gz(entries, dest, mtime):
    with open(dest, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=mtime) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as tar:
                # same naming as CI's `tar czf <archive> .`: ./, ./data/, ./gk, ...
                for e in [Entry(".", is_dir=True, mode=0o755)] + entries:
                    ti = tarfile.TarInfo("./" + e.name if e.name != "." else ".")
                    ti.mtime, ti.uid, ti.gid, ti.uname, ti.gname = mtime, 0, 0, "", ""
                    ti.mode = e.mode
                    if e.is_dir:
                        ti.type = tarfile.DIRTYPE
                        tar.addfile(ti)
                    elif e.data is not None:
                        ti.size = len(e.data)
                        tar.addfile(ti, io.BytesIO(e.data))
                    else:
                        ti.size = e.source.stat().st_size
                        with open(e.source, "rb") as f:
                            tar.addfile(ti, f)


def write_zip(entries, dest, mtime):
    date_time = time.gmtime(max(mtime, 315532800))[:6]  # zip dates start in 1980
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for e in entries:
            if e.is_dir:
                zi = zipfile.ZipInfo(e.name + "/", date_time=date_time)
                zi.create_system = 3
                zi.external_attr = ((stat.S_IFDIR | e.mode) << 16) | 0x10
                zi.compress_type = zipfile.ZIP_STORED
                zf.writestr(zi, b"")
                continue
            zi = zipfile.ZipInfo(e.name, date_time=date_time)
            zi.create_system = 3
            zi.external_attr = (stat.S_IFREG | e.mode) << 16
            zi.compress_type = zipfile.ZIP_DEFLATED
            with zf.open(zi, "w") as out:
                if e.data is not None:
                    out.write(e.data)
                else:
                    with open(e.source, "rb") as f:
                        shutil.copyfileobj(f, out, 1 << 20)


def normalize_member_name(name):
    while name.startswith("./"):
        name = name[2:]
    return name.rstrip("/")


class ArchiveReader:
    def __init__(self, path):
        self.path = Path(path)
        self.is_zip = self.path.name.endswith(".zip")
        if not self.is_zip and not self.path.name.endswith(".tar.gz"):
            raise PackageError("the launcher only accepts .zip (Windows) or .tar.gz archives")
        if self.is_zip:
            self.zf = zipfile.ZipFile(self.path)
        else:
            self.tf = tarfile.open(self.path, "r:gz")
        self._members = {}

    def close(self):
        (self.zf if self.is_zip else self.tf).close()

    def records(self):
        recs = []
        if self.is_zip:
            for zi in self.zf.infolist():
                name = normalize_member_name(zi.filename)
                mode_bits = zi.external_attr >> 16 if zi.create_system == 3 else 0
                if stat.S_ISLNK(mode_bits):
                    kind = "symlink"
                elif zi.filename.endswith("/"):
                    kind = "dir"
                else:
                    kind = "file"
                mode = stat.S_IMODE(mode_bits) if mode_bits else None
                self._members[name] = zi
                recs.append((name, kind, mode, zi.file_size))
        else:
            for ti in self.tf.getmembers():
                name = normalize_member_name(ti.name)
                if name in ("", "."):
                    if not ti.isdir():
                        recs.append((ti.name, "other", ti.mode, ti.size))
                    continue
                if ti.isdir():
                    kind = "dir"
                elif ti.isreg():
                    kind = "file"
                elif ti.issym():
                    kind = "symlink"
                elif ti.islnk():
                    kind = "link"
                else:
                    kind = "other"
                self._members[name] = ti
                recs.append((name, kind, ti.mode, ti.size))
        return recs

    def read(self, name, limit=None):
        member = self._members[name]
        if self.is_zip:
            with self.zf.open(member) as f:
                return f.read(-1 if limit is None else limit)
        f = self.tf.extractfile(member)
        return f.read(-1 if limit is None else limit) if f else b""

    def extract_to(self, dest):
        if self.is_zip:
            self.zf.extractall(dest)
            # zipfile does not restore permissions
            for zi in self.zf.infolist():
                mode_bits = zi.external_attr >> 16 if zi.create_system == 3 else 0
                if mode_bits and not zi.filename.endswith("/"):
                    os.chmod(os.path.join(dest, zi.filename), stat.S_IMODE(mode_bits))
        elif hasattr(tarfile, "data_filter"):
            self.tf.extractall(dest, filter="data")
        else:
            self.tf.extractall(dest)  # names were checked by check_entries first


def infer_platform(reader, records):
    if reader.is_zip:
        return "windows"
    for name in BINARIES:
        if any(r[0] == name and r[1] == "file" for r in records):
            fmt = binary_format_bytes(reader.read(name, 4096))
            if fmt.startswith("elf"):
                return "linux"
            if "arm64" in fmt and "x86_64" not in fmt:
                return "macos-arm"
            if fmt.startswith("macho"):
                return "macos-intel"
    return "linux"


def verify_archive(path, platform, games, extract_test, verbose):
    """Read an archive back, re-run every check, optionally extract it.
    Returns (errors, records, platform)."""
    reader = ArchiveReader(path)
    try:
        records = reader.records()
        if platform is None:
            platform = infer_platform(reader, records)
        if verbose:
            for name, kind, mode, size in sorted(records, key=lambda r: sort_key(r[0])):
                info("  {:<4} {:>4} {:>10}  {}".format(
                    kind[:4], "" if mode is None else "{:o}".format(mode), size, name))
        errors = check_entries(records, platform, games, reader.read)
        if not errors and extract_test:
            with tempfile.TemporaryDirectory(prefix="coop-mod-check-") as tmp:
                reader.extract_to(tmp)
                root = Path(tmp)
                exe = PLATFORMS[platform][0]
                for b in BINARIES:
                    p = root / (b + exe)
                    if not p.is_file():
                        errors.append("after extraction: {} is missing".format(p.name))
                    elif os.name == "posix" and platform != "windows" and not os.access(p, os.X_OK):
                        errors.append("after extraction: {} is not executable".format(p.name))
                if not (root / "data").is_dir():
                    errors.append("after extraction: data/ is not next to the binaries")
                count = sum(len(files) for _, _, files in os.walk(root))
                expected = sum(1 for r in records if r[1] == "file")
                if count != expected:
                    errors.append("after extraction: {} files, expected {}".format(count, expected))
        return errors, records, platform
    finally:
        reader.close()


# --------------------------------------------------------------------------------------------------
# Metadata
# --------------------------------------------------------------------------------------------------


def emit_metadata(repo, out_dir, version, games):
    """Run the release pipeline's own emit-metadata.py, then check the result against the schema."""
    script = repo / ".github" / "scripts" / "create-mod-release" / "emit-metadata.py"
    env = dict(os.environ)
    env.update({
        "SCHEMA_VERSION": METADATA_SCHEMA_VERSION,
        "VERSION": version,
        "SUPPORTED_GAMES": ",".join(games),
        "OUT_DIR": str(out_dir),
    })
    proc = subprocess.run([sys.executable, str(script)], env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        raise PackageError("emit-metadata.py failed:\n" + proc.stdout.decode(errors="replace"))
    path = out_dir / "metadata.json"
    with open(path, encoding="utf-8") as f:
        meta = json.load(f)
    schema_path = repo / ".github" / "schemas" / "mods" / "v2" / "mod-schema.v2.json"
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)["definitions"]["ModMetadata"]
    problems = [k for k in schema["required"] if k not in meta]
    problems += [k for k in meta if k not in schema["properties"]]
    for key in ("schemaVersion", "version"):
        if key in meta and not re.match(schema["properties"][key]["pattern"], meta[key]):
            problems.append("{}={!r} is not semver".format(key, meta[key]))
    allowed = schema["properties"]["supportedGames"]["items"]["enum"]
    problems += ["game {!r}".format(g) for g in meta.get("supportedGames", []) if g not in allowed]
    if problems:
        raise PackageError("metadata.json does not match the schema: " + "; ".join(problems))
    return path


# --------------------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------------------


def host_platform():
    if sys.platform.startswith("win") or sys.platform == "cygwin":
        return "windows"
    if sys.platform == "darwin":
        return None  # decided from the binaries (Intel or Apple Silicon)
    return "linux"


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Package a local build of this fork as an OpenGOAL Launcher mod archive "
        "(same layout as the GitHub release assets).",
        epilog="See docs/splitscreen/MOD.md.",
    )
    p.add_argument("--platform", choices=sorted(PLATFORMS), help="target platform (default: this host)")
    p.add_argument("--bin-dir", type=Path,
                   help="folder with the built binaries: a CMake build folder (game/gk, goalc/goalc, "
                   "decompiler/extractor) or a flat bin folder (gk.exe, ...). Default: auto-detect")
    p.add_argument("--repo", type=Path, help="jak-project checkout (default: the one holding this script)")
    p.add_argument("--out-dir", type=Path, help="output folder (default: <repo>/build/coop-mod)")
    p.add_argument("--name", default=DEFAULT_NAME,
                   help="archive name without extension (default: %(default)s). The launcher uses it "
                   "as the mod name and the settings/save folder name, so keep it the same between builds")
    p.add_argument("--release-name", action="store_true",
                   help="name the archive like the GitHub release asset: <platform>-<version>")
    p.add_argument("--version", help="version, e.g. v0.1.0 (default: the tag on HEAD, else v0.0.0-local.g<sha>)")
    p.add_argument("--games", default="jak1", help="supported games for metadata.json (default: %(default)s)")
    p.add_argument("--emit-metadata", action="store_true",
                   help="also write metadata.json next to the archive (as the release does)")
    p.add_argument("--strip", choices=["auto", "on", "off"], default="auto",
                   help="strip copies of the binaries like CI does (default: auto, when 'strip' exists)")
    p.add_argument("--allow-dynamic", action="store_true",
                   help="package a dynamically linked Linux/macOS build anyway (works only on this "
                   "machine while the build folder exists)")
    p.add_argument("--dry-run", action="store_true", help="run all checks, write nothing")
    p.add_argument("--check", type=Path, metavar="ARCHIVE",
                   help="only verify an existing archive (yours or a release asset)")
    p.add_argument("--verbose", "-v", action="store_true", help="list every archive entry")
    return p.parse_args(argv)


def parse_games(text):
    games = [g.strip() for g in text.split(",") if g.strip()]
    bad = [g for g in games if g not in SUPPORTED_GAMES]
    if not games or bad:
        raise PackageError("--games must be a comma-separated list of " + "|".join(SUPPORTED_GAMES))
    return games


def run_check(args):
    games = parse_games(args.games)
    if not args.check.is_file():
        raise PackageError("{} does not exist".format(args.check))
    errors, records, platform = verify_archive(args.check, args.platform, games, True, args.verbose)
    files = sum(1 for r in records if r[1] == "file")
    info("{}: {} entries ({} files), platform {}".format(args.check, len(records), files, platform))
    if errors:
        for e in errors[:50]:
            info("  ERROR: " + e)
        raise PackageError("{} problem(s) found in {}".format(len(errors), args.check))
    info("OK: only allowed paths, binaries at the root, data/ next to them.")
    return 0


def run_package(args):
    repo = find_repo(args.repo)
    games = parse_games(args.games)
    sha, epoch, tag = git_head_info(repo)

    # binaries
    if args.bin_dir:
        bin_dir = args.bin_dir if args.bin_dir.is_absolute() else Path.cwd() / args.bin_dir
    else:
        bin_dir = None
    platform = args.platform or host_platform()
    if platform is None:  # macOS host: Intel or Apple Silicon build?
        probe = bin_dir or detect_bin_dir(repo, "macos-intel")
        gk = find_binary(probe, "gk", "")
        fmt = binary_format(gk) if gk else ""
        platform = "macos-arm" if fmt == "macho-arm64" else "macos-intel"
    exe, ext, fmt_expected = PLATFORMS[platform]
    if bin_dir is None:
        bin_dir = detect_bin_dir(repo, platform)
    bin_dir = bin_dir.resolve()

    errors = []
    binaries = {}
    for name in BINARIES:
        path = find_binary(bin_dir, name, exe)
        if path is None:
            errors.append("{} not found in {} (looked for {}/{}{} and {}{})".format(
                name, bin_dir, BINARY_SUBDIR[name], name, exe, name, exe))
            continue
        if path.stat().st_size == 0:
            errors.append("{} is empty".format(path))
        fmt = binary_format(path)
        if not format_matches(fmt, fmt_expected):
            errors.append("{}: {} binary, expected {} for --platform {}".format(
                path, fmt, fmt_expected, platform))
        if os.name == "posix" and platform != "windows" and not os.access(path, os.X_OK):
            errors.append("{} is not executable".format(path))
        binaries[name] = path
    if errors:
        raise PackageError("\n  ".join(["binaries:"] + errors))

    verdict, notes = assess_portability(platform, bin_dir, binaries)
    _, cache = read_cmake_cache(bin_dir)
    build_type = cache.get("CMAKE_BUILD_TYPE")

    # version and names
    version = args.version or (tag if tag and SEMVER_RE.match(tag[1:] if tag.startswith("v") else tag) else "")
    status = git_status(repo, [t for t, _ in DATA_TREES] + [f for f, _ in DATA_FILES])
    dirty = any(code != "??" for code, _ in status)
    if not version:
        version = "v0.0.0-local.g{}{}".format(sha, ".dirty" if dirty else "")
    if not version.startswith("v"):
        version = "v" + version
    if not SEMVER_RE.match(version[1:]):
        raise PackageError("--version {!r} is not a semantic version like v1.2.3".format(version))
    if args.release_name:
        stem = "{}-{}".format(platform, version)
    else:
        stem = args.name
        if not NAME_RE.match(stem) or stem.lower() == "_settings":
            raise PackageError("--name may only use letters, digits, '-' and '_' and must not be _settings")
    out_dir = (args.out_dir or repo / "build" / "coop-mod").resolve()
    archive = out_dir / (stem + ext)

    info("Repository : {} (HEAD {}{})".format(repo, sha, ", tracked changes in packaged folders" if dirty else ""))
    info("Platform   : {}".format(platform))
    info("Binaries   : {} (build type {}, linking {})".format(bin_dir, build_type or "unknown", verdict))
    for n in notes:
        info("             " + n)
    info("Version    : {}".format(version))

    untracked = [p for code, p in status if code == "??"]
    if untracked:
        warn("{} untracked file(s) in packaged folders are NOT included (git add them if the mod "
             "needs them), e.g. {}".format(len(untracked), ", ".join(untracked[:5])))
    if dirty:
        warn("packaged folders have uncommitted changes; they are included as they are on disk")
    if build_type and build_type != "Release":
        warn("CMAKE_BUILD_TYPE is {}, the release pipeline uses Release".format(build_type))

    if verdict == "dynamic":
        hint = "Build the static preset instead:\n    " + STATIC_BUILD_HINT[platform]
        if platform == "windows":
            raise PackageError("this build is dynamically linked: its DLLs are not part of the mod "
                               "layout, so the packaged gk.exe would not start. {}".format(hint))
        problem = ("this build is dynamically linked: the archive would only run on this machine, and "
                   "only while {} exists".format(bin_dir))
        if not args.allow_dynamic:
            raise PackageError("{}. {}\nor pass --allow-dynamic for a package you only use on this "
                               "machine".format(problem, hint))
        warn(problem + ". Do not share this archive.")
    elif verdict == "unknown":
        warn("could not tell whether the build is statically linked (no CMakeCache.txt found)")

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with tempfile.TemporaryDirectory(prefix="coop-mod-") as tmp:
        staged_bins = binaries if args.dry_run else maybe_strip(binaries, platform, args.strip, tmp)
        entries, plan_errors = build_plan(repo, platform, staged_bins, version, timestamp)

        records = plan_records(entries)
        files = [e for e in entries if not e.is_dir]
        content = {e.name: e for e in files}
        plan_errors += check_entries(records, platform, games, lambda n, limit: content[n].read(limit))
        if plan_errors:
            for e in plan_errors[:50]:
                info("  ERROR: " + e)
            raise PackageError("{} problem(s) with the files to package; nothing was written".format(
                len(plan_errors)))
        total = sum(e.size() for e in files)
        info("Contents   : {} files + {} folders, {:.1f} MB uncompressed".format(
            len(files), len(entries) - len(files), total / (1 << 20)))
        if args.verbose:
            for e in entries:
                info("  {}{}".format(e.name, "/" if e.is_dir else ""))

        if args.dry_run:
            info("")
            info("Dry run: all checks passed, would write {}".format(archive))
            return 0

        out_dir.mkdir(parents=True, exist_ok=True)
        partial = out_dir / ".{}.partial{}".format(stem, ext)
        try:
            if ext == ".zip":
                write_zip(entries, partial, epoch)
            else:
                write_tar_gz(entries, partial, epoch)
            errors, read_back, _ = verify_archive(partial, platform, games, True, False)
            if not errors and len(read_back) != len(records):
                errors.append("archive has {} entries, expected {}".format(len(read_back), len(records)))
            if errors:
                for e in errors[:50]:
                    info("  ERROR: " + e)
                raise PackageError("the written archive failed verification; it was deleted")
            os.replace(partial, archive)
        finally:
            if partial.exists():
                partial.unlink()

    digest = hashlib.sha256()
    with open(archive, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    sha_path = archive.with_name(archive.name + ".sha256")
    sha_path.write_text("{}  {}\n".format(digest.hexdigest(), archive.name), encoding="utf-8")
    meta_path = emit_metadata(repo, out_dir, version, games) if args.emit_metadata else None

    mod_name = stem
    info("")
    info("Wrote {} ({:.1f} MB)".format(archive, archive.stat().st_size / (1 << 20)))
    info("      {}".format(sha_path))
    if meta_path:
        info("      {}".format(meta_path))
    info("Verified: only allowed paths, binaries at the root, data/ next to them,")
    info("          extracted cleanly into a temporary folder.")
    info("")
    info("Add it in the OpenGOAL Launcher:")
    info("  1. Install the official Jak 1 in the launcher first (the mod reuses its extracted disc files).")
    info("  2. Select Jak 1, then Features > Mods > Add from File, and pick")
    info("     {}".format(archive))
    info("  3. The launcher names the mod '{}' and decompiles and compiles the game for it (this".format(mod_name))
    info("     takes a while). Then open the mod in the Mods list and press Play.")
    info("  4. In game: Options > Game Options > Misc Options > Local co-op.")
    info("Settings and saves: <launcher install folder>/features/jak1/mods/_local/_settings/{}/OpenGOAL/jak1/".format(
        mod_name))
    info("(co-op saves in saves/coop/). Re-adding a newer archive with the same name keeps them.")
    return 0


def main(argv=None):
    if sys.version_info < (3, 9):
        print("ERROR: Python 3.9 or newer is required", file=sys.stderr)
        return 2
    args = parse_args(argv)
    try:
        if args.check:
            return run_check(args)
        return run_package(args)
    except PackageError as e:
        print("ERROR: {}".format(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
