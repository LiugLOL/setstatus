import pytest
from fastapi.testclient import TestClient

from src.config.db import get_connection
from src.main import app


@pytest.fixture(autouse=True)
def clean_database():
    with get_connection() as conn:
        conn.execute(
            """
            TRUNCATE TABLE users, circles, circle_members, user_statuses
            RESTART IDENTITY CASCADE
            """
        )

    yield

    with get_connection() as conn:
        conn.execute(
            """
            TRUNCATE TABLE users, circles, circle_members, user_statuses
            RESTART IDENTITY CASCADE
            """
        )


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def create_user(client, username="alice", display_name="Alice", password="secret1"):
    response = client.post(
        "/users",
        json={
            "username": username,
            "display_name": display_name,
            "password": password,
        },
    )
    assert response.status_code == 201
    return response.json()


def create_circle(client, owner_id, name="Test Circle"):
    response = client.post(
        "/circles",
        json={"name": name, "owner_id": owner_id},
    )
    assert response.status_code == 201
    return response.json()


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_user_and_duplicate_username(client):
    user = create_user(client)
    assert user["username"] == "alice"
    assert user["display_name"] == "Alice"
    assert isinstance(user["id"], int)

    duplicate = client.post(
        "/users",
        json={
            "username": "alice",
            "display_name": "Another Alice",
            "password": "secret2",
        },
    )
    assert duplicate.status_code == 409
    assert "already exists" in duplicate.json()["detail"].lower()


@pytest.mark.parametrize(
    "payload",
    [
        {
            "username": "valid_name",
            "display_name": "Valid",
            "password": "short",
        },
        {
            "username": "bad-name!",
            "display_name": "Valid",
            "password": "long_enough",
        },
        {
            "username": "x" * 33,
            "display_name": "Valid",
            "password": "long_enough",
        },
    ],
)
def test_create_user_rejects_invalid_pydantic_fields(client, payload):
    response = client.post("/users", json=payload)
    assert response.status_code == 422


