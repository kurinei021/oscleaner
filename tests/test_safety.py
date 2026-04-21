from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from shared.safety import contains_excluded_fragment, is_protected_path, is_within_allowed_root


class SafetyTests(unittest.TestCase):
    def test_allowed_root_check(self) -> None:
        root = Path("/tmp/example-root")
        child = root / "cache" / "file.tmp"
        outside = Path("/tmp/elsewhere/file.tmp")
        self.assertTrue(is_within_allowed_root(child, root))
        self.assertFalse(is_within_allowed_root(outside, root))

    def test_excluded_fragment_match(self) -> None:
        path = Path("/tmp/demo/node_modules/.cache/index")
        self.assertTrue(contains_excluded_fragment(path, ["node_modules/.cache"]))
        self.assertFalse(contains_excluded_fragment(path, ["Documents"]))

    def test_protected_path_detection(self) -> None:
        home = Path("/Users/example")
        protected = home / "Documents" / "report.txt"
        repo_like = home / "Projects" / "demo"
        self.assertTrue(is_protected_path(protected, ["Documents"], home))
        self.assertTrue(is_protected_path(repo_like, ["Documents"], home))

    def test_git_repository_protection(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            repo = Path(tempdir) / "repo"
            repo.mkdir()
            (repo / ".git").mkdir()
            candidate = repo / "cache"
            candidate.mkdir()
            self.assertTrue(is_protected_path(candidate, [], Path(tempdir)))


if __name__ == "__main__":
    unittest.main()
