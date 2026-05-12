#!/usr/bin/env python3
"""
Export a subdirectory's git history into a new standalone repository.

Example:
python run.py \
  --source-repo "D:\\@DEV\\project-a" \
  --source-subdir sub-module-b \
  --target-dir "D:\\@DEV\\project-module-b" \
  --rev-range "7b47ec1755525f05cd76683215dad5ed3585fe6d^..1effd2672b9a396db04668c0b1d9d89043f1aacd" \
  --force-clean-target
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from tarfile import open as tar_open
from typing import List, Optional


@dataclass
class CommitMeta:
    sha: str
    author_name: str
    author_email: str
    author_date: str
    committer_name: str
    committer_email: str
    committer_date: str
    message: str


def run_git(args: List[str], *, cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
    cmd = ["git", *args]
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def print_step(msg: str) -> None:
    print(f"\n==> {msg}")


def ensure_git_available() -> None:
    run_git(["--version"])


def normalize_subdir(subdir: str) -> str:
    cleaned = subdir.strip().replace("\\", "/").strip("/")
    if not cleaned:
        raise ValueError("source-subdir cannot be empty")
    return cleaned


def list_commits(source_repo: Path, subdir: str, rev_range: str) -> List[str]:
    args = ["-C", str(source_repo), "rev-list", "--reverse", rev_range, "--", subdir]
    result = run_git(args)
    commits = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return commits


def get_commit_meta(source_repo: Path, commit: str) -> CommitMeta:
    fmt = "%H%x1f%an%x1f%ae%x1f%ad%x1f%cn%x1f%ce%x1f%cd%x1f%B"
    result = run_git(["-C", str(source_repo), "show", "-s", f"--format={fmt}", commit])
    parts = result.stdout.split("\x1f", 7)
    if len(parts) != 8:
        raise RuntimeError(f"Unexpected metadata format for commit {commit}")
    sha, an, ae, ad, cn, ce, cd, msg = parts
    return CommitMeta(
        sha=sha.strip(),
        author_name=an.strip(),
        author_email=ae.strip(),
        author_date=ad.strip(),
        committer_name=cn.strip(),
        committer_email=ce.strip(),
        committer_date=cd.strip(),
        message=msg.rstrip("\n"),
    )


def get_commit_changed_files(source_repo: Path, commit: str, subdir: str) -> List[str]:
    result = run_git(["-C", str(source_repo), "show", "--name-status", "--pretty=format:", commit, "--", subdir])
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return lines


def init_target_repo(target_dir: Path, force_clean_target: bool) -> None:
    if target_dir.exists() and force_clean_target:
        shutil.rmtree(target_dir)

    if target_dir.exists() and any(target_dir.iterdir()):
        raise RuntimeError(
            f"Target directory is not empty: {target_dir}\n"
            "Use --force-clean-target to remove it before export."
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    run_git(["-C", str(target_dir), "init"])


def clear_worktree_keep_git(target_dir: Path) -> None:
    for entry in target_dir.iterdir():
        if entry.name == ".git":
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def copy_contents(src: Path, dst: Path) -> None:
    if not src.exists():
        return

    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def export_snapshot_for_commit(source_repo: Path, commit: str, subdir: str, temp_root: Path) -> Path:
    tar_path = temp_root / f"{commit}.tar"
    # git archive exports the requested subdir with its original prefix, e.g. practicum/...
    run_git(["-C", str(source_repo), "archive", "--format=tar", "-o", str(tar_path), commit, subdir])

    extract_dir = temp_root / f"extract_{commit}"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with tar_open(tar_path) as tar:
        tar.extractall(extract_dir)

    return extract_dir / Path(subdir)


def has_staged_changes(target_dir: Path) -> bool:
    result = run_git(["-C", str(target_dir), "diff", "--cached", "--quiet"], check=False)
    return result.returncode != 0


def commit_to_target(target_dir: Path, meta: CommitMeta) -> None:
    run_git(["-C", str(target_dir), "add", "-A"])

    if not has_staged_changes(target_dir):
        print("   - No staged changes after snapshot sync, skipping commit.")
        return

    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = meta.author_name
    env["GIT_AUTHOR_EMAIL"] = meta.author_email
    env["GIT_AUTHOR_DATE"] = meta.author_date
    env["GIT_COMMITTER_NAME"] = meta.committer_name
    env["GIT_COMMITTER_EMAIL"] = meta.committer_email
    env["GIT_COMMITTER_DATE"] = meta.committer_date

    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".txt") as msg_file:
        msg_file.write(meta.message + "\n")
        msg_path = msg_file.name

    try:
        result = subprocess.run(
            ["git", "-C", str(target_dir), "commit", "-F", msg_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Commit failed for {meta.sha}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )
    finally:
        Path(msg_path).unlink(missing_ok=True)


def export_history(
        source_repo: Path,
        source_subdir: str,
        target_dir: Path,
        rev_range: str,
        force_clean_target: bool,
        dry_run: bool,
        limit: int,
) -> None:
    print_step("Validating input and discovering commits")
    ensure_git_available()

    if not source_repo.exists():
        raise RuntimeError(f"Source repo does not exist: {source_repo}")

    source_subdir = normalize_subdir(source_subdir)
    commits = list_commits(source_repo, source_subdir, rev_range)
    if not commits:
        raise RuntimeError("No commits found for the provided subdir and revision range.")

    if limit > 0:
        commits = commits[:limit]

    total = len(commits)
    print(f"Found {total} commit(s) that touched '{source_subdir}' in range '{rev_range}'.")

    if dry_run:
        print_step("Dry run mode: listing planned commits")
        for i, sha in enumerate(commits, start=1):
            meta = get_commit_meta(source_repo, sha)
            print(f"[{i}/{total}] {sha[:12]}  {meta.message.splitlines()[0] if meta.message else '(no message)'}")
        print("\nDry run completed. No repository was created.")
        return

    print_step("Initializing target repository")
    init_target_repo(target_dir, force_clean_target)
    print(f"Initialized target repository: {target_dir}")

    start = time.time()
    with tempfile.TemporaryDirectory(prefix="subdir-export-") as temp_dir_str:
        temp_root = Path(temp_dir_str)

        for i, sha in enumerate(commits, start=1):
            meta = get_commit_meta(source_repo, sha)
            changed_files = get_commit_changed_files(source_repo, sha, source_subdir)
            percent = (i / total) * 100.0

            print_step(f"[{i}/{total}] ({percent:6.2f}%) Replaying {sha}")
            title = meta.message.splitlines()[0] if meta.message else "(no message)"
            print(f"   - Message   : {title}")
            print(f"   - Author    : {meta.author_name} <{meta.author_email}>")
            print(f"   - Date      : {meta.author_date}")
            print(f"   - File diff : {len(changed_files)} path(s)")
            for line in changed_files:
                print(f"       {line}")

            snapshot_subdir = export_snapshot_for_commit(source_repo, sha, source_subdir, temp_root)
            clear_worktree_keep_git(target_dir)
            copy_contents(snapshot_subdir, target_dir)
            commit_to_target(target_dir, meta)

            elapsed = time.time() - start
            print(f"   - Completed : {i}/{total} commits, elapsed {elapsed:.1f}s")

    print_step("Export completed")
    print(f"Target repo path : {target_dir}")
    print(f"Total commits    : {total}")
    print(f"Elapsed time     : {time.time() - start:.1f}s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a subdirectory's history from a source repository into a new standalone repository."
    )
    parser.add_argument("--source-repo", required=True, help="Path to the source git repository.")
    parser.add_argument("--source-subdir", required=True,
                        help="Subdirectory inside source repo to export (repo-relative).")
    parser.add_argument("--target-dir", required=True, help="Path to create the exported standalone repository.")
    parser.add_argument(
        "--rev-range",
        default="HEAD",
        help="Git revision range to scan (default: HEAD). Example: <start>^..<end>",
    )
    parser.add_argument(
        "--force-clean-target",
        action="store_true",
        help="Delete target directory first if it exists.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only list commits, do not create target repo.")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Replay only the first N commits after filtering (0 means all).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        export_history(
            source_repo=Path(args.source_repo).resolve(),
            source_subdir=args.source_subdir,
            target_dir=Path(args.target_dir).resolve(),
            rev_range=args.rev_range,
            force_clean_target=args.force_clean_target,
            dry_run=args.dry_run,
            limit=args.limit,
        )
        return 0
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
