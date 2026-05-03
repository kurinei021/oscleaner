from __future__ import annotations

import math
import shutil
from typing import Any

from shared.utils import format_bytes


def render_console_report(report: dict[str, Any]) -> str:
    command = report["meta"]["command"]
    view = report["meta"].get("view", "text")
    if view == "dashboard":
        dashboard_renderer = {
            "analyze": _render_analyze_dashboard,
            "status": _render_status_dashboard,
        }.get(command)
        if dashboard_renderer:
            return dashboard_renderer(report)
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
    lines = [f"oscleaner {meta['command']} on {meta['platform']} at {meta['generated_at']}"]
    if meta["command"] == "clean":
        lines.append(f"Cleanup mode: dry-run={meta['dry_run']} confirm={meta['confirm']} apply={meta['apply']}")
        lines.append(
            "Warning: preview only. No files are being deleted."
            if meta["dry_run"]
            else "Warning: deletions are limited to configured safe targets."
        )
    return lines


def _render_overview(overview: dict[str, Any]) -> list[str]:
    largest = overview.get("largest_cleanup_target")
    lines = [
        "",
        "Overview:",
        f"- Safe reclaimable estimate: {format_bytes(overview['total_reclaimable_bytes'])}",
        f"- Cleanup target count: {overview['cleanup_target_count']}",
    ]
    if largest:
        lines.append(
            f"- Largest safe target: {largest['label']} ({format_bytes(largest['estimated_reclaimable_bytes'])})"
        )
    return lines


def _render_disk_usage(disk_usage: list[dict[str, Any]]) -> list[str]:
    lines = ["", "Disk summary:"]
    for disk in disk_usage:
        before = disk.get("before", {})
        after = disk.get("after", {})
        line = f"- {disk['label']}: free {format_bytes(before.get('free', 0))} / total {format_bytes(before.get('total', 0))}"
        if after:
            delta = after.get("free", 0) - before.get("free", 0)
            line += f" | after free {format_bytes(after.get('free', 0))} | delta {format_bytes(delta)}"
        lines.append(line)
    return lines


def _render_cleanup_targets(cleanup_targets: list[dict[str, Any]], title: str = "Safe cleanup targets:") -> list[str]:
    lines = ["", title]
    for target in cleanup_targets:
        lines.append(f"- {target['label']}: {format_bytes(target['estimated_reclaimable_bytes'])} at {target['path']}")
        for entry in target.get("largest_entries", []):
            lines.append(f"  {entry['name']}: {format_bytes(entry['size_bytes'])}")
        if target.get("note"):
            lines.append(f"  note: {target['note']}")
    return lines


def _render_largest_locations(locations: list[dict[str, Any]], title: str = "Largest locations snapshot:") -> list[str]:
    lines = ["", title]
    for item in locations:
        lines.append(
            f"- {item['label']}: {format_bytes(item['size_bytes'])} | {item['category']} | {item['path']}"
        )
    return lines


def _render_category_totals(category_totals: list[dict[str, Any]]) -> list[str]:
    lines = ["", "Category totals:"]
    for item in category_totals:
        lines.append(f"- {item['category']}: {format_bytes(item['size_bytes'])}")
    return lines


def _render_health_checks(health_checks: list[dict[str, Any]]) -> list[str]:
    lines = ["", "Health checks:"]
    for check in health_checks:
        lines.append(f"- {check['severity']}: {check['title']} | {check['detail']}")
    return lines


def _render_risk_findings(risk_findings: list[dict[str, Any]]) -> list[str]:
    lines = ["", "Risk findings:"]
    for finding in risk_findings:
        lines.append(f"- {finding['severity']}: {finding['title']} | {finding['detail']}")
    return lines


def _render_actions(actions: list[dict[str, Any]]) -> list[str]:
    lines = ["", "Actions:"]
    for action in actions:
        lines.append(
            f"- {action['status']}: {action['label']} | estimated {format_bytes(action['estimated_bytes'])} | {action['detail']}"
        )
    return lines


