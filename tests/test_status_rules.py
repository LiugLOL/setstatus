from datetime import datetime, timedelta, timezone


import pytest

from src.domain.status_rules import (
    is_status_active,
    resolve_effective_status,
    validate_status_input,
)


def test_status_with_no_expiration_is_active():
    assert is_status_active({"text": "Available"}, now=datetime.now(timezone.utc))
    assert is_status_active({"expires_at": None}, now=datetime.now(timezone.utc))


@pytest.mark.parametrize("status", [None, {}])
def test_is_status_active_handles_missing_or_empty_status(status):
    # An empty dict has no expires_at, so the domain rule treats it as non-expiring.
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
    circle = {"text": "circle", "expires_at": now + timedelta(seconds=1)}
    global_status = {"text": "global", "expires_at": now + timedelta(seconds=1)}

    result = resolve_effective_status(circle, global_status, now)

    assert result == {"text": "circle", "expires_at": circle["expires_at"], "scope": "circle"}
    assert circle == {"text": "circle", "expires_at": circle["expires_at"]}
    assert global_status == {"text": "global", "expires_at": global_status["expires_at"]}


@pytest.mark.parametrize(
    "circle_status",
    [
        None,
        {},
        {"text": "expired", "expires_at": datetime(2025, 1, 1, tzinfo=timezone.utc)},
    ],
)
def test_resolve_uses_global_when_circle_is_none_empty_or_expired(circle_status):
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    global_status = {"text": "global", "expires_at": now + timedelta(seconds=1)}

    if circle_status == {}:
        # Empty status is non-expiring under the implementation's current expires_at lookup.
        assert resolve_effective_status(circle_status, global_status, now)["scope"] == "circle"
    elif circle_status is None:
        assert resolve_effective_status(circle_status, global_status, now) == {
            "text": "global",
            "expires_at": global_status["expires_at"],
            "scope": "global",
        }
    else:
        # The expired case is the timezone-matched case; empty status is handled above.
        assert resolve_effective_status(circle_status, global_status, now) == {
            "text": "global",
            "expires_at": global_status["expires_at"],
            "scope": "global",
        }


def test_resolve_circle_expiration_exact_boundary_falls_back_to_global():
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    circle = {"text": "circle", "expires_at": now}
    global_status = {"text": "global", "expires_at": now + timedelta(seconds=1)}

    assert resolve_effective_status(circle, global_status, now)["scope"] == "global"


@pytest.mark.parametrize(
    "circle_status,global_status",
    [
        (None, None),
        ({"text": "expired", "expires_at": datetime(2025, 1, 1, tzinfo=timezone.utc)}, None),
        (None, {"text": "expired", "expires_at": datetime(2025, 1, 1, tzinfo=timezone.utc)}),
        (
            {"text": "expired", "expires_at": datetime(2025, 1, 1, tzinfo=timezone.utc)},
            {"text": "expired", "expires_at": datetime(2025, 1, 1, tzinfo=timezone.utc)},
        ),
    ],
)
def test_resolve_returns_none_when_no_active_status(circle_status, global_status):
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    assert resolve_effective_status(circle_status, global_status, now) is None


@pytest.mark.parametrize("text", ["x", "x" * 140])
def test_validate_accepts_text_length_boundaries(text):
    result = validate_status_input(
        {"text": text, "availability": "open", "expires_in_minutes": None}
    )
    assert result["text"] == text
    assert result["availability"] == "open"
    assert result["expires_at"] is None


@pytest.mark.parametrize("text", ["", " ", "\t\r\n", " " * 140])
def test_validate_rejects_whitespace_only_text(text):
    with pytest.raises(ValueError, match="text must be"):
        validate_status_input({"text": text, "availability": "open"})


def test_validate_rejects_text_over_140_cleaned_characters():
    with pytest.raises(ValueError, match="text must be between"):
        validate_status_input({"text": "x" * 141, "availability": "open"})


