"""Shared terminal color and formatting helpers for CLI scripts."""

from __future__ import annotations


class Color:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


def colored(text: str, color: str) -> str:
    return f"{color}{text}{Color.END}"


def separator(char: str = "=", length: int = 70) -> str:
    return char * length
