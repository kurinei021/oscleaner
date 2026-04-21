# Testing safely

## Automated checks

Run:

```bash
python3 -m unittest discover -s tests
```

The test suite validates:

- Protected path detection
- Allowed-root checks
- Exclusion fragment logic
- Console report rendering

## Manual validation checklist

1. Run `python3 safe_start.py` and confirm the output is audit-only.
2. Run `python3 oscleaner.py clean` and confirm it stays dry-run.
3. Create a temporary test folder inside a cache directory, then rerun cleanup preview and verify only that folder is proposed.
4. Create a folder named like a protected path inside a temp area, such as `Documents`, and verify it is skipped.
5. On Linux, create a fresh file in `/tmp` and confirm it is not included until it is older than the configured threshold.
6. Review the JSON report and log file before trying any real cleanup.

## Suggested first live test

Use a throwaway cache folder and a dry-run first:

```bash
mkdir -p ~/.cache/oscleaner-demo
dd if=/dev/zero of=~/.cache/oscleaner-demo/sample.bin bs=1m count=5
python3 oscleaner.py clean
```

Then remove the test data manually if you do not want to run an applied cleanup.
