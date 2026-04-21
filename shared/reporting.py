from __future__ import annotations

from typing import Any

from shared.utils import format_bytes


def render_console_report(report: dict[str, Any]) -> str:
    command = report["meta"]["command"]
    renderer = {
        "audit": _render_audit,
        "clean": _render_clean,
        "analyze": _render_analyze,
        "doctor": _render_doctor,
        "status": _render_status,
    }.get(command, _render_audit)
    return renderer(report)


def _render_header(report: dict[str, Any]) -> list[str]:
    meta = report["meta"]
    lines = [
        f"oscleaner {meta['command']} on {meta['platform']} at {meta['generated_at']}",
    ]
    if meta["command"] == "clean":
        lines.append(
            f"Cleanup mode: dry-run={meta['dry_run']} confirm={meta['confirm']} apply={meta['apply']}"
        )
        if meta["dry_run"]:
            lines.append("Warning: preview only. No files are being deleted.")
        else:
            lines.append("Warning: deletions are limited to configured safe targets.")
    return lines


def _render_overview(report: dict[str, Any]) -> list[str]:
    overview = report["overview"]
    largest_target = overview.get("largest_cleanup_target")
    lines = [
        "",
        "Overview:",
        f"- Safe reclaimable estimate: {format_bytes(overview['total_reclaimable_bytes'])}",
        f"- Cleanup target count: {overview['cleanup_target_count']}",
    ]
    if largest_target:
        lines.append(
            f"- Largest safe target: {largest_target['label']} ({format_bytes(largest_target['estimated_reclaimable_bytes'])})"
        )
    return lines


def _render_disk_usage(report: dict[str, Any]) -> list[str]:
    lines = ["", "Disk summary:"]
    for disk in report["audit"]["disk_usage"]:
        before = disk.get("before", {})
        after = disk.get("after", {})
        line = (
            f"- {disk['label']}: free {format_bytes(before.get('free', 0))}"
            f" / total {format_bytes(before.get('total', 0))}"
        )
        if after:
            delta = after.get("free", 0) - before.get("free", 0)
            line += f" | after free {format_bytes(after.get('free', 0))} | delta {format_bytes(delta)}"
        lines.append(line)
    return lines


def _render_cleanup_targets(report: dict[str, Any]) -> list[str]:
    lines = ["", "Safe cleanup targets:"]
    for target in report["audit"]["targets"]:
        lines.append(
            f"- {target['label']}: {format_bytes(target['estimated_reclaimable_bytes'])} at {target['path']}"
        )
        for entry in target.get("largest_entries", []):
            lines.append(f"  {entry['name']}: {format_bytes(entry['size_bytes'])}")
        if target.get("note"):
            lines.append(f"  note: {target['note']}")
    return lines


def _render_largest_locations(report: dict[str, Any]) -> list[str]:
    lines = ["", "Largest locations snapshot:"]
    for entry in report["audit"]["largest_locations"]:
        lines.append(
            f"- {entry['label']}: {format_bytes(entry['size_bytes'])} | {entry['category']} | {entry['path']}"
        )
    return lines


def _render_actions(report: dict[str, Any]) -> list[str]:
    if not report["actions"]:
        return []
    lines = ["", "Actions:"]
    for action in report["actions"]:
        lines.append(
            f"- {action['status']}: {action['label']} | estimated {format_bytes(action['estimated_bytes'])} | {action['detail']}"
        )
    return lines


def _render_health_checks(report: dict[str, Any]) -> list[str]:
    lines = ["", "Health checks:"]
    for check in report["health_checks"]:
        lines.append(f"- {check['severity']}: {check['title']} | {check['detail']}")
    return lines


def _render_recommendations(report: dict[str, Any]) -> list[str]:
    if not report["recommendations"]:
        return []
    lines = ["", "Recommendations:"]
    for recommendation in report["recommendations"]:
        lines.append(f"- {recommendation}")
    return lines


def _render_audit(report: dict[str, Any]) -> str:
    lines = []
    lines.extend(_render_header(report))
    lines.extend(_render_overview(report))
    lines.extend(_render_disk_usage(report))
    lines.extend(_render_cleanup_targets(report))
    lines.extend(_render_largest_locations(report))
    lines.extend(_render_health_checks(report))
    lines.extend(_render_recommendations(report))
    return "\n".join(lines)


def _render_clean(report: dict[str, Any]) -> str:
    lines = []
    lines.extend(_render_header(report))
    lines.extend(_render_overview(report))
    lines.extend(_render_disk_usage(report))
    lines.extend(_render_cleanup_targets(report))
    lines.extend(_render_actions(report))
    lines.extend(_render_recommendations(report))
    return "\n".join(lines)


def _render_analyze(report: dict[str, Any]) -> str:
    lines = []
    lines.extend(_render_header(report))
    lines.extend(_render_overview(report))
    lines.extend(_render_largest_locations(report))
    lines.extend(_render_cleanup_targets(report))
    return "\n".join(lines)


def _render_doctor(report: dict[str, Any]) -> str:
    lines = []
    lines.extend(_render_header(report))
    lines.extend(_render_health_checks(report))
    lines.extend(_render_overview(report))
    lines.extend(_render_recommendations(report))
    return "\n".join(lines)


def _render_status(report: dict[str, Any]) -> str:
    lines = []
    lines.extend(_render_header(report))
    lines.extend(_render_overview(report))
    lines.extend(_render_disk_usage(report))
    lines.extend(_render_health_checks(report))
    return "\n".join(lines)
