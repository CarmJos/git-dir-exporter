# git-dir-exporter

`git-dir-exporter` is a Python script that replays the history of one subdirectory from a source Git repository into a new standalone repository.

This repository currently provides a single CLI script: `src/run.py`.

## What It Does

- Finds commits that touched a specific subdirectory in a source repository.
- Rebuilds that subdirectory snapshot commit-by-commit.
- Commits each snapshot into a target repository while preserving:
  - commit message
  - author / committer name and email
  - author / committer date

Use this when you need to split a module out of a monorepo while retaining meaningful history.

## Requirements

- Python 3.10+ (3.9 may also work, but not explicitly verified)
- Git CLI available in `PATH`
- Windows / Linux / macOS (script uses Python stdlib + Git)

No third-party Python packages are required for runtime.

## Quick Start

1. Clone this repository.
2. Run a dry-run first to confirm commit selection.
3. Run the export.

```powershell
python .\src\run.py --help
```

## Usage

```powershell
python .\src\run.py `
  --source-repo "D:\@DEV\project-a" `
  --source-subdir "modules/sub-module-b" `
  --target-dir "D:\@DEV\project-module-b" `
  --rev-range "HEAD" `
  --dry-run
```

After validating output, remove `--dry-run` and run again.

### Arguments

- `--source-repo` (required): source Git repository path.
- `--source-subdir` (required): repo-relative directory to export.
- `--target-dir` (required): output directory for new Git repo.
- `--rev-range` (optional, default `HEAD`): commit range to replay.
- `--force-clean-target` (flag): delete existing target directory before export.
- `--dry-run` (flag): list planned commits only, do not create repository.
- `--limit` (optional, default `0`): replay only first N matched commits (`0` = all).

## Typical Workflow

1. Identify subdirectory and revision range in source repo.
2. Execute dry-run and inspect commit list.
3. Export into an empty target directory.
4. Verify target history (`git log --oneline`) and content.
5. Add remote and push if needed.

More command examples are in `doc/command-examples.md`.

## Notes and Limitations

- The script replays snapshots, not raw patch hunks.
- Merge topology is flattened into a linear history based on selected commits.
- Rename detection depends on path history visible to `git rev-list ... -- <subdir>`.
- Always validate result history before publishing the new repository.

## Project Structure

- `src/run.py`: main CLI script.
- `doc/command-examples.md`: practical command examples.
- `requirements.txt`: dependency declaration (currently no runtime dependencies).

## License

This project is licensed under the GNU LGPL v3.0. See `LICENSE`.
