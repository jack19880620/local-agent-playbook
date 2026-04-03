#!/usr/bin/env python3
"""The 3-Bug Challenge (from Test 11)

Give this file to your agent and ask it to find all 3 bugs.
A good agent should find all 3 and suggest fixes.
A great agent will also add defensive coding patterns.

Usage:
    python3 engine/local-agent-engine.py "Read examples/buggy-code.py and find all bugs"
"""


def process_user(user_data):
    """Process user data and return summary"""

    # BUG 1: = instead of == (SyntaxError in Python 3)
    if user_data["status"] = "active":
        active = True
    else:
        active = False

    # BUG 2: Empty list causes ZeroDivisionError
    scores = user_data.get("scores", [])
    average = sum(scores) / len(scores)

    # BUG 3: No error handling for missing key
    # KeyError if "email" doesn't exist
    email = user_data["email"]

    return {
        "active": active,
        "average_score": average,
        "email": email
    }


if __name__ == "__main__":
    # Test case that triggers all 3 bugs
    test_user = {
        "status": "active",
        "scores": [],
        # "email" key intentionally missing
    }
    result = process_user(test_user)
    print(result)
