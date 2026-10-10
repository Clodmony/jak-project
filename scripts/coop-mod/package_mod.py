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
    custom_assets/*/texture_replacements/* or anything extracted from a disc never are. Files that
    are staged but not committed, untracked files and deleted tracked files in the packaged folders
    stop the run unless --allow-uncommitted is given; this is the main guard against packaging
    something by accident.
  - Every entry is also checked against an allow list and a best-effort deny list (disc and game
    file names and types, saves, settings, keys) before and after writing, and the custom assets
    that game.gp builds must be present.
  - The binaries are checked: built after their C/C++ sources last changed (else rebuild or
    --allow-stale), and, read from the executables themselves, linked only against system
    libraries. A build that only runs on this machine (dynamically linked against libraries in the
    build folder) is refused unless --allow-dynamic is given (Linux and macOS only). On Linux the
    minimum glibc and libstdc++ versions the binaries need are printed.

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
import zlib
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

# how to make a static build in the folder that the auto-detection looks at first. One command per
# line: Windows PowerShell 5.1 does not accept '&&'.
STATIC_BUILD_HINT = {
    "linux": ["cmake --preset=Release-linux-clang-static", "cmake --build build/Release/bin"],
    "windows": ["cmake --preset=Release-windows-clang-static", "cmake --build out/build/Release"],
    "macos-intel": ["cmake --preset=Release-macos-x86_64-clang-static",
                    "cmake --build build/Release/bin"],
    "macos-arm": ["cmake --preset=Release-macos-arm64-clang-static", "cmake --build build/Release/bin"],
}

# C/C++ sources of each binary (git-tracked files below these folders with SOURCE_EXTENSIONS, plus
# CMakeLists.txt files), from the target_link_libraries calls in game/, goalc/ and decompiler/
# CMakeLists.txt: gk = runtime + common; goalc = compiler + decomp (+ sound); extractor = decomp +
# compiler (+ sound). Packaged data folders hold no such files.
BINARY_SOURCES = {
    "gk": ["game", "common", "third-party"],
    "goalc": ["goalc", "decompiler", "game/sound", "common", "third-party"],
    "extractor": ["decompiler", "goalc", "game/sound", "common", "third-party"],
}
SOURCE_EXTENSIONS = {
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".inl", ".ipp", ".asm", ".s", ".cmake",
}

# Ubuntu 22.04, where the release pipeline builds Linux (linux-build-clang.yaml `runs-on`): the
# newest glibc / libstdc++ symbol versions a Linux package may need to start on that system
LINUX_BASELINE = {"GLIBC": (2, 35), "GLIBCXX": (3, 4, 30)}

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
# Best effort only: the main guard is that only committed, git-tracked files are packaged.
# Extensions of disc images, game archives, compiled objects, audio, PS2 drivers and save files
# (.png, .glb and .txt are not here: the repository tracks such files in the packaged folders).
FORBIDDEN_EXTENSIONS = {
    ".iso", ".img", ".cue", ".bin", ".cgo", ".dgo", ".go", ".o", ".str", ".vag", ".sbk", ".mus",
    ".p2s", ".sav", ".gci", ".mcd", ".ps2", ".irx", ".cnf", ".ayb", ".wav", ".elf",
}
# File names from the game discs (decompiler/config/*/*/inputs.jsonc, *_config.jsonc): the
# streamed audio VAGWAD.<language>, TEXT/<n>COMMON.TXT / <n>SUBTIT.TXT and the boot ELF
# (SCUS_971.24, SCES_503.61, ...). Compared case-insensitively with the last path component.
FORBIDDEN_NAME_RE = re.compile(
    r"^vagwad\.[a-z]+$|^\d+[a-z]+\.txt$|^[a-z]{4}_\d{3}\.\d{2}$", re.IGNORECASE
)
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
        if FORBIDDEN_NAME_RE.match(parts[-1]):
            return "name of a game disc file"
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


def head_files(repo, trees):
    """Paths of the files committed in HEAD below `trees`."""
    out = git(repo, "ls-tree", "-r", "-z", "--name-only", "HEAD", "--", *trees).stdout
    return {p for p in out.decode("utf-8").split("\0") if p}


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
    """Pick a build from the default places. Returns (folder, candidates) with candidates a list of
    (folder, CMake cache says static, gk modification time), the chosen one first: a static build
    first (the only kind that can be shared), then the newest gk. The cache only reflects the last
    configure; the binaries themselves are checked later."""
    exe = PLATFORMS[platform][0]
    found = []
    for cand in candidate_bin_dirs(repo, platform):
        gk = find_binary(cand, "gk", exe) if cand.is_dir() else None
        if gk:
            _, cache = read_cmake_cache(cand)
            found.append((cand, cmake_bool(cache.get("STATICALLY_LINK")) is True, gk.stat().st_mtime))
    if not found:
        raise PackageError(
            "no build found in {}; build first or pass --bin-dir".format(
                ", ".join(str(c) for c in candidate_bin_dirs(repo, platform))
            )
        )
    found.sort(key=lambda f: (f[1], f[2]), reverse=True)
    return found[0][0], found


