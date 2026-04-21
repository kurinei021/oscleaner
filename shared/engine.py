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
    kind: str = "directory"
    age_days: int | None = None
    note: str | None = None


@dataclass
class RunOptions:
    command: str
    confirm: bool = False
    apply: bool = False
    json_out: Path | None = None
    log_file: Path | None = None
    age_days: int | None = None
    max_items: int | None = None
    include_system_temp: bool = False
    include_package_cache: bool = False
    include_homebrew: bool = False


class HousekeepingEngine:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.system = platform.system()
        self.home = Path.home()
        self.max_children_per_target = 250

    def run(self, options: RunOptions) -> dict[str, Any]:
        effective_age_days = options.age_days or self.config["age_days_tmp_cleanup"]
        effective_max_items = options.max_items or self.config["max_largest_entries"]
        dry_run = not (options.command == "clean" and options.apply and options.confirm)
        log_path = options.log_file or Path("logs") / f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
        ensure_parent(log_path)

        before_usage = self._collect_disk_usage()
        cleanup_targets = self._build_cleanup_targets(
            age_days=effective_age_days,
            include_system_temp=options.include_system_temp,
        )
        cleanup_audit = [self._audit_cleanup_target(target, effective_max_items) for target in cleanup_targets]
        largest_locations = self._collect_largest_locations(effective_max_items)
        total_reclaimable = sum(item["estimated_reclaimable_bytes"] for item in cleanup_audit)
        recommendations = self._build_recommendations(options.include_package_cache, options.include_homebrew)
        health_checks = self._build_health_checks(before_usage, cleanup_audit)

        actions: list[dict[str, Any]] = []
        if options.command == "clean":
            for target in cleanup_targets:
                actions.append(self._cleanup_target(target, dry_run=dry_run))

        after_usage = self._collect_disk_usage()
        disk_usage = self._merge_disk_usage(before_usage, after_usage)
        report = {
            "meta": {
                "platform": self.system,
                "generated_at": now_utc_iso(),
                "command": options.command,
                "dry_run": dry_run,
                "confirm": options.confirm,
                "apply": options.apply,
                "log_file": str(log_path),
            },
            "overview": {
                "total_reclaimable_bytes": total_reclaimable,
                "largest_cleanup_target": self._largest_cleanup_target(cleanup_audit),
                "cleanup_target_count": len(cleanup_audit),
            },
            "audit": {
                "disk_usage": disk_usage,
                "targets": cleanup_audit,
                "largest_locations": largest_locations,
            },
            "health_checks": health_checks,
            "actions": actions,
            "recommendations": recommendations,
        }

        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(report, indent=2))
            handle.write("\n")

        if options.json_out:
            write_json(options.json_out, report, indent=self.config["json_indent"])

        return report

    def _collect_disk_usage(self) -> list[dict[str, Any]]:
        candidates: list[tuple[str, Path]] = [("Home volume", self.home)]
        if self.system == "Windows":
            candidates.append(("System drive", Path(os.environ.get("SystemDrive", "C:\\"))))
        else:
            candidates.append(("Root volume", Path("/")))

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

    def _build_cleanup_targets(self, *, age_days: int, include_system_temp: bool) -> list[Target]:
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
                note="Only cleared after explicit clean --confirm --apply.",
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
                note="Only entries older than the configured age and owned by the current user are eligible.",
            ),
        ]

    def _collect_largest_locations(self, max_items: int) -> list[dict[str, Any]]:
        locations = []
        for child in self._iter_analysis_roots():
            size_bytes = self._fast_path_size(child)
            locations.append(
                {
                    "label": child.name or str(child),
                    "path": str(child),
                    "size_bytes": size_bytes,
                    "category": self._categorize_location(child),
                }
            )
        locations.sort(key=lambda item: item["size_bytes"], reverse=True)
        return locations[:max_items]

    def _iter_analysis_roots(self) -> list[Path]:
        candidates: list[Path] = []
        if self.home.exists():
            for index, child in enumerate(iter_accessible_children(self.home)):
                if index >= self.max_children_per_target:
                    break
                if child.name.startswith("."):
                    continue
                candidates.append(child)

        platform_specific = []
        if self.system == "Darwin":
            platform_specific = [self.home / "Library", self.home / "Applications"]
        elif self.system == "Windows":
            platform_specific = [
                Path(os.environ.get("LOCALAPPDATA", self.home / "AppData/Local")),
                Path(os.environ.get("APPDATA", self.home / "AppData/Roaming")),
            ]
        else:
            platform_specific = [self.home / ".cache", self.home / ".local/share"]

        for candidate in platform_specific:
            if candidate.exists():
                candidates.append(candidate)

        deduped: list[Path] = []
        seen = set()
        for candidate in candidates:
            normalized = str(candidate.resolve(strict=False))
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(candidate)
        return deduped

    def _categorize_location(self, path: Path) -> str:
        lower = path.name.lower()
        if lower in {"downloads", "documents", "desktop", "pictures", "videos", "music"}:
            return "user-content"
        if "cache" in lower or lower == "library":
            return "cache-or-library"
        if lower in {"applications", "appdata"}:
            return "apps"
        if lower in {"dev", "developer", "projects", "code", "src"}:
            return "developer"
        return "home"

    def _largest_cleanup_target(self, cleanup_audit: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not cleanup_audit:
            return None
        return max(cleanup_audit, key=lambda item: item["estimated_reclaimable_bytes"])

    def _build_health_checks(
        self, disk_usage: list[dict[str, Any]], cleanup_audit: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        checks = []
        total_reclaimable = sum(item["estimated_reclaimable_bytes"] for item in cleanup_audit)
        primary_volume = disk_usage[0]["usage"] if disk_usage else {}
        total = primary_volume.get("total", 0)
        free = primary_volume.get("free", 0)
        free_ratio = (free / total) if total else 1.0

        if free_ratio < 0.1:
            checks.append(
                {
                    "severity": "high",
                    "title": "Low free space",
                    "detail": f"Free space is below 10% on the primary volume ({format_bytes(free)} remaining).",
                }
            )
        elif free_ratio < 0.2:
            checks.append(
                {
                    "severity": "medium",
                    "title": "Free space is tightening",
                    "detail": f"Free space is below 20% on the primary volume ({format_bytes(free)} remaining).",
                }
            )

        if total_reclaimable > 5 * 1024 * 1024 * 1024:
            checks.append(
                {
                    "severity": "medium",
                    "title": "Large reclaim opportunity",
                    "detail": f"Safe cleanup targets currently account for about {format_bytes(total_reclaimable)}.",
                }
            )

        if not checks:
            checks.append(
                {
                    "severity": "info",
                    "title": "No urgent housekeeping issues",
                    "detail": "The current snapshot does not show a critical low-space condition in the audited safe targets.",
                }
            )
        return checks

    def _build_recommendations(self, include_package_cache: bool, include_homebrew: bool) -> list[str]:
        recommendations = [
            "Review startup-impact tools manually; oscleaner reports opportunities but does not disable startup items automatically."
        ]

        if self.system == "Windows":
            recommendations.append(
                "If you need deeper Windows cleanup, review Storage Sense or Disk Cleanup manually before enabling any persistent behavior."
            )
        elif self.system == "Darwin":
            if include_homebrew and shutil.which("brew"):
                recommendations.append(
                    "Homebrew detected. Review `brew cleanup -s --prune=all --dry-run` manually before opting into package-cache cleanup."
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

        recommendations.append(
            "Use dry-run first for every destructive path. Real cleanup still requires both --confirm and --apply."
        )
        return recommendations

    def _detect_linux_distro(self) -> str | None:
        for candidate in ("apt", "dnf", "pacman"):
            if shutil.which(candidate):
                return candidate
        return None

    def _audit_cleanup_target(self, target: Target, max_items: int) -> dict[str, Any]:
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
                ["powershell", "-NoProfile", "-Command", "Clear-RecycleBin -Force"],
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
            return [
                path
                for path in iter_accessible_children(target.path)
                if self._linux_tmp_candidate(path, target.age_days or 0)
            ]
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
