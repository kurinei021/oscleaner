#!/usr/bin/env python3
"""oscleaner command line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from shared.config import load_config
from shared.engine import HousekeepingEngine, RunOptions
from shared.reporting import render_console_report


def _add_common_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        default="config/example-config.json",
        help="Path to the JSON config file.",
    )
    parser.add_argument("--json-out", help="Optional JSON report output path.")
    parser.add_argument(
        "--log-file",
        help="Optional action log output path. Defaults to logs/run-<timestamp>.log.",
    )
    parser.add_argument(
        "--age-days",
        type=int,
        help="Age threshold in days for Linux /tmp filtering and similar temp pruning.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        help="Maximum number of entries to show in the summary sections.",
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
    parser.add_argument(
        "--view",
        choices=("text", "dashboard"),
        default="text",
        help="Console presentation style. Default: text.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oscleaner",
        description="Cross-platform device housekeeping with audit-first safety defaults.",
    )
    subparsers = parser.add_subparsers(dest="command")

    audit = subparsers.add_parser("audit", help="Read-only disk and cleanup opportunity audit.")
    _add_common_flags(audit)

    clean = subparsers.add_parser("clean", help="Preview or apply cleanup for safe targets only.")
    _add_common_flags(clean)
    clean.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm that you reviewed the cleanup plan.",
    )
    clean.add_argument(
        "--apply",
        action="store_true",
        help="Apply cleanup changes. Without this flag, clean remains a dry-run.",
    )

    analyze = subparsers.add_parser("analyze", help="Inspect the largest user-safe locations.")
    _add_common_flags(analyze)
    analyze.add_argument(
        "--path",
        help="Optional path to inspect more deeply instead of the default home-level scan.",
    )
    analyze.add_argument(
        "--depth",
        type=int,
        default=2,
        help="Directory depth to inspect for analyze output. Default: 2.",
    )

    doctor = subparsers.add_parser("doctor", help="Show device-health warnings and housekeeping advice.")
    _add_common_flags(doctor)

    status = subparsers.add_parser("status", help="Show a concise current housekeeping snapshot.")
    _add_common_flags(status)

    config_cmd = subparsers.add_parser("config", help="Print the effective config file path and notes.")
    config_cmd.add_argument(
        "--config",
        default="config/example-config.json",
        help="Path to the JSON config file.",
    )

    return parser


def _options_from_args(args: argparse.Namespace) -> RunOptions:
    return RunOptions(
        command=args.command,
        confirm=getattr(args, "confirm", False),
        apply=getattr(args, "apply", False),
        json_out=Path(args.json_out) if getattr(args, "json_out", None) else None,
        log_file=Path(args.log_file) if getattr(args, "log_file", None) else None,
        age_days=getattr(args, "age_days", None),
        max_items=getattr(args, "max_items", None),
        include_system_temp=getattr(args, "include_system_temp", False),
        include_package_cache=getattr(args, "include_package_cache", False),
        include_homebrew=getattr(args, "include_homebrew", False),
        analyze_path=Path(args.path).expanduser() if getattr(args, "path", None) else None,
        analyze_depth=getattr(args, "depth", None),
        view=getattr(args, "view", "text"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        args = parser.parse_args(["audit"])

    if args.command == "config":
        print(f"Config file: {Path(args.config)}")
        print("Tip: create a local copy of config/example-config.json and pass it with --config.")
        return 0

    config = load_config(Path(args.config))
    engine = HousekeepingEngine(config=config)
    report = engine.run(_options_from_args(args))

    print(render_console_report(report))
    if getattr(args, "json_out", None):
        print(f"\nJSON report written to {args.json_out}")
    print(f"Action log written to {report['meta']['log_file']}")

    blocked_apply = args.command == "clean" and args.apply and not args.confirm
    if blocked_apply:
        print("\nCleanup was blocked because --apply requires --confirm.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
