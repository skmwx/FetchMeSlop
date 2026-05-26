"""
conftest.py — Pytest configuration for FetchMeSlop tests.

Adds the project root to sys.path so that ``import config``,
``import utils``, etc. resolve correctly when pytest is run from
any working directory.
"""

import pathlib
import sys

# Project root is one level above the tests/ package
PROJECT_ROOT = pathlib.Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
