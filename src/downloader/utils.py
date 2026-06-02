"""Shared utilities for the downloader."""

import os
from pathlib import Path


def find_cookies_file() -> str | None:
    """Look for a cookies.txt file in the project root directory.
    
    Searches from the project root (where run.py / run_gui.py live).
    Returns the absolute path if found, otherwise None.
    """
    script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidate = os.path.join(script_dir, "cookies.txt")
    if os.path.isfile(candidate):
        return candidate
    return None