def _render_recommendations(recommendations: list[str]) -> list[str]:
    lines = ["", "Recommendations:"]
    for recommendation in recommendations:
        lines.append(f"- {recommendation}")
    return lines


def _render_audit(report: dict[str, Any]) -> str:
    lines = []
    lines.extend(_render_header(report))
    lines.extend(_render_overview(report["overview"]))
    lines.extend(_render_disk_usage(report["disk_usage"]))
    lines.extend(_render_cleanup_targets(report["cleanup_targets"]))
    lines.extend(_render_largest_locations(report["largest_locations"]))
    lines.extend(_render_health_checks(report["health_checks"]))
    lines.extend(_render_recommendations(report["recommendations"]))
    return "\n".join(lines)


def _render_clean(report: dict[str, Any]) -> str:
    lines = []
    lines.extend(_render_header(report))
    lines.extend(_render_overview(report["overview"]))
    lines.extend(_render_disk_usage(report["disk_usage"]))
    lines.extend(_render_cleanup_targets(report["cleanup_targets"]))
    lines.extend(_render_actions(report["actions"]))
    lines.extend(_render_recommendations(report["recommendations"]))
    return "\n".join(lines)


def _render_analyze(report: dict[str, Any]) -> str:
    lines = []
    lines.extend(_render_header(report))
    lines.extend(
        [
            "",
            "Analysis focus:",
            f"- Scope: {report['focus']['scan_scope']}",
            f"- Root: {report['focus']['root']}",
            f"- Depth: {report['focus']['depth']}",
            f"- Locations inspected: {report['focus']['location_count']}",
        ]
    )
    lines.extend(_render_largest_locations(report["largest_locations"], title="Largest visible locations:"))
    lines.extend(_render_category_totals(report["category_totals"]))
    lines.extend(
        [
            "",
            "Cleanup summary:",
            f"- Safe reclaimable estimate: {format_bytes(report['cleanup_summary']['total_reclaimable_bytes'])}",
            f"- Largest safe target: {report['cleanup_summary']['largest_cleanup_target']['label']} ({format_bytes(report['cleanup_summary']['largest_cleanup_target']['estimated_reclaimable_bytes'])})"
            if report["cleanup_summary"]["largest_cleanup_target"]
            else "- Largest safe target: none",
        ]
    )
    return "\n".join(lines)


def _render_doctor(report: dict[str, Any]) -> str:
    lines = []
    lines.extend(_render_header(report))
    lines.extend(_render_health_checks(report["health_checks"]))
    lines.extend(_render_risk_findings(report["risk_findings"]))
    lines.extend(_render_overview(report["overview"]))
    lines.extend(_render_recommendations(report["recommendations"]))
    return "\n".join(lines)


def _render_status(report: dict[str, Any]) -> str:
    lines = []
    lines.extend(_render_header(report))
    status = report["status"]
    primary = status.get("primary_volume")
    lines.extend(["", "Current status:"])
    if primary:
        before = primary["before"]
        lines.append(
            f"- Free space: {format_bytes(before.get('free', 0))} of {format_bytes(before.get('total', 0))} on {primary['label']}"
        )
    lines.append(f"- Safe reclaimable estimate: {format_bytes(status['safe_reclaimable_bytes'])}")
    if status["top_targets"]:
        top = status["top_targets"][0]
        lines.append(f"- Top safe target: {top['label']} ({format_bytes(top['estimated_reclaimable_bytes'])})")
    lines.extend(_render_health_checks(report["health_checks"]))
    return "\n".join(lines)


