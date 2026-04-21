#!/usr/bin/env python3
"""Top-level safe entrypoint for oscleaner."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from shared.config import load_config
from shared.engine import HousekeepingEngine
from shared.reporting import render_console_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit disk usage and preview or apply safe cleanup operations."
    )
    parser.add_argument(
        "--mode",
        choices=("audit", "cleanup"),
        default="audit",
        help="Run in read-only audit mode or cleanup mode.",
    )
    parser.add_argument(
        "--config",
        default="config/example-config.json",
        help="Path to the JSON config file.",
    )
    parser.add_argument(
        "--json-out",
        help="Optional JSON report output path.",
    )
    parser.add_argument(
        "--log-file",
        help="Optional action log output path. Defaults to logs/run-<timestamp>.log.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Explicitly confirm that cleanup was reviewed and approved.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply cleanup changes. Without this flag, cleanup mode stays in dry-run.",
    )
    parser.add_argument(
        "--age-days",
        type=int,
        help="Age threshold in days for Linux /tmp filtering and similar temp pruning.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        help="Maximum number of largest entries to show per target.",
    )
    parser.add_argument(
        "--include-system-temp",
        action="store_true",
        help="Include carefully scoped system temp targets when available and safe.",
    )
    parser.add_argument(
        "--include-package-cache",
        action="store_true",
        help="Include package-manager cache guidance in the report.",
    )
    parser.add_argument(
        "--include-homebrew",
        action="store_true",
        help="Include Homebrew cleanup guidance on macOS when brew is available.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = load_config(Path(args.config))
    engine = HousekeepingEngine(config=config)

    report = engine.run(
        mode=args.mode,
        confirm=args.confirm,
        apply=args.apply,
        json_out=Path(args.json_out) if args.json_out else None,
        log_file=Path(args.log_file) if args.log_file else None,
        age_days=args.age_days,
        max_items=args.max_items,
        include_system_temp=args.include_system_temp,
        include_package_cache=args.include_package_cache,
        include_homebrew=args.include_homebrew,
    )

    print(render_console_report(report))
    if args.json_out:
        print(f"\nJSON report written to {args.json_out}")
    print(f"Action log written to {report['meta']['log_file']}")

    blocked_apply = args.mode == "cleanup" and args.apply and not args.confirm
    if blocked_apply:
        print(
            "\nCleanup was blocked because --apply requires --confirm.",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
