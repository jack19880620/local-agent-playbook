#!/usr/bin/env python3
"""Fibonacci with O(2^n) problem — can your agent find and fix it?"""


def fibonacci(n):
    """Calculate the nth Fibonacci number (intentionally inefficient)"""
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


if __name__ == "__main__":
    # This will be extremely slow for large n
    # and will hit Python's recursion limit for n > ~997
    n = 40
    print(f"fibonacci({n}) = {fibonacci(n)}")

    # Try this and watch it hang:
    # fibonacci(100)  # O(2^n) = heat death of the universe
