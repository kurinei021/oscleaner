from __future__ import annotations

from pathlib import Path


def normalize_path(path: Path) -> Path:
    try:
        return path.expanduser().resolve(strict=False)
    except OSError:
        return path.expanduser()


def looks_like_repo(path: Path) -> bool:
    current = normalize_path(path)
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return True
    return False


def contains_excluded_fragment(path: Path, fragments: list[str]) -> bool:
    normalized = str(normalize_path(path)).lower()
    return any(fragment.lower() in normalized for fragment in fragments)


def is_protected_path(path: Path, protected_names: list[str], home: Path | None = None) -> bool:
    candidate = normalize_path(path)
    lower_parts = {part.lower() for part in candidate.parts}
    if any(name.lower() in lower_parts for name in protected_names):
        return True

    if looks_like_repo(candidate):
        return True

    cloud_markers = {"onedrive", "dropbox", "google drive", "icloud drive", "syncthing"}
    if any(marker in part.lower() for part in candidate.parts for marker in cloud_markers):
        return True

    if home:
        home = normalize_path(home)
        dev_markers = {"dev", "developer", "projects", "repos", "repositories", "workspace", "workspaces", "code", "src"}
        try:
            relative = candidate.relative_to(home)
        except ValueError:
            relative = None
        if relative and relative.parts and relative.parts[0].lower() in dev_markers:
            return True

    return False


def is_within_allowed_root(path: Path, allowed_root: Path) -> bool:
    candidate = normalize_path(path)
    root = normalize_path(allowed_root)
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False
