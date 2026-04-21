from __future__ import annotations

from typing import Any

from shared.utils import format_bytes


def render_console_report(report: dict[str, Any]) -> str:
    meta = report["meta"]
    lines = [
        f"oscleaner report for {meta['platform']} at {meta['generated_at']}",
        f"Mode: {meta['mode']} | dry-run: {meta['dry_run']} | confirm: {meta['confirm']}",
    ]

    if meta["mode"] == "cleanup":
        if meta["dry_run"]:
            lines.append("Warning: cleanup mode is running in preview only. No files are being deleted.")
        else:
            lines.append("Warning: cleanup mode is applying deletions only within the configured safe targets.")

    lines.extend(["", "Disk summary:"])

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

    lines.extend(["", "Cleanup opportunities:"])
    for target in report["audit"]["targets"]:
        lines.append(
            f"- {target['label']}: {format_bytes(target['estimated_reclaimable_bytes'])}"
            f" reclaimable at {target['path']}"
        )
        for entry in target.get("largest_entries", []):
            lines.append(f"  {entry['name']}: {format_bytes(entry['size_bytes'])}")

    if report["actions"]:
        lines.extend(["", "Actions:"])
        for action in report["actions"]:
            lines.append(
                f"- {action['status']}: {action['label']} | "
                f"estimated {format_bytes(action['estimated_bytes'])} | {action['detail']}"
            )

    if report["recommendations"]:
        lines.extend(["", "Recommendations:"])
        for recommendation in report["recommendations"]:
            lines.append(f"- {recommendation}")

    return "\n".join(lines)
