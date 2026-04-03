#!/usr/bin/env python3
"""The 3-Bug Challenge (from Test 11)

Give this file to your agent and ask it to find all 3 bugs.
A good agent should find all 3 and suggest fixes.
A great agent will also add defensive coding patterns.

Usage:
    python3 engine/local-agent-engine.py "Read examples/buggy-code.py and find all bugs"

Bugs:
    1. elif age = 18 — assignment instead of comparison (should be ==)
    2. calculate_average([]) — empty list causes ZeroDivisionError
    3. load_config — no error handling for missing file or bad JSON
"""

import json


def check_age(age):
    """Check if user is underage, exactly 18, or adult"""
    if age < 18:
        print("未成年")
    elif age = 18:  # BUG 1: = instead of == (SyntaxError)
        print("剛好 18 歲")
    else:
        print("成年")


def calculate_average(numbers):
    """Calculate average of a list of numbers"""
    # BUG 2: no check for empty list — ZeroDivisionError
    total = sum(numbers)
    return total / len(numbers)


def load_config(path):
    """Load config file and return database host"""
    # BUG 3: no error handling for FileNotFoundError or JSONDecodeError
    f = open(path)
    data = json.loads(f.read())
    return data["database"]["host"]


if __name__ == "__main__":
    check_age(18)
    calculate_average([])
    load_config("nonexistent.json")