def test_validate_trims_text_before_applying_length_boundary():
    result = validate_status_input(
        {"text": "  " + ("x" * 140) + "  ", "availability": "open"}
    )
    assert result["text"] == "x" * 140

    with pytest.raises(ValueError):
        validate_status_input(
            {"text": "  " + ("x" * 139) + "  " + "y", "availability": "open"}
        )


@pytest.mark.parametrize("text", [None, True, False, 1, 1.0, [], {}, object()])
def test_validate_rejects_non_string_text(text):
    with pytest.raises(ValueError, match="text must be a string"):
        validate_status_input({"text": text, "availability": "open"})


@pytest.mark.parametrize(
    "availability",
    [None, "", "available", "OPEN", "busy ", "unknown", 1, True, []],
)
def test_validate_rejects_invalid_availability(availability):
    with pytest.raises((ValueError, TypeError), match="availability|unhashable"):
        validate_status_input({"text": "ok", "availability": availability})


@pytest.mark.parametrize("availability", ["open", "busy", "essential_only", "dnd"])
def test_validate_accepts_every_valid_availability(availability):
    result = validate_status_input({"text": "ok", "availability": availability})
    assert result["availability"] == availability


@pytest.mark.parametrize("expires_in", [True, False])
def test_validate_rejects_boolean_expires_in_minutes(expires_in):
    with pytest.raises(ValueError, match="expires_in_minutes"):
        validate_status_input(
            {"text": "ok", "availability": "open", "expires_in_minutes": expires_in}
        )


@pytest.mark.parametrize("expires_in", [0, -1, -0.001])
def test_validate_rejects_zero_and_negative_expiration(expires_in):
    with pytest.raises(ValueError, match="expires_in_minutes"):
        validate_status_input(
            {"text": "ok", "availability": "open", "expires_in_minutes": expires_in}
        )


@pytest.mark.parametrize("expires_in", [float("nan"), float("inf"), float("-inf")])
def test_validate_rejects_nan_and_infinite_expiration(expires_in):
    with pytest.raises(
        (ValueError, OverflowError),
        match="expires_in_minutes|NaN|integer|infinity",
    ):
        validate_status_input(
            {"text": "ok", "availability": "open", "expires_in_minutes": expires_in}
        )


@pytest.mark.parametrize("expires_in", ["5", [], {}, object()])
def test_validate_rejects_non_numeric_non_none_expiration(expires_in):
    if expires_in is None:
        pytest.skip("None means no expiration and is valid")
    with pytest.raises((ValueError, TypeError), match="expires_in_minutes|not supported"):
        validate_status_input(
            {"text": "ok", "availability": "open", "expires_in_minutes": expires_in}
        )


@pytest.mark.parametrize("expires_in", [1, 0.5, 140])
def test_validate_accepts_positive_numeric_expiration(expires_in):
    before = datetime.now(timezone.utc)
    result = validate_status_input(
        {"text": "ok", "availability": "busy", "expires_in_minutes": expires_in}
    )
    after = datetime.now(timezone.utc)

    assert result["expires_at"] is not None
    assert result["expires_at"] >= before + timedelta(minutes=expires_in)
    assert result["expires_at"] <= after + timedelta(minutes=expires_in)


def test_validate_missing_expires_key_is_valid():
    result = validate_status_input({"text": "ok", "availability": "dnd"})
    assert result["expires_at"] is None


@pytest.mark.parametrize(
    "status",
    [
        {},
        {"availability": "open", "expires_in_minutes": None},
        {"text": "ok", "expires_in_minutes": None},
    ],
)
def test_validate_rejects_missing_required_keys(status):
    with pytest.raises(ValueError):
        validate_status_input(status)


@pytest.mark.parametrize("status", [None, [], "status", 42, True])
def test_validate_rejects_non_dict_input(status):
    with pytest.raises((ValueError, AttributeError)):
        validate_status_input(status)
