from datetime import datetime, timedelta, timezone

import pytest

from src.domain.status_rules import (
    is_status_active,
    resolve_effective_status,
    validate_status_input,
)


def test_status_with_no_expiration_is_active():
    assert is_status_active({"activity": "Available"}, now=datetime.now(timezone.utc))
    assert is_status_active({"expires_at": None}, now=datetime.now(timezone.utc))


@pytest.mark.parametrize("status", [None, {}])
def test_is_status_active_handles_missing_or_empty_status(status):
    if status is None:
        assert is_status_active(status) is False
    else:
        assert is_status_active(status) is True


def test_is_status_active_rejects_expiration_at_exact_now_boundary():
    now = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert is_status_active({"expires_at": now + timedelta(microseconds=1)}, now) is True
    assert is_status_active({"expires_at": now}, now) is False
    assert is_status_active({"expires_at": now - timedelta(microseconds=1)}, now) is False


def test_is_status_active_handles_naive_datetimes():
    now = datetime(2026, 1, 2, 3, 4, 5)
    assert is_status_active({"expires_at": now + timedelta(seconds=1)}, now)
    assert not is_status_active({"expires_at": now}, now)
    assert not is_status_active({"expires_at": now - timedelta(seconds=1)}, now)


def test_is_status_active_handles_mixed_timezone_awareness_as_error():
    aware_now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    naive_expiration = datetime(2026, 1, 2)
    with pytest.raises(TypeError):
        is_status_active({"expires_at": naive_expiration}, aware_now)

    naive_now = datetime(2026, 1, 2)
    aware_expiration = datetime(2026, 1, 2, tzinfo=timezone.utc)
    with pytest.raises(TypeError):
        is_status_active({"expires_at": aware_expiration}, naive_now)


def test_none_status_and_none_now_are_handled():
    assert is_status_active(None, None) is False
    assert is_status_active({"expires_at": None}, None)


def test_resolve_prefers_active_circle_over_global():
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    circle = {"activity": "circle", "expires_at": now + timedelta(seconds=1)}
    global_status = {"activity": "global", "expires_at": now + timedelta(seconds=1)}

    result = resolve_effective_status(circle, global_status, now)

    assert result == {"activity": "circle", "expires_at": circle["expires_at"], "scope": "circle"}


@pytest.mark.parametrize(
    "circle_status",
    [
        None,
        {"activity": "expired", "expires_at": datetime(2025, 1, 1, tzinfo=timezone.utc)},
    ],
)
def test_resolve_uses_global_when_circle_is_none_or_expired(circle_status):
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    global_status = {"activity": "global", "expires_at": now + timedelta(seconds=1)}

    assert resolve_effective_status(circle_status, global_status, now) == {
        "activity": "global",
        "expires_at": global_status["expires_at"],
        "scope": "global",
    }


def test_resolve_circle_expiration_exact_boundary_falls_back_to_global():
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    circle = {"activity": "circle", "expires_at": now}
    global_status = {"activity": "global", "expires_at": now + timedelta(seconds=1)}

    assert resolve_effective_status(circle, global_status, now)["scope"] == "global"


@pytest.mark.parametrize(
    "circle_status,global_status",
    [
        (None, None),
        ({"activity": "expired", "expires_at": datetime(2025, 1, 1, tzinfo=timezone.utc)}, None),
        (None, {"activity": "expired", "expires_at": datetime(2025, 1, 1, tzinfo=timezone.utc)}),
        (
            {"activity": "expired", "expires_at": datetime(2025, 1, 1, tzinfo=timezone.utc)},
            {"activity": "expired", "expires_at": datetime(2025, 1, 1, tzinfo=timezone.utc)},
        ),
    ],
)
def test_resolve_returns_none_when_no_active_status(circle_status, global_status):
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    assert resolve_effective_status(circle_status, global_status, now) is None


@pytest.mark.parametrize("activity", ["x", "x" * 80])
def test_validate_accepts_activity_length_boundaries(activity):
    result = validate_status_input(
        {"activity": activity, "availability": "open", "expires_in_minutes": None}
    )
    assert result["activity"] == activity
    assert result["availability"] == "open"
    assert result["expires_at"] is None


