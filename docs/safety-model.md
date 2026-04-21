# Safety model

`oscleaner` is designed to make the safe path the default path.

## Default behavior

- The default command runs `audit` mode only.
- Cleanup mode is still non-destructive until `--apply` and `--confirm` are both present.
- Reports are generated before any deletion is attempted.
- Actions are written to a log file for review.

## Protected areas

The tool refuses to target or recurse into paths that look like:

- `Documents`, `Desktop`, `Downloads`, `Pictures`, `Videos`, `Music`
- Git repositories or directories containing `.git`
- Common cloud-sync roots such as `OneDrive`, `Dropbox`, `Google Drive`, `iCloud Drive`
- Common developer-workspace roots such as `Dev`, `Developer`, `Projects`, `Repos`, `Workspace`, `Code`, `src`

## Cleanup scope

The project only audits or cleans:

- User temp directories
- User cache directories
- Trash / Recycle Bin where practical
- Linux `/tmp` with age and ownership filtering

Anything outside those allowlisted targets is excluded by design.

## Non-goals

The tool does not:

- Modify the Windows registry
- Change startup items automatically
- Disable services automatically
- Uninstall software automatically
- Perform broad root-level wildcard deletion
- Assume sudo or admin approval

## Approval boundaries

Admin or privileged operations are intentionally left manual. If a target would likely require elevated access, the project reports it and leaves the execution step to the operator.
