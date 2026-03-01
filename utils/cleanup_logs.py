"""Clean up files in the `logs/` folder.

Local-only helper script intended to be run as a backend job (cron/launchd/GitHub
Actions, etc.). It deletes old log files based on retention rules.

Usage:
    python utils/cleanup_logs.py --dry-run
    python utils/cleanup_logs.py --yes
    python utils/cleanup_logs.py --days 14 --keep 200

Default behavior (DESTRUCTIVE):
- Deletes ALL files in `logs/` (equivalent to --days 0 --keep 0)
- Prompts for confirmation unless --yes is provided
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = PROJECT_ROOT / "logs"


@dataclass(frozen=True)
class Candidate:
    path: Path
    mtime: float
    size: int


def _iter_log_files(logs_dir: Path) -> list[Candidate]:
    if not logs_dir.exists():
        return []

    out: list[Candidate] = []
    for p in logs_dir.rglob("*"):
        if not p.is_file():
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        out.append(Candidate(path=p, mtime=st.st_mtime, size=st.st_size))

    # newest first
    out.sort(key=lambda c: c.mtime, reverse=True)
    return out


def _format_bytes(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.2f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{n} B"


def _confirm_or_exit(logs_dir: Path, assume_yes: bool) -> bool:
    """Return True if the user confirmed, False if they declined.

    This keeps interactive aborts graceful (no exception traceback).
    """

    if assume_yes:
        return True

    if not logs_dir.exists():
        return True

    try:
        file_count = sum(1 for p in logs_dir.rglob("*") if p.is_file())
    except OSError:
        file_count = 0

    resp = input(
        "\n\u26a0\ufe0f  WARNING: This will delete log files in:\n"
        f"  {logs_dir}\n\n"
        f"Detected files: {file_count}\n\n"
        "Continue? [y/N]: "
    ).strip()

    if resp.lower() not in {"y", "yes"}:
        print("Cleanup aborted.")
        return False

    return True


def cleanup_logs(
    *,
    logs_dir: Path,
    keep_newest: int,
    max_age_days: int,
    max_total_files: int | None,
    dry_run: bool,
) -> int:
    """Delete log files older than retention period, keeping newest N files.

    Operates recursively over `logs_dir` including all subfolders.

    Notes:
    - Subfolders are never removed.
    - Any delete/stat errors are reported and processing continues.

    Additionally, if max_total_files is set, delete oldest files until the total
    count is <= max_total_files (after applying keep_newest protection).
    """

    files = _iter_log_files(logs_dir)
    if not files:
        print(f"No files found in {logs_dir}")
        return 0

    now = time.time()
    cutoff = now - (max_age_days * 86400)

    keep_newest = max(keep_newest, 0)
    protected = set(c.path for c in files[:keep_newest])

    delete: list[Candidate] = []
    keep: list[Candidate] = []

    # Pass 1: age-based deletion
    for c in files:
        if c.path in protected:
            keep.append(c)
            continue
        if c.mtime < cutoff:
            delete.append(c)
        else:
            keep.append(c)

    # Pass 2: total-count cap (delete oldest first)
    if max_total_files is not None:
        max_total_files = max(max_total_files, 0)
        if len(keep) > max_total_files:
            # keep is in newest-first order already
            overflow = keep[max_total_files:]
            keep = keep[:max_total_files]
            for c in overflow:
                if c.path in protected:
                    # Respect protection even if it violates the cap
                    keep.append(c)
                else:
                    delete.append(c)

            # Deduplicate after possible moves between keep/delete
            delete_paths = set()
            dedup_delete: list[Candidate] = []
            for c in delete:
                if c.path in delete_paths:
                    continue
                delete_paths.add(c.path)
                dedup_delete.append(c)
            delete = dedup_delete

    total_size = sum(c.size for c in files)
    delete_size = sum(c.size for c in delete)

    print(f"Logs dir: {logs_dir}")
    print(f"Total files: {len(files)} ({_format_bytes(total_size)})")
    print(
        f"Retention: delete if older than {max_age_days} days, "
        f"always keep newest {keep_newest} files"
        + (
            f", cap total files at {max_total_files}"
            if max_total_files is not None
            else ""
        )
    )
    print(f"Will delete: {len(delete)} files ({_format_bytes(delete_size)})")

    if dry_run:
        for c in delete:
            age_days = (now - c.mtime) / 86400
            try:
                rel = c.path.relative_to(PROJECT_ROOT)
            except Exception:
                rel = c.path
            print(f"DRY-RUN delete: {rel} (age {age_days:.1f}d)")
        if keep_newest:
            for c in files[:keep_newest]:
                try:
                    rel = c.path.relative_to(PROJECT_ROOT)
                except Exception:
                    rel = c.path
                print(f"DRY-RUN keep (protected): {rel}")
        return 0

    deleted = 0
    errors = 0
    for c in delete:
        try:
            c.path.unlink()
            deleted += 1
        except OSError as e:
            errors += 1
            print(f"Could not delete {c.path}: {e}", file=sys.stderr)
        except Exception as e:
            errors += 1
            print(f"Unexpected error deleting {c.path}: {e}", file=sys.stderr)

    # Never remove directories; optionally report empty directories is out of scope.

    print(f"Deleted {deleted}/{len(delete)} files")
    if errors:
        print(f"Encountered {errors} errors while deleting files (continued).")
    return 0 if deleted == len(delete) else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Clean up old files in the logs folder."
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Do not prompt for confirmation.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=0,
        help="Delete files older than N days (default: 0 = delete all).",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=0,
        help="Always keep newest N files regardless of age (default: 0).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without deleting anything.",
    )
    parser.add_argument(
        "--logs-dir",
        default=str(LOGS_DIR),
        help="Override logs directory (default: <repo>/logs).",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Optional: cap total number of files by deleting oldest files.",
    )
    args = parser.parse_args(argv)

    logs_dir = Path(args.logs_dir).expanduser().resolve()

    # Prompt unless explicitly skipped, and never prompt on dry-run.
    if not args.dry_run:
        if not _confirm_or_exit(logs_dir, bool(args.yes)):
            return 0

    return cleanup_logs(
        logs_dir=logs_dir,
        keep_newest=max(args.keep, 0),
        max_age_days=max(args.days, 0),
        max_total_files=args.max_files,
        dry_run=bool(args.dry_run),
    )


if __name__ == "__main__":
    raise SystemExit(main())
