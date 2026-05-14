from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class ParsedCommand:
    task: str
    tags: str
    due_date: date | None


def _parse_due_date(token: str) -> date | None:
    if not token.startswith("@"):
        return None
    value = token[1:]
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("Invalid date format. Use YYYY-MM-DD.")


def parse_task_input(raw: str) -> ParsedCommand:
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
