# Unsupported or risky targets

The following targets are intentionally not cleaned automatically:

- Home directories broadly
- `Documents`, `Desktop`, `Downloads`, `Pictures`, `Videos`, `Music`
- Source repositories and folders containing `.git`
- Cloud-sync directories
- Arbitrary large folders found outside allowlisted cache/temp roots
- Browser profiles broadly outside safe cache paths
- System files and operating-system directories
- Windows registry locations
- Startup folders, launch agents, services, or scheduled tasks
- Application uninstall data
- Linux package caches that require elevated privileges
- Homebrew cleanup execution without explicit manual review

These are reported only as manual-review areas when relevant.