def _render_analyze_dashboard(report: dict[str, Any]) -> str:
    locations = report["largest_locations"]
    if not locations:
        return _render_analyze(report)

    terminal_width = shutil.get_terminal_size((100, 24)).columns
    lines = [
        f"oscleaner analyze  {report['focus']['root']}  depth={report['focus']['depth']}",
        "",
        _dashboard_title(
            "Analyze Disk",
            f"{report['focus']['root']}",
            report["cleanup_summary"]["total_reclaimable_bytes"],
        ),
        "",
    ]
    total_size = sum(item["size_bytes"] for item in locations) or 1
    bar_width = max(18, min(28, terminal_width // 4))
    for index, item in enumerate(locations[:8], start=1):
        percent = (item["size_bytes"] / total_size) * 100
        bar = _bar(percent / 100, bar_width)
        label = item["label"]
        if len(label) > 28:
            label = label[:25] + "..."
        lines.append(
            f"{index:>2}. {bar} {percent:>5.1f}%  {label:<28} {format_bytes(item['size_bytes']):>9}  {item['category']}"
        )
    lines.extend(
        [
            "",
            f"Categories: {_inline_category_totals(report['category_totals'])}",
            f"Safe cleanup estimate: {format_bytes(report['cleanup_summary']['total_reclaimable_bytes'])}",
        ]
    )
    largest = report["cleanup_summary"].get("largest_cleanup_target")
    if largest:
        lines.append(
            f"Largest safe target: {largest['label']} ({format_bytes(largest['estimated_reclaimable_bytes'])})"
        )
    return "\n".join(lines)


def _render_status_dashboard(report: dict[str, Any]) -> str:
    status = report["status"]
    snapshot = report.get("system_snapshot") or {}
    primary = status.get("primary_volume")
    memory = snapshot.get("memory")
    disk = snapshot.get("disk") or {}
    load_avg = snapshot.get("load_average")
    lines = [
        "oscleaner status",
        "",
        f"Health {snapshot.get('health_score', 0):>3}  {snapshot.get('host', 'local')}  {snapshot.get('machine', '')}  {snapshot.get('os_label', '')}".strip(),
        "",
    ]
    if primary:
        before = primary["before"]
        disk_ratio = (before.get("used", 0) / before.get("total", 1)) if before.get("total", 0) else 0
        lines.append(
            f"Disk    {_bar(disk_ratio, 24)}  used {format_bytes(before.get('used', 0))} / {format_bytes(before.get('total', 0))}"
        )
        lines.append(f"        free {format_bytes(before.get('free', 0))}  reclaimable {format_bytes(status['safe_reclaimable_bytes'])}")
    if memory:
        mem_ratio = (memory["used_bytes"] / memory["total_bytes"]) if memory["total_bytes"] else 0
        lines.append(
            f"Memory  {_bar(mem_ratio, 24)}  used {format_bytes(memory['used_bytes'])} / {format_bytes(memory['total_bytes'])}"
        )
    if load_avg:
        lines.append(f"Load    {load_avg[0]:.2f} / {load_avg[1]:.2f} / {load_avg[2]:.2f}  ({snapshot.get('cpu_count', 1)} cores)")
    top_targets = status.get("top_targets") or []
    if top_targets:
        lines.append("")
        lines.append("Top Safe Targets")
        for item in top_targets[:4]:
            lines.append(f"- {item['label']:<24} {format_bytes(item['estimated_reclaimable_bytes']):>9}")
    if report.get("health_checks"):
        lines.append("")
        lines.append("Health Checks")
        for check in report["health_checks"][:3]:
            lines.append(f"- {check['title']}: {check['detail']}")
    return "\n".join(lines)


def _dashboard_title(label: str, path: str, total_bytes: int) -> str:
    return f"{label}  {path}  |  Safe reclaim: {format_bytes(total_bytes)}"


def _inline_category_totals(category_totals: list[dict[str, Any]]) -> str:
    return " | ".join(f"{item['category']} {format_bytes(item['size_bytes'])}" for item in category_totals[:4])


def _bar(ratio: float, width: int) -> str:
    ratio = max(0.0, min(1.0, ratio))
    filled = int(math.floor(ratio * width))
    empty = max(width - filled, 0)
    return "[" + ("#" * filled) + ("." * empty) + "]"
