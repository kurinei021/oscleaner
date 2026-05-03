from __future__ import annotations

import json
import os
import platform
import shutil
import socket
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
    analyze_path: Path | None = None
    analyze_depth: int | None = None
    view: str = "text"


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

        report = self._build_report(
            options=options,
            dry_run=dry_run,
            age_days=effective_age_days,
            max_items=effective_max_items,
            log_path=log_path,
        )

        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(report, indent=2))
            handle.write("\n")

        if options.json_out:
            write_json(options.json_out, report, indent=self.config["json_indent"])

        return report

    def _build_report(
        self,
        *,
        options: RunOptions,
        dry_run: bool,
        age_days: int,
        max_items: int,
        log_path: Path,
    ) -> dict[str, Any]:
        builders = {
            "audit": self._build_audit_report,
            "clean": self._build_clean_report,
            "analyze": self._build_analyze_report,
            "doctor": self._build_doctor_report,
            "status": self._build_status_report,
        }
        builder = builders.get(options.command, self._build_audit_report)
        return builder(options=options, dry_run=dry_run, age_days=age_days, max_items=max_items, log_path=log_path)

    def _base_meta(self, *, options: RunOptions, dry_run: bool, log_path: Path) -> dict[str, Any]:
        return {
            "platform": self.system,
            "generated_at": now_utc_iso(),
            "command": options.command,
            "view": options.view,
            "dry_run": dry_run,
            "confirm": options.confirm,
            "apply": options.apply,
            "log_file": str(log_path),
        }

    def _build_audit_report(
        self, *, options: RunOptions, dry_run: bool, age_days: int, max_items: int, log_path: Path
    ) -> dict[str, Any]:
        disk_usage = self._snapshot_disk_usage()
        cleanup_targets = self._audit_cleanup_targets(age_days=age_days, max_items=max_items, include_system_temp=options.include_system_temp)
        largest_locations = self._collect_largest_locations(max_items)
        recommendations = self._build_recommendations(options.include_package_cache, options.include_homebrew)
        health_checks = self._build_health_checks(disk_usage, cleanup_targets)
        return {
            "meta": self._base_meta(options=options, dry_run=dry_run, log_path=log_path),
            "overview": self._build_overview(cleanup_targets),
            "disk_usage": disk_usage,
            "cleanup_targets": cleanup_targets,
            "largest_locations": largest_locations,
            "health_checks": health_checks,
            "recommendations": recommendations,
        }

    def _build_clean_report(
        self, *, options: RunOptions, dry_run: bool, age_days: int, max_items: int, log_path: Path
    ) -> dict[str, Any]:
        before_usage = self._collect_disk_usage()
        targets = self._build_cleanup_targets(age_days=age_days, include_system_temp=options.include_system_temp)
        cleanup_targets = [self._audit_cleanup_target(target, max_items) for target in targets]
        actions = [self._cleanup_target(target, dry_run=dry_run) for target in targets]
        after_usage = self._collect_disk_usage()
        recommendations = self._build_recommendations(options.include_package_cache, options.include_homebrew)
        return {
            "meta": self._base_meta(options=options, dry_run=dry_run, log_path=log_path),
            "overview": self._build_overview(cleanup_targets),
            "disk_usage": self._merge_disk_usage(before_usage, after_usage),
            "cleanup_targets": cleanup_targets,
            "actions": actions,
            "recommendations": recommendations,
        }

    def _build_analyze_report(
        self, *, options: RunOptions, dry_run: bool, age_days: int, max_items: int, log_path: Path
    ) -> dict[str, Any]:
        analyze_root = options.analyze_path or self.home
        analyze_depth = max(1, options.analyze_depth or 2)
        locations = self._collect_largest_locations(max_items=max_items * 2, root=analyze_root, depth=analyze_depth)
        categories = self._group_locations_by_category(locations, max_items)
        cleanup_targets = self._audit_cleanup_targets(age_days=age_days, max_items=3, include_system_temp=options.include_system_temp)
        return {
            "meta": self._base_meta(options=options, dry_run=dry_run, log_path=log_path),
            "focus": {
                "scan_scope": "space investigation across visible locations",
                "location_count": len(locations),
                "root": str(analyze_root),
                "depth": analyze_depth,
            },
            "largest_locations": locations[:max_items],
            "category_totals": categories,
            "cleanup_summary": self._build_overview(cleanup_targets),
        }

    def _build_doctor_report(
        self, *, options: RunOptions, dry_run: bool, age_days: int, max_items: int, log_path: Path
    ) -> dict[str, Any]:
        disk_usage = self._snapshot_disk_usage()
        cleanup_targets = self._audit_cleanup_targets(age_days=age_days, max_items=3, include_system_temp=options.include_system_temp)
        health_checks = self._build_health_checks(disk_usage, cleanup_targets)
        largest_locations = self._collect_largest_locations(max_items=max_items * 2, root=self.home, depth=2)
        risks = self._build_risk_findings(cleanup_targets, largest_locations)
        recommendations = self._build_recommendations(options.include_package_cache, options.include_homebrew)
        return {
            "meta": self._base_meta(options=options, dry_run=dry_run, log_path=log_path),
            "health_checks": health_checks,
            "risk_findings": risks,
            "recommendations": recommendations,
            "overview": self._build_overview(cleanup_targets),
        }

    def _build_status_report(
        self, *, options: RunOptions, dry_run: bool, age_days: int, max_items: int, log_path: Path
    ) -> dict[str, Any]:
        disk_usage = self._snapshot_disk_usage()
        cleanup_targets = self._audit_cleanup_targets(age_days=age_days, max_items=1, include_system_temp=options.include_system_temp)
        top_targets = sorted(cleanup_targets, key=lambda item: item["estimated_reclaimable_bytes"], reverse=True)[:2]
        return {
            "meta": self._base_meta(options=options, dry_run=dry_run, log_path=log_path),
            "status": {
                "primary_volume": disk_usage[0] if disk_usage else None,
                "top_targets": top_targets,
                "safe_reclaimable_bytes": sum(item["estimated_reclaimable_bytes"] for item in cleanup_targets),
            },
            "health_checks": self._build_health_checks(disk_usage, cleanup_targets),
            "system_snapshot": self._build_system_snapshot(disk_usage, cleanup_targets),
        }

    def _build_overview(self, cleanup_targets: list[dict[str, Any]]) -> dict[str, Any]:
        total_reclaimable = sum(item["estimated_reclaimable_bytes"] for item in cleanup_targets)
        largest_target = None
        if cleanup_targets:
            largest_target = max(cleanup_targets, key=lambda item: item["estimated_reclaimable_bytes"])
        return {
            "total_reclaimable_bytes": total_reclaimable,
            "largest_cleanup_target": largest_target,
            "cleanup_target_count": len(cleanup_targets),
        }

    def _snapshot_disk_usage(self) -> list[dict[str, Any]]:
        results = []
        for entry in self._collect_disk_usage():
            results.append(
                {
                    "label": entry["label"],
                    "path": entry["path"],
                    "before": entry["usage"],
                    "after": entry["usage"],
                }
            )
        return results

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
            Target("win-user-cache", "Windows safe cache", local_app_data / "Microsoft/Windows/INetCache", True, local_app_data / "Microsoft/Windows/INetCache"),
            Target("win-crash-dumps", "Windows crash dumps", local_app_data / "CrashDumps", True, local_app_data / "CrashDumps"),
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
            Target("mac-user-cache", "macOS user caches", self.home / "Library/Caches", True, self.home / "Library/Caches"),
            Target("mac-trash", "macOS Trash", self.home / ".Trash", True, self.home / ".Trash"),
        ]
        temp_env = os.environ.get("TMPDIR")
        if temp_env:
            temp_dir = Path(temp_env)
            targets.insert(1, Target("mac-user-temp", "macOS user temp", temp_dir, True, temp_dir))
        return targets

    def _linux_targets(self, age_days: int) -> list[Target]:
        return [
            Target("linux-user-cache", "Linux user cache", self.home / ".cache", True, self.home / ".cache"),
            Target("linux-user-trash", "Linux user trash", self.home / ".local/share/Trash/files", True, self.home / ".local/share/Trash/files"),
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

    def _audit_cleanup_targets(self, *, age_days: int, max_items: int, include_system_temp: bool) -> list[dict[str, Any]]:
        targets = self._build_cleanup_targets(age_days=age_days, include_system_temp=include_system_temp)
        return [self._audit_cleanup_target(target, max_items) for target in targets]

    def _collect_largest_locations(self, max_items: int, root: Path | None = None, depth: int = 1) -> list[dict[str, Any]]:
        locations = []
        for child in self._iter_analysis_roots(root=root, depth=depth):
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

    def _group_locations_by_category(self, locations: list[dict[str, Any]], max_items: int) -> list[dict[str, Any]]:
        grouped: dict[str, int] = {}
        for item in locations:
            grouped[item["category"]] = grouped.get(item["category"], 0) + item["size_bytes"]
        rows = [{"category": category, "size_bytes": size_bytes} for category, size_bytes in grouped.items()]
        rows.sort(key=lambda item: item["size_bytes"], reverse=True)
        return rows[:max_items]

    def _iter_analysis_roots(self, root: Path | None = None, depth: int = 1) -> list[Path]:
        if root is not None:
            return self._walk_analysis_root(root, depth)

        candidates: list[Path] = []
        if self.home.exists():
            for index, child in enumerate(iter_accessible_children(self.home)):
                if index >= self.max_children_per_target:
                    break
                if child.name.startswith("."):
                    continue
                candidates.append(child)

        if self.system == "Darwin":
            platform_specific = [self.home / "Library", self.home / "Applications"]
        elif self.system == "Windows":
            platform_specific = [Path(os.environ.get("LOCALAPPDATA", self.home / "AppData/Local")), Path(os.environ.get("APPDATA", self.home / "AppData/Roaming"))]
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

    def _walk_analysis_root(self, root: Path, depth: int) -> list[Path]:
        if not root.exists():
            return []

        collected: list[Path] = []
        queue: list[tuple[Path, int]] = [(root, 0)]
        seen = set()
        while queue:
            current, level = queue.pop(0)
            normalized = str(current.resolve(strict=False))
            if normalized in seen:
                continue
            seen.add(normalized)

            if level > 0:
                collected.append(current)
            if level >= depth:
                continue

            for index, child in enumerate(iter_accessible_children(current)):
                if index >= self.max_children_per_target:
                    break
                if child.name.startswith(".") and level == 0:
                    continue
                queue.append((child, level + 1))

        return collected

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

    def _build_health_checks(self, disk_usage: list[dict[str, Any]], cleanup_targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        checks = []
        total_reclaimable = sum(item["estimated_reclaimable_bytes"] for item in cleanup_targets)
        primary_volume = disk_usage[0]["before"] if disk_usage else {}
        total = primary_volume.get("total", 0)
        free = primary_volume.get("free", 0)
        free_ratio = (free / total) if total else 1.0

        if free_ratio < 0.1:
            checks.append({"severity": "high", "title": "Low free space", "detail": f"Free space is below 10% on the primary volume ({format_bytes(free)} remaining)."})
        elif free_ratio < 0.2:
            checks.append({"severity": "medium", "title": "Free space is tightening", "detail": f"Free space is below 20% on the primary volume ({format_bytes(free)} remaining)."})

        if total_reclaimable > 5 * 1024 * 1024 * 1024:
            checks.append({"severity": "medium", "title": "Large reclaim opportunity", "detail": f"Safe cleanup targets currently account for about {format_bytes(total_reclaimable)}."})

        if not checks:
            checks.append({"severity": "info", "title": "No urgent housekeeping issues", "detail": "The current snapshot does not show a critical low-space condition in the audited safe targets."})
        return checks

    def _build_risk_findings(
        self, cleanup_targets: list[dict[str, Any]], largest_locations: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        findings = []
        for target in cleanup_targets:
            size_bytes = target["estimated_reclaimable_bytes"]
            if size_bytes > 2 * 1024 * 1024 * 1024:
                findings.append({"severity": "medium", "title": f"{target['label']} is unusually large", "detail": f"This safe target alone accounts for about {format_bytes(size_bytes)}."})
            if target.get("note"):
                findings.append({"severity": "info", "title": f"{target['label']} has caveats", "detail": target["note"]})

        for location in largest_locations[:5]:
            label_lower = location["label"].lower()
            category = location["category"]
            size_bytes = location["size_bytes"]
            if "virtual machine" in label_lower or label_lower.endswith(".utm") or label_lower.endswith(".pvm"):
                findings.append(
                    {
                        "severity": "medium",
                        "title": "Virtual machines are the dominant space consumer",
                        "detail": f"{location['label']} uses about {format_bytes(size_bytes)} and is outside safe auto-clean scope.",
                    }
                )
            elif category == "developer" and size_bytes > 500 * 1024 * 1024:
                findings.append(
                    {
                        "severity": "info",
                        "title": "Developer workspace detected",
                        "detail": f"{location['label']} uses about {format_bytes(size_bytes)} and is excluded from automatic cleanup by design.",
                    }
                )
            elif category == "user-content" and label_lower == "downloads" and size_bytes > 500 * 1024 * 1024:
                findings.append(
                    {
                        "severity": "info",
                        "title": "Downloads may be worth a manual review",
                        "detail": f"Downloads currently use about {format_bytes(size_bytes)}. This is user content and will not be auto-cleaned.",
                    }
                )
            elif location["label"] == "Library" and size_bytes > 2 * 1024 * 1024 * 1024:
                findings.append(
                    {
                        "severity": "info",
                        "title": "Library data is a major storage bucket",
                        "detail": f"Library currently uses about {format_bytes(size_bytes)}. Review caches separately from app data before deleting anything manually.",
                    }
                )

        if not findings:
            findings.append({"severity": "info", "title": "No special cleanup risks surfaced", "detail": "The current safe targets do not show an unusual warning beyond normal review."})
        return findings

    def _build_recommendations(self, include_package_cache: bool, include_homebrew: bool) -> list[str]:
        recommendations = [
            "Review startup-impact tools manually; oscleaner reports opportunities but does not disable startup items automatically."
        ]
        if self.system == "Windows":
            recommendations.append("If you need deeper Windows cleanup, review Storage Sense or Disk Cleanup manually before enabling any persistent behavior.")
        elif self.system == "Darwin":
            if include_homebrew and shutil.which("brew"):
                recommendations.append("Homebrew detected. Review `brew cleanup -s --prune=all --dry-run` manually before opting into package-cache cleanup.")
        else:
            if include_package_cache:
                distro = self._detect_linux_distro()
                command = {"apt": "sudo apt clean", "dnf": "sudo dnf clean all", "pacman": "sudo paccache -r"}.get(
                    distro, "Review your distro package cache policy manually."
                )
                recommendations.append(f"Package cache guidance for {distro or 'unknown distro'}: {command}")
        recommendations.append("Use dry-run first for every destructive path. Real cleanup still requires both --confirm and --apply.")
        return recommendations

    def _build_system_snapshot(
        self, disk_usage: list[dict[str, Any]], cleanup_targets: list[dict[str, Any]]
    ) -> dict[str, Any]:
        primary = disk_usage[0]["before"] if disk_usage else {}
        total = primary.get("total", 0)
        free = primary.get("free", 0)
        free_ratio = (free / total) if total else 1.0
        reclaimable = sum(item["estimated_reclaimable_bytes"] for item in cleanup_targets)
        load_avg = self._load_average()
        memory = self._memory_snapshot()
        health_score = 100
        if free_ratio < 0.2:
            health_score -= 15
        if free_ratio < 0.1:
            health_score -= 20
        if reclaimable > 5 * 1024 * 1024 * 1024:
            health_score -= 10
        if load_avg and load_avg[0] > max(os.cpu_count() or 1, 1):
            health_score -= 10
        health_score = max(0, min(100, health_score))
        return {
            "host": socket.gethostname(),
            "machine": platform.machine(),
            "os_label": self._os_label(),
            "cpu_count": os.cpu_count() or 1,
            "load_average": load_avg,
            "memory": memory,
            "disk": {
                "used_bytes": primary.get("used", 0),
                "free_bytes": free,
                "total_bytes": total,
            },
            "health_score": health_score,
        }

    def _os_label(self) -> str:
        if self.system == "Darwin":
            version = platform.mac_ver()[0] or platform.release()
            return f"macOS {version}"
        return f"{self.system} {platform.release()}"

    def _load_average(self) -> tuple[float, float, float] | None:
        try:
            return os.getloadavg()
        except (AttributeError, OSError):
            return None

    def _memory_snapshot(self) -> dict[str, int] | None:
        if self.system == "Darwin":
            return self._memory_snapshot_macos()
        if self.system == "Linux":
            return self._memory_snapshot_linux()
        return None

    def _memory_snapshot_macos(self) -> dict[str, int] | None:
        try:
            total_output = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            total = int(total_output)
            vm_output = subprocess.run(
                ["vm_stat"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.splitlines()
        except (OSError, subprocess.CalledProcessError, ValueError):
            return None

        page_size = 4096
        free_pages = 0
        speculative_pages = 0
        for line in vm_output:
            if "page size of" in line:
                try:
                    page_size = int(line.split("page size of")[1].split("bytes")[0].strip())
                except (IndexError, ValueError):
                    page_size = 4096
            if line.startswith("Pages free:"):
                free_pages = self._parse_vm_stat_pages(line)
            if line.startswith("Pages speculative:"):
                speculative_pages = self._parse_vm_stat_pages(line)
        free = (free_pages + speculative_pages) * page_size
        used = max(total - free, 0)
        return {"total_bytes": total, "used_bytes": used, "free_bytes": free}

    def _memory_snapshot_linux(self) -> dict[str, int] | None:
        meminfo = Path("/proc/meminfo")
        if not meminfo.exists():
            return None
        values: dict[str, int] = {}
        try:
            for line in meminfo.read_text(encoding="utf-8").splitlines():
                key, value = line.split(":", 1)
                values[key] = int(value.strip().split()[0]) * 1024
        except (OSError, ValueError):
            return None
        total = values.get("MemTotal")
        available = values.get("MemAvailable")
        if total is None or available is None:
            return None
        used = max(total - available, 0)
        return {"total_bytes": total, "used_bytes": used, "free_bytes": available}

    def _parse_vm_stat_pages(self, line: str) -> int:
        try:
            return int(line.split(":")[1].strip().rstrip("."))
        except (IndexError, ValueError):
            return 0

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
            return {"label": target.label, "status": "skipped", "estimated_bytes": 0, "detail": "Path does not exist on this system."}

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
            return {"label": target.label, "status": "skipped", "estimated_bytes": estimated, "detail": "Windows-only cleanup action."}
        if dry_run:
            return {"label": target.label, "status": "dry-run", "estimated_bytes": estimated, "detail": "Would invoke Clear-RecycleBin after explicit confirmation."}
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", "Clear-RecycleBin -Force"], check=True, capture_output=True, text=True)
            detail = "Recycle Bin cleared with Clear-RecycleBin."
            status = "applied"
        except (OSError, subprocess.CalledProcessError) as exc:
            detail = f"Failed to clear Recycle Bin: {exc}"
            status = "error"
        return {"label": target.label, "status": status, "estimated_bytes": estimated, "detail": detail}

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
                result = subprocess.run(["du", "-sk", str(path)], check=True, capture_output=True, text=True)
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
