from __future__ import annotations

import unittest

from shared.reporting import render_console_report


class ReportingTests(unittest.TestCase):
    def test_console_render_contains_summary(self) -> None:
        report = {
            "meta": {
                "platform": "Linux",
                "generated_at": "2026-04-21T08:00:00+00:00",
                "command": "audit",
                "dry_run": True,
                "confirm": False,
                "apply": False,
                "log_file": "logs/test.log",
            },
            "overview": {
                "total_reclaimable_bytes": 50,
                "largest_cleanup_target": {
                    "label": "Linux user cache",
                    "estimated_reclaimable_bytes": 50,
                },
                "cleanup_target_count": 1,
            },
            "disk_usage": [
                {
                    "label": "Home volume",
                    "before": {"free": 10, "total": 100},
                    "after": {"free": 10, "total": 100},
                }
            ],
            "cleanup_targets": [
                {
                    "label": "Linux user cache",
                    "estimated_reclaimable_bytes": 50,
                    "path": "/home/example/.cache",
                    "largest_entries": [{"name": "pip", "size_bytes": 25}],
                    "note": None,
                }
            ],
            "largest_locations": [
                {
                    "label": "Downloads",
                    "size_bytes": 99,
                    "category": "user-content",
                    "path": "/home/example/Downloads",
                }
            ],
            "health_checks": [{"severity": "info", "title": "Healthy", "detail": "Looks fine."}],
            "actions": [],
            "recommendations": ["Review startup items manually."],
        }
        output = render_console_report(report)
        self.assertIn("Disk summary", output)
        self.assertIn("Linux user cache", output)
        self.assertIn("Recommendations", output)
        self.assertIn("Largest locations snapshot", output)

    def test_status_render_is_shorter_and_status_specific(self) -> None:
        report = {
            "meta": {
                "platform": "Linux",
                "generated_at": "2026-04-21T08:00:00+00:00",
                "command": "status",
                "dry_run": True,
                "confirm": False,
                "apply": False,
                "log_file": "logs/test.log",
            },
            "status": {
                "primary_volume": {
                    "label": "Home volume",
                    "before": {"free": 100, "total": 1000},
                    "after": {"free": 100, "total": 1000},
                },
                "top_targets": [
                    {
                        "label": "Linux user cache",
                        "estimated_reclaimable_bytes": 50,
                    }
                ],
                "safe_reclaimable_bytes": 50,
            },
            "health_checks": [{"severity": "info", "title": "Healthy", "detail": "Looks fine."}],
        }
        output = render_console_report(report)
        self.assertIn("Current status", output)
        self.assertIn("Top safe target", output)

    def test_analyze_render_highlights_focus_and_cleanup_summary(self) -> None:
        report = {
            "meta": {
                "platform": "Linux",
                "generated_at": "2026-04-21T08:00:00+00:00",
                "command": "analyze",
                "view": "text",
                "dry_run": True,
                "confirm": False,
                "apply": False,
                "log_file": "logs/test.log",
            },
            "focus": {
                "scan_scope": "space investigation across visible locations",
                "root": "/home/example",
                "depth": 2,
                "location_count": 4,
            },
            "largest_locations": [
                {
                    "label": "Downloads",
                    "size_bytes": 99,
                    "category": "user-content",
                    "path": "/home/example/Downloads",
                }
            ],
            "category_totals": [{"category": "user-content", "size_bytes": 99}],
            "cleanup_summary": {
                "total_reclaimable_bytes": 50,
                "largest_cleanup_target": {
                    "label": "Linux user cache",
                    "estimated_reclaimable_bytes": 50,
                },
                "cleanup_target_count": 1,
            },
        }
        output = render_console_report(report)
        self.assertIn("Root: /home/example", output)
        self.assertIn("Cleanup summary", output)

    def test_dashboard_analyze_render_contains_bars(self) -> None:
        report = {
            "meta": {
                "platform": "Linux",
                "generated_at": "2026-04-21T08:00:00+00:00",
                "command": "analyze",
                "view": "dashboard",
                "dry_run": True,
                "confirm": False,
                "apply": False,
                "log_file": "logs/test.log",
            },
            "focus": {
                "scan_scope": "space investigation across visible locations",
                "root": "/home/example",
                "depth": 2,
                "location_count": 2,
            },
            "largest_locations": [
                {
                    "label": "Library",
                    "size_bytes": 80,
                    "category": "cache-or-library",
                    "path": "/home/example/Library",
                },
                {
                    "label": "Downloads",
                    "size_bytes": 20,
                    "category": "user-content",
                    "path": "/home/example/Downloads",
                },
            ],
            "category_totals": [
                {"category": "cache-or-library", "size_bytes": 80},
                {"category": "user-content", "size_bytes": 20},
            ],
            "cleanup_summary": {
                "total_reclaimable_bytes": 50,
                "largest_cleanup_target": {
                    "label": "Linux user cache",
                    "estimated_reclaimable_bytes": 50,
                },
                "cleanup_target_count": 1,
            },
        }
        output = render_console_report(report)
        self.assertIn("Analyze Disk", output)
        self.assertIn("[", output)

    def test_dashboard_status_render_contains_health(self) -> None:
        report = {
            "meta": {
                "platform": "Linux",
                "generated_at": "2026-04-21T08:00:00+00:00",
                "command": "status",
                "view": "dashboard",
                "dry_run": True,
                "confirm": False,
                "apply": False,
                "log_file": "logs/test.log",
            },
            "status": {
                "primary_volume": {
                    "label": "Home volume",
                    "before": {"free": 400, "used": 600, "total": 1000},
                    "after": {"free": 400, "used": 600, "total": 1000},
                },
                "top_targets": [{"label": "Linux user cache", "estimated_reclaimable_bytes": 50}],
                "safe_reclaimable_bytes": 50,
            },
            "health_checks": [{"severity": "info", "title": "Healthy", "detail": "Looks fine."}],
            "system_snapshot": {
                "host": "test-host",
                "machine": "x86_64",
                "os_label": "Linux 6.0",
                "cpu_count": 8,
                "load_average": (0.5, 0.7, 0.9),
                "memory": {"total_bytes": 1000, "used_bytes": 600, "free_bytes": 400},
                "disk": {"used_bytes": 600, "free_bytes": 400, "total_bytes": 1000},
                "health_score": 92,
            },
        }
        output = render_console_report(report)
        self.assertIn("Health  92", output)
        self.assertIn("Top Safe Targets", output)


if __name__ == "__main__":
    unittest.main()
