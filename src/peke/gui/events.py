"""Factories for structured desktop-console events."""
from datetime import datetime, timezone

from peke.pipeline import Event, Level


def ui_event(tag: str, level: Level, message: str) -> Event:
    """Represent a UI action or validation message using the standard event schema."""
    return Event(datetime.now(timezone.utc).isoformat(), "ui", level, message, tag)