def fmt_time(epoch):
    return datetime.datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M:%S")


def stale_sources(repo, binaries):
    """{binary name: [(mtime, path), ...] newest first} of the git-tracked C/C++ and CMake files
    that changed after that binary was linked: the rule make and ninja use to decide on a rebuild.
    (`gk --version` cannot tell: common/CMakeLists.txt writes the revision at configure time.)"""
    roots = sorted({r for rs in BINARY_SOURCES.values() for r in rs})
    out = git(repo, "ls-files", "-z", "--", "CMakeLists.txt", *roots).stdout.decode("utf-8")
    sources = []
    for path in out.split("\0"):
        base = path.rsplit("/", 1)[-1]
        if not path or (base != "CMakeLists.txt"
                        and os.path.splitext(base)[1].lower() not in SOURCE_EXTENSIONS):
            continue
        try:
            sources.append((path, (repo / path).stat().st_mtime))
        except OSError:
            continue  # deleted in the working tree
    result = {}
    for name, bin_path in binaries.items():
        built = bin_path.stat().st_mtime
        prefixes = tuple(r + "/" for r in BINARY_SOURCES[name])
        newer = sorted(
            ((m, p) for p, m in sources
             if m > built and (p == "CMakeLists.txt" or p.startswith(prefixes))),
            reverse=True,
        )
        if newer:
            result[name] = newer
    return result


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


def c_string(data, start, end=None):
    end = len(data) if end is None else min(end, len(data))
    stop = data.find(b"\0", start, end)
    return data[start:stop if stop >= 0 else end].decode("utf-8", errors="replace")


def elf_dynamic_info(data):
    """(needed libraries, runpath entries, [(library, symbol version)]) of a 64-bit little-endian
    ELF image, e.g. (['libc.so.6'], [], [('libc.so.6', 'GLIBC_2.34')]). Empty for a fully static
    binary."""
    if len(data) < 64 or data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        return [], [], []
    phoff = struct.unpack_from("<Q", data, 32)[0]
    phentsize, phnum = struct.unpack_from("<HH", data, 54)
    loads, dynamic = [], None
    for i in range(phnum):
        off = phoff + i * phentsize
        if off + 40 > len(data):
            break
        p_type, _, p_offset, p_vaddr, _, p_filesz = struct.unpack_from("<IIQQQQ", data, off)
        if p_type == 1:
            loads.append((p_vaddr, p_offset, p_filesz))
        elif p_type == 2:
            dynamic = (p_offset, p_filesz)
    if dynamic is None:
        return [], [], []

    def to_offset(addr):
        for vaddr, offset, size in loads:
            if vaddr <= addr < vaddr + size:
                return addr - vaddr + offset
        return None

    needed, runpaths, tags = [], [], {}
    for off in range(dynamic[0], min(dynamic[0] + dynamic[1], len(data)) - 15, 16):
        tag, val = struct.unpack_from("<qQ", data, off)
        if tag == 0:
            break
        if tag == 1:  # DT_NEEDED
            needed.append(val)
        elif tag in (15, 29):  # DT_RPATH, DT_RUNPATH
            runpaths.append(val)
        else:
            tags[tag] = val
    strtab = to_offset(tags[5]) if 5 in tags else None  # DT_STRTAB
    if strtab is None:
        return [], [], []

    versions = []  # .gnu.version_r: DT_VERNEED / DT_VERNEEDNUM
    off = to_offset(tags[0x6FFFFFFE]) if 0x6FFFFFFE in tags else None
    count = tags.get(0x6FFFFFFF, 0)
    while off is not None and count > 0 and off + 16 <= len(data):
        _, vn_cnt, vn_file, vn_aux, vn_next = struct.unpack_from("<HHIII", data, off)
        lib = c_string(data, strtab + vn_file)
        aux = off + vn_aux
        for _ in range(vn_cnt):
            if aux + 16 > len(data):
                break
            _, _, _, vna_name, vna_next = struct.unpack_from("<IHHII", data, aux)
            versions.append((lib, c_string(data, strtab + vna_name)))
            if not vna_next:
                break
            aux += vna_next
        count -= 1
        if not vn_next:
            break
        off += vn_next

    rp = []
    for v in runpaths:
        rp.extend(x for x in c_string(data, strtab + v).split(":") if x)
    return [c_string(data, strtab + v) for v in needed], rp, versions


