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


if __name__ == "__main__":
    unittest.main()
