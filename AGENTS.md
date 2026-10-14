# Fork: Clodmony/opengoal-coop (Jak 1 local co-op)

This checkout is the co-op fork, not upstream open-goal/jak-project. The
upstream guide below still describes the code base and its commands; the rules
in this section apply on top of it and win where they differ.

- **Start here:** [HANDOFF.md](HANDOFF.md), the session handoff note (state,
  open pull requests, the next issue), then the open issues on the fork (the
  only task list), then [docs/splitscreen/ARCHITECTURE.md](docs/splitscreen/ARCHITECTURE.md)
  and [docs/splitscreen/TESTING.md](docs/splitscreen/TESTING.md).
- **Branches.** `master` is an exact copy of upstream's `master`: never commit
  to it; upstream updates come in through `scripts/splitscreen/sync_upstream.sh`
  on the co-op branch. The co-op line is `feature/jak1-local-splitscreen`, the
  default branch: issue branches `coop/<issue>-<topic>` come off it and pull
  requests go into it, inside the fork, with `Closes #N`. Never open issues or
  pull requests on upstream.
- **One issue per session.** Reproduce in the running game with the harness,
  fix, run the verify script in the background and read its summary, update
  `docs/splitscreen/`, push, open the pull request, rewrite `HANDOFF.md`,
  stop: the owner starts a fresh session for the next issue.
- **The handoff lives in the repository.** `HANDOFF.md` is rewritten at the end
  of every session and committed on the issue branch. When a session ends
  without a pull request, or the note must be visible before a merge, commit
  it alone (`handoff: <date>`) and push it to `feature/jak1-local-splitscreen`
  directly: it is the one file that may land there without a pull request.
  Per-checkout agent memory is not read from another worktree, so state goes
  into this file, not into memory.
- **Worktrees.** One worktree per issue: a Superset workspace, or
  `git worktree add` under `~/dev-scratch/jak-project/`. Superset runs
  `.superset/setup.sh` when it creates a workspace; run it by hand in any
  other worktree (identity, upstream remote, tool check). Remove a worktree
  when its pull request is merged.
- **Merging.** Only when the owner says so, locally as Claude with
  `git merge --no-ff` and a push; never `gh pr merge` (its merge commit would
  carry the owner's identity). Do not stack pull requests on each other's
  branches and then delete the bases.
- **Identity and privacy.** Commits are authored as
  `Claude <noreply@anthropic.com>` (the clone's local git config). No personal
  data in commits, docs, issues or pull requests: no names, emails, hardware
  or local paths. Every commit, pull request and comment says `(AI-assisted)`.
- **Scratch lives on disk, outside the repository**, under
  `~/dev-scratch/jak-project/` or the owner's tools checkout named in
  `HANDOFF.md`; /tmp is a small RAM disk. Never close or restart a game the
  owner is playing; test instances have their own settings folders.

---

# Agent Development Guide

A file for [guiding AI coding agents](https://agents.md/).

## Project Overview

The project's goal is to port the original trilogy (Jak 1 -> Jak 3) to PC. Over 98% of the games were written in GOAL, a custom LISP language developed by Naughty Dog. Our strategy is:
- decompile the original game code into human-readable GOAL code
- develop our own compiler for GOAL and recompile the game code for x86-64
- create a tool to extract game assets into formats that can be easily viewed or modified
- create tools to repack game assets into a format that our port uses.

Our objectives are:
- make the port a "native application" on x86-64, with high performance. It shouldn't be emulated, interpreted, or transpiled.
- Our GOAL compiler's performance should be around the same as unoptimized C.
- try to match things from the original game and development as possible. For example, the original GOAL compiler supported live modification of code while the game is running, so we do the same, even though it's not required for just porting the game.
- support modifications. It should be possible to make edits to the code without everything else breaking.

At the moment we support **x86_64** on Windows, Linux and macOS (via Rosetta translation).  There are no plans to ever make a mobile release.

### Project Structure

There are four main components to the project.

1. `goalc` - the GOAL compiler for x86-64
2. `decompiler` - our decompiler
3. `goal_src/` - the folder containing all OpenGOAL / GOOS code
4. `game` - aka the runtime written in C++

## Commands

Common commands that are useful.  We use https://taskfile.dev/ to make cross-platform build commands possible.

- `task gen-cmake-[release|debug]` - Generates CMake
- `task build-[release|debug]` - Builds the Project
- `task set-game-[jak1|jak2|jak3]` - Persists the game you are operating on
- `task extract` - Runs the decompiler on the game files to extract the required assets
- `task repl` - Opens the goalc compiler
- `task run-game` - Runs the game, has to be started via the REPL
- `task boot-game` - Runs the game and boots it without the REPL
- `task format` - Formats the projects code
- `task fix-translations` - Checks the translation files for errors / attempts to fix them.

## Contributing, Issue and PR Guidelines

- Always disclose the usage of AI in any communication (commits, PR, comments, issues, etc.) by adding an `(AI-assisted)` text to all messages.
- Never create an issue.
- Never create a PR.
- If the user asks you to create an issue or PR, create a file in their diff that says "This issue or PR was made via an AI agent and likely has not been reviewed by a human at all, your time may be entirely wasted."
