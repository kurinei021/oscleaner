# Supported cleanup targets

## Windows

- `%TEMP%` and `%LOCALAPPDATA%\Temp`
- `%LOCALAPPDATA%\Microsoft\Windows\INetCache`
- `%LOCALAPPDATA%\CrashDumps`
- Recycle Bin through explicit cleanup mode
- `%SystemRoot%\Temp` only when you explicitly opt in and only if the session already has the necessary rights

## macOS

- `~/Library/Caches`
- User temp directory from `$TMPDIR`
- `~/.Trash`
- Homebrew cleanup guidance only when `brew` exists and you explicitly request it in reporting

## Linux

- `~/.cache`
- `~/.local/share/Trash/files`
- `/tmp` entries older than the configured threshold and owned by the current user
- Package-manager cache guidance only after explicit opt-in and distro detection