def test_get_user_by_id_and_missing_user(client):
    user = create_user(client)

    response = client.get(f"/users/{user['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == user["id"]
    assert response.json()["username"] == "alice"

    missing = client.get("/users/2147483647")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "User not found"


def test_create_circle_generates_invite_and_controls_invite_access(client):
    owner = create_user(client)
    member = create_user(client, username="bob", display_name="Bob")
    outsider = create_user(client, username="carol", display_name="Carol")

    circle = create_circle(client, owner["id"], "Friends")

    assert isinstance(circle["invite_code"], str)
    assert len(circle["invite_code"]) == 8
    assert circle["invite_code"] == circle["invite_code"].upper()
    assert circle["owner_id"] == owner["id"]

    owner_invite = client.get(
        f"/circles/{circle['id']}/invite",
        params={"user_id": owner["id"]},
    )
    assert owner_invite.status_code == 200
    assert owner_invite.json()["invite_code"] == circle["invite_code"]

    member_invite = client.get(
        f"/circles/{circle['id']}/invite",
        params={"user_id": member["id"]},
    )
    assert member_invite.status_code == 404

    outsider_invite = client.get(
        f"/circles/{circle['id']}/invite",
        params={"user_id": outsider["id"]},
    )
    assert outsider_invite.status_code == 404


def test_join_circle_duplicate_and_invalid_invite(client):
    owner = create_user(client)
    joiner = create_user(client, username="bob", display_name="Bob")
    circle = create_circle(client, owner["id"])

    joined = client.post(
        "/circles/join",
        json={"invite_code": circle["invite_code"], "user_id": joiner["id"]},
    )
    assert joined.status_code == 200
    assert joined.json()["circle_id"] == circle["id"]
    assert joined.json()["user_id"] == joiner["id"]

    duplicate = client.post(
        "/circles/join",
        json={"invite_code": circle["invite_code"], "user_id": joiner["id"]},
    )
    assert duplicate.status_code == 400

    invalid = client.post(
        "/circles/join",
        json={"invite_code": "ZZZZZZZZ", "user_id": joiner["id"]},
    )
    assert invalid.status_code == 400


def test_circle_feed_global_circle_precedence_and_upsert(client):
    user = create_user(client)
    circle = create_circle(client, user["id"])

    global_status = client.put(
        f"/users/{user['id']}/status",
        json={
            "activity": "Working globally",
            "availability": "open",
            "expires_in_minutes": None,
            "circle_id": None,
        },
    )
    assert global_status.status_code == 200

    feed = client.get(f"/circles/{circle['id']}/feed")
    assert feed.status_code == 200
    member_feed = next(row for row in feed.json() if row["user_id"] == user["id"])
    assert member_feed["status"]["scope"] == "global"
    assert member_feed["status"]["activity"] == "Working globally"

    circle_status = client.put(
        f"/users/{user['id']}/status",
        json={
            "activity": "In the circle",
            "availability": "dnd",
            "expires_in_minutes": None,
            "circle_id": circle["id"],
        },
    )
    assert circle_status.status_code == 200

    feed = client.get(f"/circles/{circle['id']}/feed")
    member_feed = next(row for row in feed.json() if row["user_id"] == user["id"])
    assert member_feed["status"]["scope"] == "circle"
    assert member_feed["status"]["activity"] == "In the circle"

    updated_global = client.put(
        f"/users/{user['id']}/status",
        json={
            "activity": "Updated global",
            "availability": "open",
            "expires_in_minutes": None,
            "circle_id": None,
        },
    )
    assert updated_global.status_code == 200

    with get_connection() as conn:
        count = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM user_statuses
            WHERE user_id = %s AND circle_id IS NULL
            """,
            (user["id"],),
        ).fetchone()["count"]
        global_row = conn.execute(
            """
            SELECT activity
            FROM user_statuses
            WHERE user_id = %s AND circle_id IS NULL
            """,
            (user["id"],),
        ).fetchone()

    assert count == 1
    assert global_row["activity"] == "Updated global"

    updated_circle = client.put(
        f"/users/{user['id']}/status",
        json={
            "activity": "Updated circle",
            "availability": "essential_only",
            "expires_in_minutes": None,
            "circle_id": circle["id"],
        },
    )
    assert updated_circle.status_code == 200

    with get_connection() as conn:
        circle_count = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM user_statuses
            WHERE user_id = %s AND circle_id = %s
            """,
            (user["id"], circle["id"]),
        ).fetchone()["count"]
    assert circle_count == 1


def test_expired_circle_status_falls_back_to_active_global_status(client):
    user = create_user(client)
    circle = create_circle(client, user["id"])

    global_response = client.put(
        f"/users/{user['id']}/status",
        json={
            "activity": "Available globally",
            "availability": "open",
            "expires_in_minutes": None,
            "circle_id": None,
        },
    )
    assert global_response.status_code == 200

    circle_response = client.put(
        f"/users/{user['id']}/status",
        json={
            "activity": "Expired circle status",
            "availability": "dnd",
            "expires_in_minutes": 60,
            "circle_id": circle["id"],
        },
    )
    assert circle_response.status_code == 200

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE user_statuses
            SET expires_at = NOW() - INTERVAL '1 minute'
            WHERE user_id = %s AND circle_id = %s
            """,
            (user["id"], circle["id"]),
        )

    feed = client.get(f"/circles/{circle['id']}/feed")
    assert feed.status_code == 200
    member_feed = next(row for row in feed.json() if row["user_id"] == user["id"])
    assert member_feed["status"]["scope"] == "global"
    assert member_feed["status"]["activity"] == "Available globally"


@pytest.mark.parametrize(
    "payload",
    [
        {
            "activity": "",
            "availability": "open",
            "expires_in_minutes": None,
        },
        {
            "activity": " " * 80,
            "availability": "open",
            "expires_in_minutes": None,
        },
        {
            "activity": "x" * 81,
            "availability": "open",
            "expires_in_minutes": None,
        },
        {
            "activity": "Working",
            "availability": "away",
            "expires_in_minutes": None,
        },
        {
            "activity": "Working",
            "availability": "open",
            "expires_in_minutes": -1,
        },
    ],
)
def test_status_payload_validation_returns_422(client, payload):
    user = create_user(client)

    response = client.put(f"/users/{user['id']}/status", json=payload)

    assert response.status_code == 422
