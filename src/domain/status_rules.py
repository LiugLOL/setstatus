import math
from datetime import datetime, timezone, timedelta


def is_status_active(status: dict | None, now: datetime | None = None) -> bool:
    if status is None:
        return False

    expires_at = status.get("expires_at")
    if expires_at is None:
        return True

    if now is None:
        now = datetime.now(timezone.utc)

    return expires_at > now


def resolve_effective_status(
    circle_status: dict | None,
    global_status: dict | None,
    now: datetime | None = None,
) -> dict | None:
    if is_status_active(circle_status, now):
        return {**circle_status, "scope": "circle"}
    if is_status_active(global_status, now):
        return {**global_status, "scope": "global"}
    return None


VALID_AVAILABILITIES = {"open", "busy", "essential_only", "dnd"}


def validate_status_input(status: dict) -> dict:
    if not isinstance(status, dict):
        raise ValueError("status must be a dict")

    text = status.get("text")
    if not isinstance(text, str):
        raise ValueError("text must be a string")

    cleaned_text = text.strip()
    if len(cleaned_text) < 1 or len(cleaned_text) > 140:
        raise ValueError("text must be between 1 and 140 characters")

    availability = status.get("availability")
    if availability not in VALID_AVAILABILITIES:
        raise ValueError(f"availability must be one of {sorted(VALID_AVAILABILITIES)}")

    expires_in = status.get("expires_in_minutes")
    if expires_in is None:
        expires_at = None
    else:
        if (
            isinstance(expires_in, bool)
            or not isinstance(expires_in, (int, float))
            or not math.isfinite(expires_in)
            or expires_in <= 0
        ):
            raise ValueError("expires_in_minutes must be a positive number")
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in)

    return {
        "text": cleaned_text,
        "availability": availability,
        "expires_at": expires_at,
    }