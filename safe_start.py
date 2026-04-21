#!/usr/bin/env python3
"""Legacy safe-start entrypoint that defaults to audit mode."""

from __future__ import annotations

from oscleaner import main


if __name__ == "__main__":
    raise SystemExit(main(["audit"]))