def max_symbol_versions(versions):
    """Highest GLIBC_ and GLIBCXX_ version in [(library, version)], e.g.
    {'GLIBC': (2, 38), 'GLIBCXX': (3, 4, 32)}."""
    best = {}
    for _, ver in versions:
        m = re.match(r"^(GLIBC|GLIBCXX)_(\d+(?:\.\d+)*)$", ver)
        if m:
            t = tuple(int(x) for x in m.group(2).split("."))
            if t > best.get(m.group(1), ()):
                best[m.group(1)] = t
    return best


def version_text(t):
    return ".".join(str(x) for x in t)


def pe_imports(data):
    """Names of the DLLs a PE image imports, normal and delay-loaded, as written in the file;
    None if it is not a PE image."""
    if len(data) < 0x40 or data[:2] != b"MZ":
        return None
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if pe + 24 > len(data) or data[pe:pe + 4] != b"PE\0\0":
        return None
    nsections = struct.unpack_from("<H", data, pe + 6)[0]
    opt_size = struct.unpack_from("<H", data, pe + 20)[0]
    opt = pe + 24
    magic = struct.unpack_from("<H", data, opt)[0]
    if magic == 0x20B:  # PE32+
        image_base = struct.unpack_from("<Q", data, opt + 24)[0]
        dirs = opt + 112
    elif magic == 0x10B:  # PE32
        image_base = struct.unpack_from("<I", data, opt + 28)[0]
        dirs = opt + 96
    else:
        return None
    ndirs = struct.unpack_from("<I", data, dirs - 4)[0]
    sections = []
    for i in range(nsections):
        s = opt + opt_size + 40 * i
        if s + 40 > len(data):
            break
        vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, s + 8)
        sections.append((vaddr, max(vsize, rawsize), rawptr))

    def to_offset(rva):
        for vaddr, size, rawptr in sections:
            if vaddr <= rva < vaddr + size:
                return rva - vaddr + rawptr
        return None

    names = []
    # directory 1: IMAGE_IMPORT_DESCRIPTOR (20 bytes, name RVA at +12);
    # directory 13: delay-load descriptor (32 bytes, attributes at +0, name at +4)
    for index, size, name_at in ((1, 20, 12), (13, 32, 4)):
        if index >= ndirs:
            continue
        rva = struct.unpack_from("<I", data, dirs + 8 * index)[0]
        off = to_offset(rva) if rva else None
        while off is not None and off + size <= len(data) and len(names) < 1000:
            if data[off:off + size] == b"\0" * size:
                break
            name = struct.unpack_from("<I", data, off + name_at)[0]
            if index == 13 and not struct.unpack_from("<I", data, off)[0] & 1:
                name -= image_base  # old-style delay-load descriptors hold addresses, not RVAs
            name_off = to_offset(name)
            if name_off is not None:
                names.append(c_string(data, name_off, name_off + 260))
            off += size
    return names


MACHO_CPU = {"macho-x86_64": 0x01000007, "macho-arm64": 0x0100000C}


def macho_dylibs(data, expected):
    """(dylibs, rpaths) from the load commands of a Mach-O image (the `expected` slice of a
    universal binary), or None if it is not one."""
    if data[:4] == b"\xca\xfe\xba\xbe":
        count = struct.unpack_from(">I", data, 4)[0]
        for i in range(min(count, 16)):
            cpu, _, offset, size, _ = struct.unpack_from(">IIIII", data, 8 + 20 * i)
            if cpu == MACHO_CPU.get(expected):
                return macho_dylibs(data[offset:offset + size], expected)
        return None
    if len(data) < 32 or data[:4] != b"\xcf\xfa\xed\xfe":
        return None
    ncmds = struct.unpack_from("<I", data, 16)[0]
    off, dylibs, rpaths = 32, [], []
    # LC_LOAD_DYLIB, LC_LOAD_WEAK_DYLIB, LC_REEXPORT_DYLIB, LC_LAZY_LOAD_DYLIB, LC_LOAD_UPWARD_DYLIB
    dylib_cmds = {0xC, 0x80000018, 0x8000001F, 0x20, 0x80000023}
    for _ in range(ncmds):
        if off + 12 > len(data):
            break
        cmd, cmdsize = struct.unpack_from("<II", data, off)
        if cmd in dylib_cmds or cmd == 0x8000001C:  # LC_RPATH
            name_at = struct.unpack_from("<I", data, off + 8)[0]
            text = c_string(data, off + name_at, off + cmdsize)
            (rpaths if cmd == 0x8000001C else dylibs).append(text)
        if cmdsize < 8:
            break
        off += cmdsize
    return dylibs, rpaths


