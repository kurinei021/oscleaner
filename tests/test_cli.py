from __future__ import annotations

import unittest

from oscleaner import build_parser


class CliTests(unittest.TestCase):
    def test_clean_command_requires_explicit_subcommand(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["clean", "--confirm", "--apply"])
        self.assertEqual(args.command, "clean")
        self.assertTrue(args.confirm)
        self.assertTrue(args.apply)

    def test_default_parser_accepts_audit(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["audit"])
        self.assertEqual(args.command, "audit")

    def test_analyze_accepts_path_and_depth(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["analyze", "--path", "~/Downloads", "--depth", "3", "--view", "dashboard"])
        self.assertEqual(args.command, "analyze")
        self.assertEqual(args.path, "~/Downloads")
        self.assertEqual(args.depth, 3)
        self.assertEqual(args.view, "dashboard")


if __name__ == "__main__":
    unittest.main()
