#!/usr/bin/env python3
"""Code review test — 3 bugs hidden inside. Can your agent find all 3?

Bug 1: Assignment instead of comparison (= vs ==)
Bug 2: Division by zero on empty list
Bug 3: Missing error handling for file operations
"""


def check_status(value):
    """Check if value is valid"""
    # BUG 1: = instead of == (assignment, not comparison)
    if value = "active":
        return True
    return False


def calculate_average(numbers):
    """Calculate the average of a list of numbers"""
    # BUG 2: No check for empty list → ZeroDivisionError
    total = sum(numbers)
    return total / len(numbers)


def read_config(path):
    """Read configuration from file"""
    # BUG 3: No try/except → crashes if file doesn't exist
    with open(path, 'r') as f:
        data = f.read()
    return data


if __name__ == "__main__":
    print(check_status("active"))
    print(calculate_average([]))
    print(read_config("/nonexistent/config.json"))