# libraries every Linux desktop has; anything else would have to ship next to the binaries.
# (A static build still links these dynamically; gk also needs libz when CMake found a system zlib.)
SYSTEM_LIB_RE = re.compile(
    r"^(libc|libm|libdl|librt|libpthread|libresolv|libutil|libz|libstdc\+\+|libgcc_s)\.so(\.\d+)*$"
    r"|^ld-linux[-\w.]*\.so(\.\d+)*$"
)
# DLLs that come with Windows (plus the API sets). A DLL outside this list is only reported: the
# list is not complete, and the build folder check below is what refuses a dynamic build.
WINDOWS_SYSTEM_DLLS = {
    "kernel32.dll", "kernelbase.dll", "ntdll.dll", "user32.dll", "gdi32.dll", "advapi32.dll",
    "shell32.dll", "ole32.dll", "oleaut32.dll", "comdlg32.dll", "comctl32.dll", "ws2_32.dll",
    "wsock32.dll", "crypt32.dll", "bcrypt.dll", "ncrypt.dll", "secur32.dll", "winmm.dll",
    "imm32.dll", "version.dll", "setupapi.dll", "cfgmgr32.dll", "dbghelp.dll", "shlwapi.dll",
    "opengl32.dll", "dwmapi.dll", "uxtheme.dll", "hid.dll", "wldap32.dll", "normaliz.dll",
    "iphlpapi.dll", "userenv.dll", "winhttp.dll", "wininet.dll", "dinput8.dll", "xinput1_4.dll",
    "xinput9_1_0.dll", "dxgi.dll", "d3d11.dll", "d3d12.dll", "dsound.dll", "propsys.dll",
    "powrprof.dll", "psapi.dll", "rpcrt4.dll", "combase.dll", "msvcrt.dll", "ucrtbase.dll",
    "shcore.dll", "winusb.dll", "mfplat.dll", "mfreadwrite.dll", "mf.dll", "avrt.dll",
}


def shorten(items, keep=3):
    if len(items) <= keep:
        return ", ".join(items)
    return "{} and {} more".format(", ".join(items[:keep]), len(items) - keep)


VERDICT_TEXT = {
    "static": "static build (needs no libraries from the build)",
    "dynamic": "needs libraries that are not part of the package (dynamic build)",
    "unknown": "could not be determined",
}


def assess_portability(platform, images, folder_files=None, cache=None):
    """Judge from the binaries themselves which libraries they need.
    images: {name: bytes}; folder_files: {name: lower-case file names next to that binary} when
    packaging from a build folder; cache: CMakeCache values (only used when the binaries cannot
    be read). Returns (verdict, notes, warnings, requirements): verdict is 'static' (only system
    libraries), 'dynamic' or 'unknown'; requirements the highest GLIBC/GLIBCXX versions (Linux)."""
    notes, warnings, requirements = [], [], {}
    verdict = None
    exe = PLATFORMS[platform][0]
    for name in BINARIES:
        img = images.get(name)
        if img is None:
            continue
        label = name + exe
        try:
            parsed = (elf_dynamic_info(img) if platform == "linux" else pe_imports(img)
                      if platform == "windows" else macho_dylibs(img, PLATFORMS[platform][2]))
        except (struct.error, IndexError, ValueError):
            parsed = None
        if parsed is None:
            continue
        if platform == "linux":
            needed, runpath, versions = parsed
            for key, value in max_symbol_versions(versions).items():
                requirements[key] = max(requirements.get(key, ()), value)
            odd = [lib for lib in needed if not SYSTEM_LIB_RE.match(lib)]
            abs_rp = [r for r in runpath if not r.startswith("$ORIGIN")]
            if odd or abs_rp:
                verdict = "dynamic"
                notes.append("{} needs {} (RUNPATH {})".format(
                    label, shorten(odd) or "only system libraries", shorten(abs_rp) or "none"))
            elif verdict is None:
                verdict = "static"
        elif platform == "windows":
            imports = parsed
            local = [d for d in imports if folder_files and d.lower() in folder_files.get(name, ())]
            other = [d for d in imports if d not in local and d.lower() not in WINDOWS_SYSTEM_DLLS
                     and not re.match(r"^(api|ext)-ms-", d, re.IGNORECASE)]
            if local:
                verdict = "dynamic"
                notes.append("{} imports {} from its build folder".format(label, shorten(local, 6)))
            elif verdict is None:
                verdict = "static"
            if other:
                warnings.append("{} imports {}, which is neither in the package nor a known Windows "
                                "system DLL; it must exist on every machine that runs the mod"
                                .format(label, shorten(other, 6)))
        else:
            dylibs, rpaths = parsed
            odd = [d for d in dylibs if not d.startswith(("/usr/lib/", "/System/Library/"))]
            if odd:
                verdict = "dynamic"
                rp = " (LC_RPATH {})".format(shorten(rpaths)) if rpaths else ""
                notes.append("{} loads {}{}".format(label, shorten(odd, 4), rp))
            elif verdict is None:
                verdict = "static"
    if verdict is None:
        static = cmake_bool((cache or {}).get("STATICALLY_LINK"))
        verdict = {True: "static", False: "dynamic", None: "unknown"}[static]
        if static is not None:
            notes.append("from CMakeCache.txt only (STATICALLY_LINK), the binaries could not be read")
    return verdict, notes, warnings, requirements