@pytest.mark.parametrize("activity", ["", " ", "\t\r\n", " " * 80])
def test_validate_rejects_whitespace_only_activity(activity):
    with pytest.raises(ValueError, match="activity must be"):
        validate_status_input({"activity": activity, "availability": "open"})


def test_validate_rejects_activity_over_80_cleaned_characters():
    with pytest.raises(ValueError, match="activity must be between"):
        validate_status_input({"activity": "x" * 81, "availability": "open"})


def test_validate_trims_activity_before_applying_length_boundary():
    result = validate_status_input(
        {"activity": "  " + ("x" * 80) + "  ", "availability": "open"}
    )
    assert result["activity"] == "x" * 80

    with pytest.raises(ValueError):
        validate_status_input(
            {"activity": "  " + ("x" * 79) + "  " + "y", "availability": "open"}
        )


@pytest.mark.parametrize("activity", [None, True, False, 1, 1.0, [], {}, object()])
def test_validate_rejects_non_string_activity(activity):
    with pytest.raises(ValueError, match="activity must be a string"):
        validate_status_input({"activity": activity, "availability": "open"})


@pytest.mark.parametrize(
    "availability",
    [None, "", "available", "OPEN", "busy", "dnd ", "unknown", 1, True, []],
)
def test_validate_rejects_invalid_availability(availability):
    with pytest.raises((ValueError, TypeError), match="availability|unhashable"):
        validate_status_input({"activity": "ok", "availability": availability})


@pytest.mark.parametrize("availability", ["open", "essential_only", "dnd"])
def test_validate_accepts_every_valid_availability(availability):
    result = validate_status_input({"activity": "ok", "availability": availability})
    assert result["availability"] == availability


@pytest.mark.parametrize("expires_in", [True, False])
def test_validate_rejects_boolean_expires_in_minutes(expires_in):
    with pytest.raises(ValueError, match="expires_in_minutes"):
        validate_status_input(
            {"activity": "ok", "availability": "open", "expires_in_minutes": expires_in}
        )


@pytest.mark.parametrize("expires_in", [0, -1, -0.001])
def test_validate_rejects_zero_and_negative_expiration(expires_in):
    with pytest.raises(ValueError, match="expires_in_minutes"):
        validate_status_input(
            {"activity": "ok", "availability": "open", "expires_in_minutes": expires_in}
        )


@pytest.mark.parametrize("expires_in", [float("nan"), float("inf"), float("-inf")])
def test_validate_rejects_nan_and_infinite_expiration(expires_in):
    with pytest.raises(
        (ValueError, OverflowError),
        match="expires_in_minutes|NaN|integer|infinity",
    ):
        validate_status_input(
            {"activity": "ok", "availability": "open", "expires_in_minutes": expires_in}
        )


@pytest.mark.parametrize("expires_in", ["5", [], {}, object()])
def test_validate_rejects_non_numeric_non_none_expiration(expires_in):
    with pytest.raises((ValueError, TypeError), match="expires_in_minutes|not supported"):
        validate_status_input(
            {"activity": "ok", "availability": "open", "expires_in_minutes": expires_in}
        )


@pytest.mark.parametrize("expires_in", [1, 0.5, 80])
def test_validate_accepts_positive_numeric_expiration(expires_in):
    before = datetime.now(timezone.utc)
    result = validate_status_input(
        {"activity": "ok", "availability": "essential_only", "expires_in_minutes": expires_in}
    )
    after = datetime.now(timezone.utc)

    assert result["expires_at"] is not None
    assert result["expires_at"] >= before + timedelta(minutes=expires_in)
    assert result["expires_at"] <= after + timedelta(minutes=expires_in)


def test_validate_missing_expires_key_is_valid():
    result = validate_status_input({"activity": "ok", "availability": "dnd"})
    assert result["expires_at"] is None


@pytest.mark.parametrize(
    "status",
    [
        {},
        {"availability": "open", "expires_in_minutes": None},
        {"activity": "ok", "expires_in_minutes": None},
    ],
)
def test_validate_rejects_missing_required_keys(status):
    with pytest.raises(ValueError):
        validate_status_input(status)


@pytest.mark.parametrize("status", [None, [], "status", 42, True])
def test_validate_rejects_non_dict_input(status):
    with pytest.raises((ValueError, AttributeError)):
        validate_status_input(status)