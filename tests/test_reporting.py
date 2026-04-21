from __future__ import annotations

import unittest

from shared.reporting import render_console_report


class ReportingTests(unittest.TestCase):
    def test_console_render_contains_summary(self) -> None:
        report = {
            "meta": {
                "platform": "Linux",
                "generated_at": "2026-04-21T08:00:00+00:00",
                "mode": "audit",
                "dry_run": True,
                "confirm": False,
                "log_file": "logs/test.log",
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
                    }
                ],
            },
            "actions": [],
            "recommendations": ["Review startup items manually."],
        }
        output = render_console_report(report)
        self.assertIn("Disk summary", output)
        self.assertIn("Linux user cache", output)
        self.assertIn("Recommendations", output)


if __name__ == "__main__":
    unittest.main()
