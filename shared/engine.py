from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from shared.safety import contains_excluded_fragment, is_protected_path, is_within_allowed_root
from shared.utils import (
    current_uid,
    ensure_parent,
    format_bytes,
    iter_accessible_children,
    now_utc_iso,
    path_owner_uid,
    safe_disk_usage,
    write_json,
)


@dataclass
class Target:
    id: str
    label: str
    path: Path
    cleanup_supported: bool
    allowed_root: Path
    protected: bool = False
    kind: str = "directory"
    age_days: int | None = None
    requires_opt_in: bool = False
    opt_in_flag: str | None = None
    note: str | None = None


class HousekeepingEngine:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.system = platform.system()
        self.home = Path.home()
        self.max_children_per_target = 250

    def run(
        self,
        *,
        mode: str,
        confirm: bool,
        apply: bool,
        json_out: Path | None,
        log_file: Path | None,
        age_days: int | None,
        max_items: int | None,
        include_system_temp: bool,
        include_package_cache: bool,
        include_homebrew: bool,
    ) -> dict[str, Any]:
        dry_run = not (mode == "cleanup" and apply and confirm)
        effective_age_days = age_days or self.config["age_days_tmp_cleanup"]
        effective_max_items = max_items or self.config["max_largest_entries"]
        log_path = log_file or Path("logs") / f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
        ensure_parent(log_path)

        before_usage = self._collect_disk_usage()
        targets = self._build_targets(
            age_days=effective_age_days,
            include_system_temp=include_system_temp,
        )
        audit_targets = [self._audit_target(target, effective_max_items) for target in targets]

        actions: list[dict[str, Any]] = []
        recommendations = self._build_recommendations(include_package_cache, include_homebrew)
        if mode == "cleanup":
            for target in targets:
                actions.append(self._cleanup_target(target, dry_run=dry_run))

        after_usage = self._collect_disk_usage()
        disk_usage = self._merge_disk_usage(before_usage, after_usage)

        report = {
            "meta": {
                "platform": self.system,
                "generated_at": now_utc_iso(),
                "mode": mode,
                "dry_run": dry_run,
                "confirm": confirm,
                "log_file": str(log_path),
            },
            "audit": {
                "disk_usage": disk_usage,
                "targets": audit_targets,
            },
            "actions": actions,
            "recommendations": recommendations,
        }

        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(report, indent=2))
            handle.write("\n")

        if json_out:
            write_json(json_out, report, indent=self.config["json_indent"])

        return report

    def _collect_disk_usage(self) -> list[dict[str, Any]]:
        candidates: list[tuple[str, Path]] = [("Home volume", self.home)]
        if self.system != "Windows":
            candidates.append(("Root volume", Path("/")))
        else:
            system_drive = Path(os.environ.get("SystemDrive", "C:\\"))
            candidates.append(("System drive", system_drive))

        results = []
        for label, path in candidates:
            usage = safe_disk_usage(path)
            if usage:
                results.append({"label": label, "path": str(path), "usage": usage})
        return results

    def _merge_disk_usage(self, before: list[dict[str, Any]], after: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_label = {entry["label"]: entry for entry in after}
        merged = []
        for entry in before:
            after_entry = by_label.get(entry["label"], {})
            merged.append(
                {
                    "label": entry["label"],
                    "path": entry["path"],
                    "before": entry["usage"],
                    "after": after_entry.get("usage"),
                }
            )
        return merged

    def _build_targets(self, *, age_days: int, include_system_temp: bool) -> list[Target]:
        if self.system == "Windows":
            return self._windows_targets(include_system_temp)
        if self.system == "Darwin":
            return self._macos_targets()
        return self._linux_targets(age_days)

    def _windows_targets(self, include_system_temp: bool) -> list[Target]:
        local_app_data = Path(os.environ.get("LOCALAPPDATA", self.home / "AppData/Local"))
        user_temp = Path(os.environ.get("TEMP", local_app_data / "Temp"))
        targets = [
            Target("win-user-temp", "Windows user temp", user_temp, True, user_temp),
            Target(
                "win-user-cache",
                "Windows safe cache",
                local_app_data / "Microsoft/Windows/INetCache",
                True,
                local_app_data / "Microsoft/Windows/INetCache",
            ),
            Target(
                "win-crash-dumps",
                "Windows crash dumps",
                local_app_data / "CrashDumps",
                True,
                local_app_data / "CrashDumps",
            ),
            Target(
                "win-recycle-bin",
                "Windows Recycle Bin",
                Path(os.environ.get("SystemDrive", "C:\\")) / "$Recycle.Bin",
                True,
                Path(os.environ.get("SystemDrive", "C:\\")) / "$Recycle.Bin",
                kind="windows_recycle_bin",
            ),
        ]
        if include_system_temp:
            system_root = Path(os.environ.get("SystemRoot", "C:\\Windows"))
            targets.append(
                Target(
                    "win-system-temp",
                    "Windows system temp",
                    system_root / "Temp",
                    True,
                    system_root / "Temp",
                    requires_opt_in=True,
                    opt_in_flag="--include-system-temp",
                    note="May require admin privileges depending on system configuration.",
                )
            )
        return targets

    def _macos_targets(self) -> list[Target]:
        targets = [
            Target(
                "mac-user-cache",
                "macOS user caches",
                self.home / "Library/Caches",
                True,
                self.home / "Library/Caches",
            ),
            Target(
                "mac-trash",
                "macOS Trash",
                self.home / ".Trash",
                True,
                self.home / ".Trash",
            ),
        ]
        temp_env = os.environ.get("TMPDIR")
        if temp_env:
            temp_dir = Path(temp_env)
            targets.insert(
                1,
                Target(
                    "mac-user-temp",
                    "macOS user temp",
                    temp_dir,
                    True,
                    temp_dir,
                ),
            )
        return targets

    def _linux_targets(self, age_days: int) -> list[Target]:
        return [
            Target(
                "linux-user-cache",
                "Linux user cache",
                self.home / ".cache",
                True,
                self.home / ".cache",
            ),
            Target(
                "linux-user-trash",
                "Linux user trash",
                self.home / ".local/share/Trash/files",
                True,
                self.home / ".local/share/Trash/files",
            ),
            Target(
                "linux-tmp",
                "Linux /tmp old user-owned files",
                Path("/tmp"),
                True,
                Path("/tmp"),
                age_days=age_days,
            ),
        ]

    def _build_recommendations(self, include_package_cache: bool, include_homebrew: bool) -> list[str]:
        recommendations: list[str] = []
        recommendations.append(
            "Review startup-impact tools manually; this project reports safe cleanup opportunities but does not disable startup apps automatically."
        )

        if self.system == "Windows":
            recommendations.append(
                "For deeper Windows cleanup, review Storage Sense or Disk Cleanup manually before enabling anything persistent."
            )
        elif self.system == "Darwin":
            if include_homebrew and shutil.which("brew"):
                recommendations.append(
                    "Homebrew detected. Review `brew cleanup -s --prune=all --dry-run` manually before any package-cache cleanup."
                )
        else:
            if include_package_cache:
                distro = self._detect_linux_distro()
                command = {
                    "apt": "sudo apt clean",
                    "dnf": "sudo dnf clean all",
                    "pacman": "sudo paccache -r",
                }.get(distro, "Review your distro package cache policy manually.")
                recommendations.append(
                    f"Package cache guidance for {distro or 'unknown distro'}: {command}"
                )
        return recommendations

    def _detect_linux_distro(self) -> str | None:
        for candidate in ("apt", "dnf", "pacman"):
            if shutil.which(candidate):
                return candidate
        return None

    def _audit_target(self, target: Target, max_items: int) -> dict[str, Any]:
        exists = target.path.exists()
        estimated = self._estimate_target_bytes(target) if exists else 0
        largest_entries = self._largest_entries(target.path, max_items, target) if exists else []
        return {
            "id": target.id,
            "label": target.label,
            "path": str(target.path),
            "exists": exists,
            "cleanup_supported": target.cleanup_supported,
            "estimated_reclaimable_bytes": estimated,
            "largest_entries": largest_entries,
            "note": target.note,
        }

    def _estimate_target_bytes(self, target: Target) -> int:
        total = 0
        for child in self._iter_cleanup_candidates(target):
            total += self._fast_path_size(child)
        return total

    def _largest_entries(self, path: Path, max_items: int, target: Target) -> list[dict[str, Any]]:
        entries = []
        for index, child in enumerate(iter_accessible_children(path)):
            if index >= self.max_children_per_target:
                break
            if not self._cleanup_candidate_allowed(child, target):
                continue
            entries.append({"name": child.name, "size_bytes": self._fast_path_size(child)})
        entries.sort(key=lambda item: item["size_bytes"], reverse=True)
        return entries[:max_items]

    def _cleanup_target(self, target: Target, *, dry_run: bool) -> dict[str, Any]:
        if not target.path.exists():
            return {
                "label": target.label,
                "status": "skipped",
                "estimated_bytes": 0,
                "detail": "Path does not exist on this system.",
            }

        estimated = self._estimate_target_bytes(target)
        if target.kind == "windows_recycle_bin":
            return self._cleanup_windows_recycle_bin(target, dry_run, estimated)

        deleted = 0
        skipped = 0
        for child in self._iter_cleanup_candidates(target):
            if not self._cleanup_candidate_allowed(child, target):
                skipped += 1
                continue
            size = self._fast_path_size(child)
            if not dry_run:
                self._delete_path(child)
            deleted += size

        status = "dry-run" if dry_run else "applied"
        return {
            "label": target.label,
            "status": status,
            "estimated_bytes": estimated,
            "detail": f"{'Would remove' if dry_run else 'Removed'} {format_bytes(deleted)}; skipped {skipped} protected items.",
        }

    def _cleanup_windows_recycle_bin(self, target: Target, dry_run: bool, estimated: int) -> dict[str, Any]:
        if self.system != "Windows":
            return {
                "label": target.label,
                "status": "skipped",
                "estimated_bytes": estimated,
                "detail": "Windows-only cleanup action.",
            }

        if dry_run:
            return {
                "label": target.label,
                "status": "dry-run",
                "estimated_bytes": estimated,
                "detail": "Would invoke Clear-RecycleBin after explicit confirmation.",
            }

        try:
            subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Clear-RecycleBin -Force",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            detail = "Recycle Bin cleared with Clear-RecycleBin."
            status = "applied"
        except (OSError, subprocess.CalledProcessError) as exc:
            detail = f"Failed to clear Recycle Bin: {exc}"
            status = "error"
        return {
            "label": target.label,
            "status": status,
            "estimated_bytes": estimated,
            "detail": detail,
        }

    def _iter_cleanup_candidates(self, target: Target) -> list[Path]:
        if target.kind == "windows_recycle_bin":
            return list(iter_accessible_children(target.path))
        if target.id == "linux-tmp":
            return [path for path in iter_accessible_children(target.path) if self._linux_tmp_candidate(path, target.age_days or 0)]
        return list(iter_accessible_children(target.path))

    def _linux_tmp_candidate(self, path: Path, age_days: int) -> bool:
        try:
            stat = path.stat()
        except OSError:
            return False
        cutoff = datetime.now(timezone.utc) - timedelta(days=age_days)
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        if modified > cutoff:
            return False
        uid = current_uid()
        owner_uid = path_owner_uid(path)
        if uid is None:
            return False
        return owner_uid == uid

    def _cleanup_candidate_allowed(self, path: Path, target: Target) -> bool:
        if not is_within_allowed_root(path, target.allowed_root):
            return False
        if contains_excluded_fragment(path, self.config["excluded_path_fragments"]):
            return False
        if is_protected_path(path, self.config["protected_path_names"], self.home):
            return False
        return True

    def _fast_path_size(self, path: Path) -> int:
        if self.system != "Windows":
            try:
                result = subprocess.run(
                    ["du", "-sk", str(path)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                size_kb = int(result.stdout.split()[0])
                return size_kb * 1024
            except (OSError, subprocess.CalledProcessError, ValueError, IndexError):
                pass
        return self._safe_path_size(path)

    def _safe_path_size(self, path: Path) -> int:
        try:
            if path.is_file() or path.is_symlink():
                return path.stat().st_size
            total = 0
            for root, dirs, files in os.walk(path, topdown=True):
                root_path = Path(root)
                dirs[:] = [
                    directory
                    for directory in dirs
                    if not is_protected_path(root_path / directory, self.config["protected_path_names"], self.home)
                    and not contains_excluded_fragment(root_path / directory, self.config["excluded_path_fragments"])
                ]
                for filename in files:
                    file_path = root_path / filename
                    if contains_excluded_fragment(file_path, self.config["excluded_path_fragments"]):
                        continue
                    try:
                        total += file_path.stat().st_size
                    except OSError:
                        continue
            return total
        except OSError:
            return 0

    def _delete_path(self, path: Path) -> None:
        if path.is_symlink() or path.is_file():
            try:
                path.unlink()
            except OSError:
                return
            return
        shutil.rmtree(path, ignore_errors=True)
