# Scheduler guidance

All examples below default to audit-only mode.

## Windows Task Scheduler

Program/script:

```text
python
```

Arguments:

```text
C:\path\to\oscleaner\oscleaner.py audit --json-out C:\path\to\oscleaner\logs\scheduled-audit.json
```

Recommended settings:

- Run whether user is logged in or not only if your Python path and permissions are stable
- Do not enable highest privileges unless you have separately reviewed why that is necessary
- Start in the repository root so relative config and log paths resolve predictably

## macOS launchd

Example `plist` command arguments:

```xml
<array>
  <string>/usr/bin/python3</string>
  <string>/Users/your-user/path/to/oscleaner/oscleaner.py</string>
  <string>audit</string>
  <string>--json-out</string>
  <string>/Users/your-user/path/to/oscleaner/logs/launchd-audit.json</string>
</array>
```

Keep the job user-scoped and review filesystem access before changing it to cleanup mode.

## Linux cron

```cron
30 9 * * 6 /usr/bin/python3 /home/your-user/path/to/oscleaner/oscleaner.py audit --json-out /home/your-user/path/to/oscleaner/logs/cron-audit.json
```

## Linux systemd user timer

Service `ExecStart` example:

```text
/usr/bin/python3 /home/your-user/path/to/oscleaner/oscleaner.py audit --json-out /home/your-user/path/to/oscleaner/logs/systemd-audit.json
```

Use a user unit, not a system-wide root unit, unless you have a separate approval process for elevated execution.