def requirement_lines(requirements):
    """(info line, warning or None) about the glibc/libstdc++ versions a Linux build needs."""
    if not requirements:
        return None, None
    parts = []
    if "GLIBC" in requirements:
        parts.append("glibc {}".format(version_text(requirements["GLIBC"])))
    if "GLIBCXX" in requirements:
        parts.append("libstdc++ with GLIBCXX_{}".format(version_text(requirements["GLIBCXX"])))
    line = "needs at least " + " and ".join(parts) + " on the target system"
    newer = [k for k, v in requirements.items() if k in LINUX_BASELINE and v > LINUX_BASELINE[k]]
    if not newer:
        return line, None
    return line, (
        "the binaries need a newer {} than Ubuntu 22.04 has (glibc {}, GLIBCXX_{}; the release "
        "pipeline builds there), so they will not start on Ubuntu 22.04, Debian 12 or older "
        "distributions. Fine for this machine; for other people share the GitHub release asset or "
        "build in an ubuntu:22.04 container".format(
            " and ".join("glibc" if k == "GLIBC" else "libstdc++" for k in sorted(newer)),
            version_text(LINUX_BASELINE["GLIBC"]), version_text(LINUX_BASELINE["GLIBCXX"])))


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


def list_data_files(repo):
    """(files, missing, errors): files is [(path, git mode, archive path)] of every git-tracked file
    in the packaged folders that exists on disk, missing the tracked paths deleted in the working
    tree (or outside a sparse checkout)."""
    files, missing, errors = [], [], []
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
    present = []
    for path, mode, dst in files:
        if mode not in ("120000", "160000") and not os.path.lexists(repo / path):
            missing.append(path)
        else:
            present.append((path, mode, dst))
    return present, missing, errors


def build_plan(repo, files, binaries, platform, version, timestamp):
    errors, entries = [], []
    exe = PLATFORMS[platform][0]
    for name in BINARIES:
        entries.append(Entry(name + exe, source=binaries[name], mode=0o755))

    for path, mode, dst in files:
        if mode in ("120000", "160000"):
            errors.append("{} is a symlink or submodule in git".format(path))
            continue
        full = repo / path
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


# Files that game.gp compiles from custom_assets (macros in goal_src/jak1/game.gp:157-235 and
# goal_src/jak{2,3,x}/lib/project-lib.gp) and literal `:in "..."` inputs. {g} is the game, {0} the
# string in game.gp. Without them the launcher's compile step fails ("Input file ... does not exist").
GAME_GP_INPUTS = [
    (re.compile(r'\(build-custom-level\s+"([^"]+)"'), "data/custom_assets/{g}/levels/{0}/{0}.jsonc"),
    (re.compile(r'\(custom-level-cgo\s+"[^"]*"\s+"([^"]+)"'), "data/custom_assets/{g}/levels/{0}"),
    (re.compile(r'\(build-actor\s+"([^"]+)"'), "data/custom_assets/{g}/models/custom_levels/{0}.glb"),
    (re.compile(r'\(custom-actor-cgo\s+"[^"]*"\s+"([^"]+)"'), "data/custom_assets/{g}/models/{0}"),
    (re.compile(r':in\s+"((?:custom_assets|game/assets|decompiler/config|goal_src)/[^"]+)"'), "data/{0}"),
]


