# oscleaner

`oscleaner` is a conservative, cross-platform device housekeeping toolkit for Windows, macOS, and Linux. It audits disk usage, highlights safe cleanup opportunities, and performs controlled cleanup only when you explicitly approve it.

The project is intentionally opinionated:

- Audit first
- Dry-run by default
- No registry changes
- No startup/service changes by default
- No broad system deletion
- No user-content deletion
- No one-click aggressive mode

## Project layout

- `safe_start.py`: top-level safe entrypoint that runs audit mode by default
- `shared/`: cross-platform Python safety, reporting, and orchestration code
- `windows/`: PowerShell wrapper and Windows-specific notes
- `macos/`: shell wrapper and macOS-specific notes
- `linux/`: shell wrapper and Linux-specific notes
- `docs/`: safety model, scheduler examples, and testing guidance
- `config/`: example configuration
- `logs/`: run logs and example output
- `tests/`: validation for safety guards and reporting

## Quick start

Audit only on the current platform:

```bash
python3 safe_start.py
```

Use the platform wrapper instead:

```bash
./macos/run.sh
./linux/run.sh
pwsh -File .\windows\run.ps1
```

Write a JSON report:

```bash
python3 safe_start.py --json-out logs/audit-report.json
```

Preview cleanup without deleting anything:

```bash
python3 safe_start.py --mode cleanup
```

Apply cleanup only after explicit approval:

```bash
python3 safe_start.py --mode cleanup --confirm --apply
```

## Safety model

The tool only targets a narrow allowlist of cleanup locations such as user temp directories, cache directories, and Trash/Recycle Bin locations. It refuses to delete protected paths or anything that appears to be user content, a git repository, a cloud-sync directory, or a developer workspace.

Three conditions must all be true before files are deleted:

1. You selected `--mode cleanup`.
2. You passed `--confirm`.
3. You passed `--apply`.

Without all three, cleanup actions are logged as dry-run previews only.

## Supported targets

Supported targets vary by platform, but include:

- User temp directories
- User cache directories
- Trash / Recycle Bin where practical
- Linux `/tmp` only with age filtering and ownership checks
- Optional package-manager or Homebrew cleanup guidance only after explicit opt-in

See [docs/supported-targets.md](/Users/carmie/DevProject/oscleaner/docs/supported-targets.md) and [docs/unsupported-targets.md](/Users/carmie/DevProject/oscleaner/docs/unsupported-targets.md).

## Configuration

An example configuration is available at [config/example-config.json](/Users/carmie/DevProject/oscleaner/config/example-config.json). It includes:

- Protected paths
- Excluded patterns
- Default age thresholds
- JSON report preferences
- Optional package-cache and Homebrew switches

## Setup

Setup instructions are documented in [docs/setup.md](/Users/carmie/DevProject/oscleaner/docs/setup.md).

## Safe testing

Run the test suite:

```bash
python3 -m unittest discover -s tests
```

See [docs/testing.md](/Users/carmie/DevProject/oscleaner/docs/testing.md) for a safe validation checklist.

## Scheduler examples

Scheduler examples are documented in [docs/scheduling.md](/Users/carmie/DevProject/oscleaner/docs/scheduling.md). Every example defaults to audit-only mode.

## Manual approval still required

The following remain manual or guidance-based by design:

- Package-manager cache cleanup that may need admin access
- Homebrew cleanup execution
- Startup or service changes
- App uninstall actions
- Any operation requiring elevated privileges
