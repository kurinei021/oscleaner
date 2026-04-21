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
            "audit": {
                "disk_usage": [
                    {
                        "label": "Home volume",
                        "before": {"free": 10, "total": 100},
                        "after": {"free": 10, "total": 100},
                    }
                ],
                "targets": [
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
            },
            "health_checks": [{"severity": "info", "title": "Healthy", "detail": "Looks fine."}],
            "actions": [],
            "recommendations": ["Review startup items manually."],
        }
        output = render_console_report(report)
        self.assertIn("Disk summary", output)
        self.assertIn("Linux user cache", output)
        self.assertIn("Recommendations", output)
        self.assertIn("Largest locations snapshot", output)


if __name__ == "__main__":
    unittest.main()
