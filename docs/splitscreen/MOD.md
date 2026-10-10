# Jak 1 local co-op: shipping as an OpenGOAL Launcher mod

> Written with AI assistance (AI-assisted). Launcher details were read from open-goal/launcher at
> `a32643d`; the release tooling comes from OpenGOAL-Mods/OG-Mod-Base at `2c4ee857`.

Two ways to get the co-op build into the OpenGOAL Launcher as its own mod, next to (and separate
from) the official Jak 1:

1. **Local package**: build on your machine, run `scripts/coop-mod/package_mod.py`, then use
   "Add from File" in the launcher.
2. **GitHub release**: run the "Cut Mod Release" workflow on the fork. It builds Windows, Linux and
   macOS (Intel) binaries and publishes them as release assets, ready for "Add from File" or a
   mod source.

A local package installed the way the launcher installs it boots the game (see
[Validation](#validation)). Not done yet: an install through the launcher's own UI (#1), a release
run on GitHub (#2), Windows (#3).

## What a launcher mod is

OpenGOAL has no plugin loader. A launcher mod is a complete jak-project build: its own `gk`,
`goalc` and `extractor` plus a `data/` folder with the GOAL source, the decompiler config and the
runtime assets (fonts, shaders, controller database). It contains **no game files**. When you add
a mod, the launcher runs the mod's `extractor` to decompile your own disc files (the ones the
official Jak 1 install already extracted) and to compile the mod's GOAL code, inside the mod's
folder. Then it starts the mod's `gk`.

Archive layout, the same for the local package and the release assets (binaries at the archive
root, no top-level folder):

```text
gk, goalc, extractor            (gk.exe, goalc.exe, extractor.exe on Windows)
data/launcher/error-code-metadata.json
data/decompiler/config/...
data/goal_src/...
data/game/assets/...
data/game/graphics/opengl_renderer/shaders/...
data/custom_assets/...
data/log/                       (empty)
```

The launcher passes no custom arguments to a mod, so co-op is switched on in game: Options >
Game Options > Misc Options > "Local co-op" (works without `-debug`).

## Build a portable (static) build

A normal developer build (`task build-release`, or `cmake -B build --preset=Release-linux-clang`)
links the project's own libraries dynamically: on Linux `build/game/gk` loads 14 libraries from
`build/...` through an absolute RUNPATH, and on Windows the DLLs would be missing from the package.
Such a package only works on the machine that built it, as long as the build folder exists. The
release pipeline uses the `*-static` presets; do the same for packages you share.

Linux (clang, as for a normal build):

```sh
cmake --preset=Release-linux-clang-static
cmake --build build/Release/bin --parallel 8
```

The preset builds into `build/Release/bin`, which is where the packaging script looks first. Your
normal `build/` is not touched. Keep building this folder while you work on a package: the
script refuses binaries that are older than their C/C++ sources (see [Package it](#package-it)).

Even a static Linux build links glibc and libstdc++ (and zlib) dynamically, so it only starts on
systems with at least the glibc **and** libstdc++ versions it was built against. A build on a
current distribution is not portable to older ones: built on Ubuntu 24.04 (glibc 2.39, libstdc++
14), the binaries need `GLIBC_2.38` and `GLIBCXX_3.4.32` and do not start on Ubuntu 22.04
(glibc 2.35, `GLIBCXX_3.4.30`) or Debian 12 (glibc 2.36, `GLIBCXX_3.4.30`): the launcher's
decompile step fails with "version `GLIBC_2.38' not found". The packaging script prints the
minimum versions and warns when they are newer than Ubuntu 22.04's. For packages other people
will use, share the GitHub release assets (built on Ubuntu 22.04) or build in an `ubuntu:22.04`
container.

Windows (same shell as for `task gen-cmake-release`, or pick "Windows Static Release (clang)" in
Visual Studio):

```sh
cmake --preset=Release-windows-clang-static
cmake --build out/build/Release --parallel 8
```

The static and the normal Windows presets share `out/build/Release`, so this reconfigures your
normal build folder, and DLLs from an earlier normal build stay in `out/build/Release/bin`. The
packaging script therefore does not trust `CMakeCache.txt` (it only shows the last configure): it
reads the import table of each `.exe` and refuses the build when an `.exe` imports a DLL from its
folder (a normal build, or a static configure whose build did not finish).

macOS: `Release-macos-x86_64-clang-static` (Intel, what the release ships; runs on Apple Silicon
through Rosetta) or `Release-macos-arm64-clang-static` for a local Apple Silicon package
(`--platform macos-arm`), both into `build/Release/bin`. The script reads the dylibs each binary
loads (the same list as `otool -L`) and refuses the build when one is outside `/usr/lib` and
`/System/Library`, for example a Homebrew library or an `@rpath` one.

Local builds also contain your build folder path (source file names compiled in, e.g.
`/home/<you>/jak-project/game/...` or `C:\Users\<you>\...`), which shows your user name; the
script mentions it. The GitHub release assets do not have this problem.

## Package it

From the repository root (Python 3.9+, no extra packages, `git` on PATH):

```sh
python3 scripts/coop-mod/package_mod.py          # Linux / macOS
python scripts\coop-mod\package_mod.py           # Windows
```

The script finds the build (`build/Release/bin`, then `build/` on Linux and macOS;
`out/build/Release/bin`, then `build/bin` on Windows). When there are several it takes a static
one first, then the one with the newest `gk`, lists the others and warns when one of them has a
newer `gk` than the one it packages. It checks the build and writes:

- `build/coop-mod/jak1-coop.tar.gz` (Linux, macOS) or `build/coop-mod/jak1-coop.zip` (Windows);
- `<archive>.sha256`;
- `metadata.json` with `--emit-metadata` (made by the release pipeline's own `emit-metadata.py`).

It prints the archive path and the launcher steps below. Useful options:

| Option | Meaning |
| --- | --- |
| `--bin-dir PATH` | Use this build: a CMake build folder (`game/gk`, `goalc/goalc`, `decompiler/extractor`) or a flat folder (`gk.exe`, ...) |
| `--name NAME` | Archive name, default `jak1-coop`. The launcher uses it as the mod name and settings/save folder name, so keep it the same between builds |
| `--release-name` | Name it like the release asset: `linux-<version>.tar.gz`, `windows-<version>.zip`, `macos-intel-<version>.tar.gz` |
| `--version vX.Y.Z` | Default: the tag on HEAD, otherwise `v0.0.0-local.g<commit>` (`.dirty` with uncommitted changes in the packaged folders or the C/C++ sources) |
| `--allow-stale` | Package binaries that are older than their C/C++ sources anyway |
| `--allow-uncommitted` | Package even though the packaged folders have staged-but-uncommitted, untracked or deleted files (staged files are included, untracked and deleted ones left out) |
| `--allow-dynamic` | Package a dynamic Linux/macOS build anyway, for a quick test on this machine only. Refused on Windows |
| `--dry-run` | All checks, nothing written |
| `--check ARCHIVE` | Only verify an existing archive, e.g. a downloaded release asset (also prints what the binaries link against) |
| `--out-dir`, `--platform`, `--strip`, `--games`, `--verbose` | See `--help` |

What it checks (each problem stops the run before anything is written, unless the matching
`--allow-...` option is given):

- **The binaries match the sources.** Each binary must be newer than the git-tracked C/C++ and
  CMake files it is built from (the rule make and ninja use: `gk` from `game/`, `goalc` and
  `extractor` from `goalc/`, `decompiler/` and `game/sound/`, all three from `common/` and
  `third-party/`). A build left over from an older checkout or another branch is refused, because
  the packaged GOAL code would run against old C++ (for example missing kernel functions). Rebuild
  (`cmake --build build/Release/bin`) and run the script again. `gk --version` cannot tell: it
  shows the commit of the last CMake *configure* (`common/CMakeLists.txt` writes
  `common/versions/revision.h` at configure time), not of the last build.
- **The packaged folders match the last commit.** Only files **tracked by git** under
  `decompiler/config`, `goal_src`, `game/assets`, `game/graphics/opengl_renderer/shaders` and
  `custom_assets` are packaged, with their contents as they are on disk (uncommitted edits to
  tracked files are included and listed). Files that are staged but not committed, untracked files
  (`git add` and commit a new `.gc` file, or the package won't compile it) and tracked files that
  are deleted or outside a sparse checkout stop the run. This is the main guard against packaging
  something by accident: ignored files (`iso_data/`, `decompiler_out/`, `out/`, `goal_src/user/*`,
  `custom_assets/*/texture_replacements/*`, saves, settings, logs) are never packaged, and a file
  that `git add -f` put into the index is refused until it is committed.
- **What game.gp builds is there.** The custom levels and actors that `goal_src/jak1/game.gp`
  compiles (`custom_assets/jak1/levels/test-zone/...`, `custom_assets/jak1/models/custom_levels/test-actor.glb`)
  and its other literal input files must be in the archive; without them the launcher's compile
  step fails with "Input file ... does not exist".
- **Allow list and deny list.** Every entry is checked before writing and again after reading the
  archive back: anything outside the layout above, symlinks, files over 20 MB, private keys or
  tokens, forbidden folders (`iso_data`, `decompiler_out`, `out`, `saves`, `game_config`,
  texture/merc replacements, ...) and, as a best-effort extra, game disc names and types
  (`.iso`, `.cgo`, `.dgo`, `.go`, `.str`, `.vag`, `.sbk`, `.mus`, `.irx`, `.cnf`, `.ayb`, `.wav`,
  `VAGWAD.*`, `0COMMON.TXT`-style text files, the boot ELF such as `SCUS_971.24`). Extracted
  textures or models (`.png`, `.glb`) cannot be told apart from the repository's own, so the
  commit rule above is what keeps them out.
- **The binaries are portable.** Executables for the target platform (x86-64 ELF, PE or Mach-O;
  arm64 for `macos-arm`), and, read from the binaries themselves, linked only against system
  libraries: on Linux only libc, libstdc++, zlib and the like and no absolute RUNPATH, on Windows
  no DLL imported from the build folder (other non-system DLLs give a warning), on macOS no dylib
  outside `/usr/lib` and `/System/Library`. On Linux it
  prints the minimum glibc and libstdc++ versions (see above). Stripped on Linux and macOS (copies,
  like CI does) and stored with mode 755 (the launcher does not set permissions itself).
- The written archive is extracted into a temporary folder before it is moved into place.

## Add it in the launcher ("Add from File")

1. Install the official Jak 1 in the launcher first. The Mods page is only reachable from an
   installed game, and the mod reuses the disc files that install extracted
   (`<install>/active/jak1/data/iso_data/jak1`; without them the launcher asks for an ISO).
2. Select Jak 1, then **Features > Mods**, then **Add from File**. The file picker accepts `.zip`
   on Windows and `.tar.gz` on Linux and macOS.
3. The launcher unpacks the archive into `<install>/features/jak1/mods/_local/<name>`
   (`<name>` = file name without `.zip`/`.tar.gz`), then runs the mod's extractor to decompile
   and compile. This takes about as long as a fresh Jak 1 install.
4. Open the mod in the Mods list and press **Play**. In game: Options > Game Options > Misc
   Options > "Local co-op".

If something fails, look at the launcher's log folder: `extractor-jak1.log` (decompile and
compile) and `game-jak1-<name>.log` (the running game). The launcher ignores errors while
unpacking an archive and starts the install anyway, so a broken archive shows up as extractor
errors; run `package_mod.py --check` on it.

## Where settings and saves live

The launcher starts a mod's `gk` with
`-v --game jak1 --config-path <install>/features/jak1/mods/<source>/_settings/<name> -- -boot -fakeiso`,
so the mod has its own settings and saves, separate from vanilla OpenGOAL:

- settings: `<install>/features/jak1/mods/<source>/_settings/<name>/OpenGOAL/jak1/settings/`
- saves: `.../_settings/<name>/OpenGOAL/jak1/saves/`
- co-op saves: `.../_settings/<name>/OpenGOAL/jak1/saves/coop/`

`<source>` is `_local` for "Add from File", or the `sourceName` of a mod source. The `_settings`
folder is outside the mod folder: uninstalling or re-adding the mod keeps it. A different archive
name means a different, empty settings folder, so keep the name fixed (`jak1-coop`).

## Updating

- Local: rebuild, run `package_mod.py` again (same `--name`), then "Add from File" again. The
  launcher deletes and replaces `mods/_local/jak1-coop` (including its compiled game files, so it
  decompiles and compiles again) and keeps `_settings/jak1-coop`.
- Release: cut a new release (below). Launcher users who added your mod source see the update once
  you add the new version to the source JSON (the pipeline doesn't edit it); for "Add from File",
  download the new asset and rename it to `jak1-coop.tar.gz` / `jak1-coop.zip`
  before adding it, so it replaces the old one instead of becoming a second mod named
  `linux-v0.1.1`.

## Cut a GitHub release on the fork

Files (adapted from OG-Mod-Base, see [Attribution](#attribution)):

- `.github/workflows/cut-release.yaml`: the "Cut Mod Release ⭐" button. Inputs: semver bump
  (patch/minor/major) and the supported games (Jak 1 on, others off by default; co-op is Jak 1
  only, so leave them off). Its "Prep Variables" job checks the branch, checks that the co-op
  branch is merged, and computes the version.
- `.github/workflows/mod-release-pipeline.yml`: validates `metadata.json`, tags the commit
  (`mathieudutour/github-tag-action`, with the computed version as `custom_tag`), creates a draft
  release, builds with the existing
  `windows-build-clang.yaml`, `linux-build-clang.yaml` and `macos-build.yaml` using the
  `Release-*-clang-static` presets (tests included), bundles with
  `.github/scripts/releases/extract_mod_build_{windows,unix}.sh`, uploads
  `windows-<tag>.zip`, `linux-<tag>.tar.gz`, `macos-intel-<tag>.tar.gz` and `metadata.json`, and
  publishes the release.

The shared build workflows were not changed: they already have the inputs (`cmakePreset`,
`cachePrefix`, `uploadArtifacts`) and the artifact names (`opengoal-<os>-static`) the pipeline
uses.

### One-time setup on GitHub

1. **Enable Actions on the fork.** GitHub disables workflows on new forks: open the fork's
   Actions tab and enable them if it asks. (Could not be checked from here.)
2. **Make the workflow dispatchable.** GitHub only shows the "Run workflow" button for a workflow
   whose file is on the repository's **default branch** (`master` on the fork). Pick one:
   - Settings > General > Default branch: switch it to `feature/jak1-local-splitscreen`. Master
     stays untouched. Or
   - put `.github/workflows/cut-release.yaml` on `master` as well. When you run it you choose the
     branch, and the workflow files and code of **that branch** are used. Releasing from `master`
     itself also needs the pipeline, the scripts and the co-op code on `master`.
3. **Permissions.** The workflow asks for `contents: write` itself, which is enough to create the
   tag and the release with the default "Read repository contents" setting. Only if tagging fails
   with HTTP 403, set Settings > Actions > General > Workflow permissions to "Read and write".
4. If you restrict which actions may run, allow `actions/*`, `mathieudutour/github-tag-action`,
   `hendrikmuhs/ccache-action` and `ilammy/msvc-dev-cmd`.

### What gets released

Everything (co-op code and release tooling) is on `feature/jak1-local-splitscreen`, and releases
are cut from that branch: a release contains exactly what is pushed there. `REQUIRE_MERGED_BRANCH`
in `cut-release.yaml` only matters if you ever release from `master` instead: then `master` must
contain the whole co-op branch.

### Running it

Actions > "Cut Mod Release ⭐" > Run workflow > branch `feature/jak1-local-splitscreen` (or
`master`) > bump > Run.

- Releases can only be cut from `master` and `feature/jak1-local-splitscreen`
  (`ALLOWED_BRANCHES` in `cut-release.yaml`); a run on any other branch stops in "Prep Variables".
- The bump you pick decides the version: "Prep Variables" takes the highest `vX.Y.Z` tag
  (pre-release tags such as `v1.0.0-rc.1` are ignored), applies the bump and passes the result to
  the tag action as `custom_tag`. Without that, `github-tag-action` would let commit messages since
  the last tag decide whenever one follows the conventional-commit style (`fix:` gives patch,
  `feat:` minor, `BREAKING CHANGE` major; upstream has such commits, e.g. "fix: typo in
  decompression error checking (#4370)"), and the choice would only be a fallback. The run log of
  "Prep Variables" shows `Latest release tag: ...; <bump> bump: v<version>`.
- The fork has no tags yet, so the first release is `v0.0.1`, `v0.1.0` or `v1.0.0` for
  patch/minor/major. If you ever push upstream's tags to the fork, versions continue from
  upstream's latest `vX.Y.Z`.
- The allowed branches are also passed to the tag action as `releaseBranches`, as in the template
  (it only matters if `custom_tag` is ever left empty: the action would then treat other branches
  as pre-release branches and tag `v0.0.1-<branch>.0`, `.1`, ...).
- The tag is created before the builds, so the binaries report it as their revision (`BUILT_TAG`:
  `gk --version`, and the build revision the game draws on screen). This fork has no OG-Mod-Base
  `mod-settings.gc`, so `replace-mod-version-timestamp.py` finds nothing to replace.
- Expect a long run: three builds with tests (Windows up to 60 min, macOS Intel up to 120 min). A
  failing test on any platform blocks the release.
- If a build or bundle job fails, use "Re-run failed jobs" in the same run: it reuses the tag. A
  new run bumps the version again (the failed run's tag counts as the latest) and leaves the failed
  draft release and its tag behind; delete both first.
- Don't run upstream's "🏭 Draft Release" workflow on the fork.

### Installing a release

- "Add from File": download the asset for your OS and rename it to `jak1-coop.tar.gz` (Linux,
  macOS) or `jak1-coop.zip` (Windows) first, see [Updating](#updating). `package_mod.py --check
  <asset>` verifies a downloaded asset.
- Mod source: host a JSON file where a plain HTTP GET returns it (for example the raw URL of a
  file in the repository) and add it in the launcher under Settings > Mods > "Mod Source URL". The
  launcher picks the asset by OS key (`windows`, `linux`, `macos`), installs the version with the
  newest `publishedDate`, and drops the whole source if the JSON doesn't parse. Example (valid
  against the launcher's `schemas/mod-source/v1/mod-source-schema.v1.json`; adjust the version
  and URLs):

```json
{
  "schemaVersion": "1.0.0",
  "sourceName": "jak1-coop",
  "lastUpdated": "2026-10-09T00:00:00Z",
  "mods": {
    "jak1-coop": {
      "displayName": "Jak 1 local co-op (split screen)",
      "description": "Split-screen local co-op for two players. Turn it on in Options > Game Options > Misc Options > Local co-op.",
      "authors": ["Clodmony"],
      "tags": ["co-op"],
      "supportedGames": ["jak1"],
      "websiteUrl": "https://github.com/Clodmony/jak-project/tree/feature/jak1-local-splitscreen",
      "versions": [
        {
          "version": "0.1.0",
          "publishedDate": "2026-10-09T00:00:00Z",
          "supportedGames": ["jak1"],
          "assets": {
            "windows": "https://github.com/Clodmony/jak-project/releases/download/v0.1.0/windows-v0.1.0.zip",
            "linux": "https://github.com/Clodmony/jak-project/releases/download/v0.1.0/linux-v0.1.0.tar.gz",
            "macos": "https://github.com/Clodmony/jak-project/releases/download/v0.1.0/macos-intel-v0.1.0.tar.gz"
          }
        }
      ]
    }
  },
  "texturePacks": {}
}
```

`texturePacks` and each version's `supportedGames` are required in practice (the launcher only
lists versions whose `supportedGames` contains `jak1`). The release's `metadata.json` is not read
by the launcher; it is for mod lists that collect releases.

## Limitations

- No GitHub release run (#2) and no install through the launcher UI yet (#1).
- One macOS asset (Intel); the launcher has a single `macos` key, so Apple Silicon runs it through
  Rosetta.
- Each mod install keeps its own decompiled and compiled copy of the game inside the mod folder
  (disk space and install time like a second Jak 1 install).
- The launcher compares mod versions as plain strings and has no update check for `_local` mods.
- Windows packaging from a real local build has not been run (no Windows machine here): the zip
  writer and the DLL import check were tested with small executables linked by `lld-link`, the
  macOS dylib check with executables linked by `ld64.lld`.
- The release-branch checks in "Prep Variables" (merge check, version) were run locally against a
  test repository, not on GitHub.

## Validation

Done on Linux (Ubuntu 24.04) on 2026-10-09. Work files were in a temporary folder; the only file
written into the repository was the gitignored `common/versions/revision.h`, regenerated when the
scratch static build was configured (`BUILT_SHA` 77c2198f to 13dc8a51; the next build of `build/`
picks it up).

- `package_mod.py` on a static build (`Release-linux-clang-static`) and, with `--allow-dynamic`, on
  the dynamic `build/`: 4,513 files and 510 folders. Paths and modes are identical to the output of
  the official `extract_mod_build_unix.sh` + `tar czf`, and `diff -r` of `data/` is empty.
- Extracted the static package to a fresh folder: `gk --version`, `gk --help`, `goalc --help`,
  `extractor --help` and the launcher's argument list for `gk` all exit 0; `ldd gk` shows only
  system libraries.
- A crafted archive with `iso_data`, `out`, saves, a symlink, a private key, a file at the root and
  a non-executable `gk` is rejected by `--check` (17 errors); a forbidden file tracked by git is
  rejected before anything is written.
- Two runs give byte-identical archives (fixed timestamps and owners).
- Workflows parse with PyYAML; `actionlint` (with shellcheck) is clean for `cut-release.yaml` and
  reports only template issues in `mod-release-pipeline.yml` (an unused `default` on a required
  input, `versionName` assigned but unused).
- `metadata.json` from `emit-metadata.py` validates against `mod-schema.v2.json` with `ajv-cli@5`
  and Python `jsonschema`.

Added on 2026-10-10, after a review:

- The same results again (5,024 entries, listing and `data/` identical to the official script,
  reproducible, extracted binaries run). From the extracted static package, the packaged `goalc`
  builds the packaged custom actor: `goalc --game jak1 --cmd '(make "$OUT/obj/test-actor-ag.go")'`
  (once `data/out/jak1/obj` exists, which the launcher's extractor creates).
- Refused as intended, in a scratch clone: binaries older than their sources (per binary: touching
  `game/kernel/...` flags only `gk`, touching `game/sound/...` all three), with a warning when
  another build folder has a newer `gk`; staged, untracked and deleted files; a sparse checkout
  without `custom_assets` (and, with `--allow-uncommitted`, the three custom asset files game.gp
  needs); staged disc names (`0COMMON.TXT`, `0SUBTIT.TXT`, `VAGWAD.ENG`, `VAGDIR.AYB`,
  `SCUS_971.24`, `OVERLORD.IRX`, `SYSTEM.CNF`, a `.wav`).
- Windows: `.exe` files that import `SDL3.dll` and a delay-loaded `compiler.dll` from their folder
  are refused even with `STATICALLY_LINK=true` in the cache; executables that only import
  `KERNEL32.dll` next to leftover DLLs are packaged. The import lists match `llvm-readobj
  --coff-imports`. macOS: dylib lists match `llvm-objdump --macho --dylibs-used` for thin and
  universal binaries; Homebrew and `@rpath` dylibs are refused.
- `--check` on truncated, corrupt and non-archive files prints an error and exits 1 (no traceback).
- The "Prep Variables" script, run against a local test repository with the two-branch setup of
  that time: refuses a release branch that misses a co-op commit, passes after the merge, refuses
  a branch not in `ALLOWED_BRANCHES`, skips the check
  when the co-op branch is gone, and computes `0.0.1` / `0.1.0` / `1.0.0` without tags and
  `0.10.1` / `0.11.0` / `1.0.0` with `v0.0.1`, `v0.9.0`, `v0.10.0` (pre-release and malformed tags
  ignored).

Added on 2026-10-10, after merging the co-op branch (`ee509d24`):

- `package_mod.py --allow-dynamic` on the rebuilt `build/`, archive extracted to a fresh folder:
  the packaged `goal_src` is identical to the branch, and the packaged `goalc` compiles all 522
  Jak 1 targets from the packaged `data/` (`goalc --game jak1 --cmd '(make-group "all-code")'`,
  after `mkdir -p data/out/jak1/obj`).
- `./test.sh` found that the merge broke the Jak 2/3 compile tests: `goal_src/jak1/pc/pckernel-common.gc`
  is compiled for every game and had started to use the Jak 1-only `coop-split-frame?`. The
  release builds run these tests, so a release would have failed. The co-op part moved to
  `coop-update-2d-aspect` (Jak 1 only, called right after the pc-settings update in `main.gc`);
  Jak 1 behaves the same and the type consistency tests of all games pass again.

Added on 2026-10-10, after moving the packaging onto `feature/jak1-local-splitscreen` (releases are
now cut from that branch):

- With the user's own Jak 1 disc files (PAL), the launcher's install steps run by hand in a scratch
  folder: unpack `jak1-coop.tar.gz`, `./extractor --game jak1 --proj-path ./data --folder
  --decompile --compile <disc files>` (all 1321 targets built), then `./gk -v --game jak1
  --config-path <scratch> -- -boot -fakeiso` (no `-debug`, as the launcher starts it). The game
  boots to the title screen, writes `pc-settings.gc` and `display-settings.json` only under the
  given config path, and leaves `~/.config/OpenGOAL` untouched.

## Attribution

The release tooling is adapted from
[OpenGOAL-Mods/OG-Mod-Base](https://github.com/OpenGOAL-Mods/OG-Mod-Base) (commit `2c4ee857`),
ISC licence, Copyright (c) OpenGOAL Team, the same licence and copyright holder as this repository.

| File | Origin |
| --- | --- |
| `.github/workflows/cut-release.yaml` | adapted: binaries always built from this repository (the `binary_source` input is gone), `releaseBranches` set and limited to `master` / `feature/jak1-local-splitscreen`, merge check for the co-op branch, version computed from the bump and passed as `customTag` |
| `.github/workflows/mod-release-pipeline.yml` | copied; `actions/checkout`, `upload-artifact`, `download-artifact` at the versions this repository uses; optional `customTag` input passed to the tag action as `custom_tag` |
| `.github/scripts/create-mod-release/*.py` | copied unchanged (`bundle-*.py` and `common.py` are only used by the "no build" path, which `cut-release.yaml` no longer selects) |
| `.github/scripts/releases/extract_mod_build_{unix,windows}.sh`, `replace-mod-version-timestamp.py` | copied unchanged |
| `.github/schemas/README.md`, `.github/schemas/mods/v2/*` | copied unchanged |
| `scripts/coop-mod/package_mod.py` | new (AI-assisted), reproduces the layout of `extract_mod_build_unix.sh` |
