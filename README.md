# oscleaner

`oscleaner` is a conservative, cross-platform device housekeeping toolkit for Windows, macOS, and Linux. It takes the "all-in-one maintenance CLI" idea and rebuilds it around stricter safety: audit-first workflows, protected-path rules, reviewable reports, and controlled cleanup only after explicit approval.

The project is intentionally opinionated:

- Audit first
- Dry-run by default
- No registry changes
- No startup/service changes by default
- No broad system deletion
- No user-content deletion
- No one-click aggressive mode

## Why this direction

`oscleaner` is meant to feel like a polished local housekeeping tool rather than a loose collection of scripts, but it deliberately avoids the riskiest categories of system modification. The product direction is:

- Multi-command CLI instead of a single one-shot script
- Read-only inspection before any destructive step
- Cross-platform safe cleanup targets only
- Human-friendly console output and JSON for automation
- Recommendations for manual follow-up rather than hidden system changes

## Commands

```bash
python3 oscleaner.py audit
python3 oscleaner.py clean
python3 oscleaner.py analyze
python3 oscleaner.py doctor
python3 oscleaner.py status
```

- `audit`: read-only audit of safe cleanup targets plus large-location summaries
- `clean`: preview or apply cleanup within safe targets only, with before/after disk comparison
- `analyze`: investigate what is taking space across visible locations and category totals
- `doctor`: highlight space pressure, cleanup caveats, and housekeeping recommendations
- `status`: quick current-state snapshot with only the top space signals

The legacy [safe_start.py](/Users/carmie/DevProject/oscleaner/safe_start.py:1) entrypoint still exists and defaults to `audit`.

## Project layout

- `oscleaner.py`: primary multi-command CLI entrypoint
- `safe_start.py`: compatibility entrypoint that runs audit mode by default
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
python3 oscleaner.py audit
```

Use the platform wrapper instead:

```bash
./macos/run.sh
./linux/run.sh
pwsh -File .\windows\run.ps1
```

Write a JSON report:

```bash
python3 oscleaner.py audit --json-out logs/audit-report.json
```

Preview cleanup without deleting anything:

```bash
python3 oscleaner.py clean
```

Apply cleanup only after explicit approval:

```bash
python3 oscleaner.py clean --confirm --apply
```

Inspect what is actually taking space in user-visible locations:

```bash
python3 oscleaner.py analyze
```

Get a concise device-health summary:

```bash
python3 oscleaner.py doctor
python3 oscleaner.py status
```

## Safety model

The tool only targets a narrow allowlist of cleanup locations such as user temp directories, cache directories, and Trash/Recycle Bin locations. It refuses to delete protected paths or anything that appears to be user content, a git repository, a cloud-sync directory, or a developer workspace.

Three conditions must all be true before files are deleted:

1. You selected the `clean` command.
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