def strip_goal_comments(text):
    """GOAL/GOOS source without #| block |# and ; line comments (strings and #\\x characters
    are kept)."""
    text = re.sub(r"#\|.*?\|#", "", text, flags=re.DOTALL)
    out, i, n, in_string = [], 0, len(text), False
    while i < n:
        ch = text[i]
        if in_string:
            if ch == "\\":
                out.append(text[i:i + 2])
                i += 2
                continue
            in_string = ch != '"'
        elif ch == '"':
            in_string = True
        elif ch == "#" and text.startswith("#\\", i):
            out.append(text[i:i + 3])
            i += 3
            continue
        elif ch == ";":
            nl = text.find("\n", i)
            i = n if nl < 0 else nl
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def game_gp_inputs(game, text):
    """Archive paths of the input files that `game`'s game.gp names explicitly."""
    text = strip_goal_comments(text)
    found = set()
    for pattern, template in GAME_GP_INPUTS:
        for m in pattern.finditer(text):
            found.add(template.format(m.group(1), g=game))
    return sorted(found)


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
    if content_reader is not None:
        for g in games:
            gp = "data/goal_src/{}/game.gp".format(g)
            if by_name.get(gp, (None,))[0] != "file":
                continue
            text = content_reader(gp, None).decode("utf-8", errors="replace")
            for r in game_gp_inputs(g, text):
                if by_name.get(r, (None,))[0] != "file":
                    errors.append("missing file that {} compiles: {}".format(gp, r))
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


# what a truncated, corrupt or mislabelled archive raises while it is read
ARCHIVE_READ_ERRORS = (tarfile.TarError, zipfile.BadZipFile, EOFError, zlib.error, OSError)


def verify_archive(path, platform, games, extract_test, verbose):
    """Read an archive back, re-run every check, optionally extract it.
    Returns (errors, records, platform, images) with images {binary name: bytes}."""
    try:
        reader = ArchiveReader(path)
    except ARCHIVE_READ_ERRORS as e:
        raise PackageError("{} is not a readable {} archive: {}".format(
            path, "zip" if str(path).endswith(".zip") else ".tar.gz", e or type(e).__name__))
    try:
        records = reader.records()
        if platform is None:
            platform = infer_platform(reader, records)
        if verbose:
            for name, kind, mode, size in sorted(records, key=lambda r: sort_key(r[0])):
                info("  {:<4} {:>4} {:>10}  {}".format(
                    kind[:4], "" if mode is None else "{:o}".format(mode), size, name))
        errors = check_entries(records, platform, games, reader.read)
        exe = PLATFORMS[platform][0]
        names = {r[0] for r in records if r[1] == "file"}
        images = {b: reader.read(b + exe) for b in BINARIES if b + exe in names}
        if not errors and extract_test:
            with tempfile.TemporaryDirectory(prefix="coop-mod-check-") as tmp:
                reader.extract_to(tmp)
                root = Path(tmp)
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
        return errors, records, platform, images
    except ARCHIVE_READ_ERRORS as e:
        raise PackageError("{} could not be read (truncated or corrupt?): {}".format(
            path, e or type(e).__name__))
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
    p.add_argument("--allow-stale", action="store_true",
                   help="package binaries even though C/C++ sources changed after they were built")
    p.add_argument("--allow-uncommitted", action="store_true",
                   help="package even though the packaged folders have staged-but-uncommitted, "
                   "untracked or deleted files (staged files are included, the others left out)")
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
    errors, records, platform, images = verify_archive(
        args.check, args.platform, games, True, args.verbose)
    files = sum(1 for r in records if r[1] == "file")
    info("{}: {} entries ({} files), platform {}".format(args.check, len(records), files, platform))
    verdict, notes, warnings, requirements = assess_portability(platform, images)
    info("Linking: " + VERDICT_TEXT[verdict])
    for n in notes:
        info("         " + n)
    req_line, req_warning = requirement_lines(requirements) if platform == "linux" else (None, None)
    if req_line:
        info("Target : " + req_line)
    for w in warnings + ([req_warning] if req_warning else []):
        warn(w)
    if verdict == "dynamic":
        warn("this archive only runs where the libraries listed above exist (an --allow-dynamic "
             "package?); do not share it")
    if errors:
        for e in errors[:50]:
            info("  ERROR: " + e)
        raise PackageError("{} problem(s) found in {}".format(len(errors), args.check))
    info("OK: only allowed paths, binaries at the root, data/ next to them, custom assets that "
         "game.gp builds present.")
    return 0


