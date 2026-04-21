# Setup instructions

## Requirements

- Python 3.9+ recommended
- PowerShell for the Windows wrapper
- A POSIX shell for the macOS and Linux wrappers

No third-party Python packages are required.

## Basic setup

1. Clone or place the repository in a local folder you control.
2. Review [config/example-config.json](/Users/carmie/DevProject/oscleaner/config/example-config.json).
3. Run an audit-only report first:

```bash
python3 safe_start.py
```

## Optional wrapper usage

macOS:

```bash
chmod +x macos/run.sh
./macos/run.sh
```

Linux:

```bash
chmod +x linux/run.sh
./linux/run.sh
```

Windows PowerShell:

```powershell
pwsh -File .\windows\run.ps1
```

## First recommended workflow

1. Run `audit` mode.
2. Review the console summary, JSON report, and log file.
3. Run `cleanup` mode without `--apply` to preview deletion candidates.
4. Only then consider `--mode cleanup --confirm --apply`.

## Local customization

If you want a separate config, copy the example file and pass it with:

```bash
python3 safe_start.py --config path/to/local-config.json
```
