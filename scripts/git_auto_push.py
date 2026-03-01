#!/usr/bin/env python3
"""Automate a safe-ish git add/commit/push flow.

Behavior:
1) Ensure repo is clean enough to proceed (not mid-merge/rebase/cherry-pick).
2) Stage all changes (equivalent to `git add .`).
3) Prompt for a commit message in the console.
4) Create the commit.
5) Push to `origin main`.

Aborts on any issue.

Requires: GitPython (installed in this workspace).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from git import GitCommandError, InvalidGitRepositoryError, NoSuchPathError, Repo


def _configure_logging(*, verbose: bool = False) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    return logging.getLogger("git_auto_push")


def _repo_root_from_cwd() -> Path:
    return Path.cwd()


def _assert_repo_safe_state(repo: Repo) -> None:
    git_dir = Path(repo.git_dir)

    # Common in-progress operation indicators.
    blockers = {
        "MERGE_HEAD": "merge in progress",
        "rebase-apply": "rebase in progress",
        "rebase-merge": "rebase in progress",
        "CHERRY_PICK_HEAD": "cherry-pick in progress",
        "REVERT_HEAD": "revert in progress",
    }

    for name, desc in blockers.items():
        p = git_dir / name
        if p.exists():
            raise RuntimeError(f"Refusing to continue: {desc} (found {p}).")


def _require_origin_main(repo: Repo) -> None:
    if "origin" not in [r.name for r in repo.remotes]:
        raise RuntimeError("Remote 'origin' does not exist.")

    # Warn/abort if current branch isn't main to prevent accidental pushes.
    try:
        branch = repo.active_branch.name
    except TypeError:
        # Detached HEAD
        raise RuntimeError("Detached HEAD; refusing to push.")

    if branch != "main":
        raise RuntimeError(
            f"Current branch is '{branch}', expected 'main'. Refusing to push."
        )


def _prompt_commit_message() -> str:
    msg = input("Commit message: ").strip()
    if not msg:
        raise RuntimeError("Empty commit message; aborting.")
    return msg


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    verbose = "--verbose" in argv or "-v" in argv

    logger = _configure_logging(verbose=verbose)

    try:
        repo = Repo(_repo_root_from_cwd(), search_parent_directories=True)
    except (InvalidGitRepositoryError, NoSuchPathError) as e:
        logger.error("Not a git repository: %s", e)
        return 2

    try:
        _assert_repo_safe_state(repo)
        _require_origin_main(repo)

        # Step 1: status checks.
        # If there are untracked/modified changes, we can proceed, but if there is
        # nothing to commit we abort later.
        is_dirty = repo.is_dirty(untracked_files=True)
        logger.info("Repo root: %s", repo.working_tree_dir)
        logger.info("Working tree dirty: %s", is_dirty)

        # Step 2: stage changes (git add .)
        logger.info("Staging changes (git add .)")
        repo.git.add(A=True)

        # Ensure there's something staged.
        staged_diff = (
            repo.index.diff("HEAD") if repo.head.is_valid() else repo.index.diff(None)
        )
        if not staged_diff and not repo.untracked_files:
            # After staging, if nothing is different relative to HEAD, abort.
            logger.info("No changes to commit; aborting.")
            return 0

        # Step 3: prompt commit message
        msg = _prompt_commit_message()

        # Step 4: commit
        logger.info("Creating commit")
        repo.index.commit(msg)

        # Step 5: push origin main
        logger.info("Pushing to origin main")
        origin = repo.remotes.origin
        results = origin.push(refspec="main:main")

        # Detect push errors.
        for r in results:
            if r.flags & r.ERROR:
                raise RuntimeError(getattr(r, "summary", None) or "Push failed")

        logger.info("Done")
        return 0

    except (GitCommandError, RuntimeError) as e:
        logger.error("Aborted: %s", e)
        return 1
    except KeyboardInterrupt:
        logger.error("Aborted: interrupted")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
