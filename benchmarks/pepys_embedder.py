#!/usr/bin/env python3
# pepys_embedder.py — thin shim; implementation lives in diary_transformer.diary_embedder
# Copyright (c) 2026 Eric G. Suchanek, PhD, Flux-Frontiers
# License: Elastic 2.0
"""
Convenience wrapper so existing benchmark invocations still work::

    python benchmarks/pepys_embedder.py [OPTIONS]

All logic has been promoted to ``diary_transformer.diary_embedder``.
Use the installed entry point for new work::

    diary-embedder [OPTIONS]
    diary-transformer embed DIARY [OPTIONS]
"""

import multiprocessing
import sys
from pathlib import Path

# Ensure the package is importable when run directly from the repo root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from diary_transformer.diary_embedder import main  # noqa: E402

if __name__ == "__main__":
    multiprocessing.set_start_method("spawn", force=True)
    main()
