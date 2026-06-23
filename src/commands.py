"""Command parsing for user input.

Parses raw task input into structured todo data:
  - Task description (main text)
  - Tags (prefixed with #)
  - Due date (prefixed with @, ISO format)

Example input: 'Buy milk #shopping #errands @2026-12-25'
  task: 'Buy milk'
  tags: 'shopping,errands'
  due_date: date(2026, 12, 25)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class ParsedCommand:
    """Structured representation of parsed task input.

    Result of parsing raw user input via parse_task_input().

    Attributes:
        task: Task description (non-empty string).
        tags: Comma-separated tag list (e.g., 'work,urgent', or '' if no tags).
        due_date: Target completion date or None if not specified.
    """

    task: str
    tags: str
    due_date: date | None


def _parse_due_date(token: str) -> date | None:
    """Parse due date from token with @ prefix.

    Token format: '@YYYY-MM-DD'
    Only processes tokens starting with '@'.

    Args:
        token: Token from input (e.g., '@2026-12-25').

    Returns:
        Parsed date object if token starts with @, None otherwise.

    Raises:
        ValueError: If date format is invalid (not YYYY-MM-DD).
    """
    if not token.startswith("@"):
        return None
    value = token[1:]
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("Invalid date format. Use YYYY-MM-DD.")


def parse_task_input(raw: str) -> ParsedCommand:
    """Parse raw task input into structured command.

    Tokenizes input and extracts task description, tags, and due date.
    Fails fast with ValueError if input is invalid.

    Syntax:
      - Text tokens → task description
      - #TAG tokens → tags (can appear multiple times)
      - @YYYY-MM-DD → due date (only one allowed)

    Example: 'Fix bug in login #work #urgent @2026-12-31'
      task='Fix bug in login'
      tags='work,urgent'
      due_date=date(2026, 12, 31)

    Args:
        raw: Raw input string (space-separated tokens).

    Returns:
        ParsedCommand with task, tags (comma-separated), and due_date.

    Raises:
        ValueError: If task is empty, multiple due dates, or invalid date format.
    """
    parts = raw.strip().split()
    if not parts:
        raise ValueError("Task cannot be empty.")

    tags: list[str] = []
    due_date: date | None = None
    task_words: list[str] = []

    for token in parts:
        if token.startswith("#") and len(token) > 1:
            tags.append(token[1:])
            continue
        if token.startswith("@"):
            if due_date is not None:
                raise ValueError("Only one due date is allowed.")
            due_date = _parse_due_date(token)
            continue
        task_words.append(token)

    task = " ".join(task_words).strip()
    if not task:
        raise ValueError("Task cannot be empty.")

    return ParsedCommand(task=task, tags=",".join(tags), due_date=due_date)