def binaries_containing(binaries, path):
    """Names of the binaries whose bytes contain `path` (compiled-in source file names)."""
    text = str(path)
    needles = {text.encode("utf-8"), text.replace("\\", "/").encode("utf-8")}
    hits = []
    for name, p in binaries.items():
        with open(p, "rb") as f:
            data = f.read()
        if any(n in data for n in needles):
            hits.append(name)
    return hits


def run_package(args):
    repo = find_repo(args.repo)
    games = parse_games(args.games)
    sha, epoch, tag = git_head_info(repo)

    # binaries
    if args.bin_dir:
        bin_dir = args.bin_dir if args.bin_dir.is_absolute() else Path.cwd() / args.bin_dir
    else:
        bin_dir = None
    candidates = []
    platform = args.platform or host_platform()
    if platform is None:  # macOS host: Intel or Apple Silicon build?
        probe = bin_dir or detect_bin_dir(repo, "macos-intel")[0]
        gk = find_binary(probe, "gk", "")
        fmt = binary_format(gk) if gk else ""
        platform = "macos-arm" if fmt == "macho-arm64" else "macos-intel"
    exe, ext, fmt_expected = PLATFORMS[platform]
    if bin_dir is None:
        bin_dir, candidates = detect_bin_dir(repo, platform)
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

    images = {}
    for name, path in binaries.items():
        with open(path, "rb") as f:
            images[name] = f.read()
    folder_files = None
    if platform == "windows":
        folder_files = {name: {p.name.lower() for p in path.parent.iterdir()
                               if p.suffix.lower() == ".dll" and p.is_file()}
                        for name, path in binaries.items()}
    cache_path, cache = read_cmake_cache(bin_dir)
    build_type = cache.get("CMAKE_BUILD_TYPE")
    verdict, notes, port_warnings, requirements = assess_portability(
        platform, images, folder_files, cache)
    del images
    if cache_path:
        notes.append("CMake cache {}: STATICALLY_LINK={} (as of the last configure)".format(
            cache_path, cache.get("STATICALLY_LINK", "?")))
    build_root = cache_path.parent if cache_path else bin_dir
    gk_time = binaries["gk"].stat().st_mtime
    stale = stale_sources(repo, binaries)

    # git state of the packaged folders and of the sources the binaries were built from
    data_paths = [t for t, _ in DATA_TREES] + [f for f, _ in DATA_FILES]
    status = git_status(repo, data_paths)
    src_paths = sorted({r for rs in BINARY_SOURCES.values() for r in rs}) + ["CMakeLists.txt"]
    src_changed = [p for code, p in git_status(repo, src_paths) if code != "??"]
    files, missing, list_errors = list_data_files(repo)
    committed = head_files(repo, data_paths)
    new_files = sorted(p for p, _, _ in files if p not in committed)
    untracked = sorted(p for code, p in status if code == "??")
    modified = sorted({p for code, p in status
                       if code != "??" and p in committed and os.path.lexists(repo / p)})
    dirty = bool(modified or new_files or missing or src_changed)

    # version and names
    version = args.version or (tag if tag and SEMVER_RE.match(tag[1:] if tag.startswith("v") else tag) else "")
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

    info("Repository : {} (HEAD {}, committed {}{})".format(
        repo, sha, fmt_time(epoch), ", uncommitted changes" if dirty else ""))
    info("Platform   : {}".format(platform))
    info("Binaries   : {} (gk built {}, build type {})".format(
        bin_dir, fmt_time(gk_time), build_type or "unknown"))
    for cand, static, mtime in candidates[1:]:
        info("             also found: {} (gk built {}{})".format(
            cand, fmt_time(mtime), ", static" if static else ""))
    info("Linking    : {}".format(VERDICT_TEXT[verdict]))
    for n in notes:
        info("             " + n)
    req_line, req_warning = requirement_lines(requirements) if platform == "linux" else (None, None)
    if req_line:
        info("Target     : " + req_line)
    info("Version    : {}".format(version))

    blockers = list(list_errors)
    for cand, _, mtime in candidates[1:]:
        if mtime > gk_time:
            warn("{} has a newer gk (built {}) than the build being packaged. Rebuild this one "
                 "({}), or pass --bin-dir to choose".format(
                     cand, fmt_time(mtime), "cmake --build " + str(build_root)))
    if stale:
        lines = []
        for name, newer in stale.items():
            lines.append("{} (built {}) is older than {} of its source file(s), newest {} ({})".format(
                binaries[name].name, fmt_time(binaries[name].stat().st_mtime), len(newer),
                newer[0][1], fmt_time(newer[0][0])))
        if args.allow_stale:
            for line in lines:
                warn(line + "; packaging it anyway (--allow-stale)")
        else:
            blockers.append(
                "the binaries were built before their sources last changed, so they may not match "
                "the GOAL code that would be packaged:\n  " + "\n  ".join(lines)
                + "\nRebuild first:\n    cmake --build {}\nor pass --allow-stale.".format(build_root))
    if src_changed:
        warn("{} C/C++ source file(s) have uncommitted changes (the binaries may include them; the "
             "version is marked .dirty), e.g. {}".format(len(src_changed), shorten(src_changed, 3)))

    problems = []
    if new_files:
        problems.append("{} file(s) are staged but not committed (they would be included): {}".format(
            len(new_files), shorten(new_files, 8)))
    if untracked:
        problems.append("{} untracked file(s) would be left out (git add and commit them if the mod "
                        "needs them): {}".format(len(untracked), shorten(untracked, 8)))
    if missing:
        problems.append("{} tracked file(s) are deleted in the working tree (or outside a sparse "
                        "checkout) and would be left out: {}".format(len(missing), shorten(missing, 8)))
    if problems and not args.allow_uncommitted:
        blockers.append("the packaged folders differ from the last commit:\n  " + "\n  ".join(problems)
                        + "\nCommit or remove these changes (or restore the deleted files), or pass "
                        "--allow-uncommitted.")
    for problem in problems if args.allow_uncommitted else []:
        warn(problem)
    if modified:
        warn("{} tracked file(s) in the packaged folders have uncommitted edits; they are included "
             "as they are on disk: {}".format(len(modified), shorten(modified, 5)))
    if build_type and build_type != "Release":
        warn("CMAKE_BUILD_TYPE is {}, the release pipeline uses Release".format(build_type))

    if verdict == "dynamic":
        hint = "Build the static preset instead:\n    " + "\n    ".join(STATIC_BUILD_HINT[platform])
        if platform == "windows":
            blockers.append("this build is dynamically linked: its DLLs are not part of the mod "
                            "layout, so the packaged executables would not start. " + hint)
        elif not args.allow_dynamic:
            blockers.append("this build is dynamically linked: the archive would only run where "
                            "the libraries listed above exist (for a normal CMake build: on this "
                            "machine, while {} exists). {}\nor pass --allow-dynamic for a package "
                            "you only use on this machine".format(bin_dir, hint))
        else:
            warn("this build is dynamically linked: the archive only runs where the libraries listed "
                 "above exist (for a normal CMake build: on this machine, while {} exists). Do not "
                 "share this archive.".format(bin_dir))
    elif verdict == "unknown":
        warn("could not tell from the binaries or CMakeCache.txt whether the build is statically linked")
    for w in port_warnings + ([req_warning] if req_warning else []):
        warn(w)

    if blockers:
        raise PackageError("nothing was written:\n\n" + "\n\n".join(blockers))

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with tempfile.TemporaryDirectory(prefix="coop-mod-") as tmp:
        staged_bins = binaries if args.dry_run else maybe_strip(binaries, platform, args.strip, tmp)
        leaked = binaries_containing(staged_bins, repo)
        if leaked:
            info("NOTE: {} contain the build path {} (compiled-in source file names), which shows "
                 "your user name. Fine for your own use; to share, prefer the GitHub release.".format(
                     ", ".join(n + exe for n in leaked), repo))
        entries, plan_errors = build_plan(repo, files, staged_bins, platform, version, timestamp)

        records = plan_records(entries)
        plan_files = [e for e in entries if not e.is_dir]
        content = {e.name: e for e in plan_files}
        plan_errors += check_entries(records, platform, games, lambda n, limit: content[n].read(limit))
        if plan_errors:
            for e in plan_errors[:50]:
                info("  ERROR: " + e)
            raise PackageError("{} problem(s) with the files to package; nothing was written".format(
                len(plan_errors)))
        total = sum(e.size() for e in plan_files)
        info("Contents   : {} files + {} folders, {:.1f} MB uncompressed".format(
            len(plan_files), len(entries) - len(plan_files), total / (1 << 20)))
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
            errors, read_back, _, _ = verify_archive(partial, platform, games, True, False)
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
    info("Verified: only allowed paths, binaries at the root, data/ next to them, custom assets")
    info("          that game.gp builds present; extracted cleanly into a temporary folder.")
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
