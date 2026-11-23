"""Database operations for users, circles, membership, and invites."""

import secrets
from src.config.db import get_connection


def create_user(username: str, display_name: str, password_hash: str) -> dict:
    """Create a user and return its public database fields."""

    query = """
        INSERT INTO users (username, display_name, password_hash)
        VALUES (%s, %s, %s)
        RETURNING id, username, display_name, created_at
    """
    with get_connection() as conn:
        return conn.execute(query, (username, display_name, password_hash)).fetchone()


def get_user_by_id(user_id: int) -> dict | None:
    """Return a public user record, or ``None`` when it does not exist."""

    query = """
        SELECT id, username, display_name, created_at
        FROM users
        WHERE id = %s
    """
    with get_connection() as conn:
        return conn.execute(query, (user_id,)).fetchone()


def create_circle(name: str, owner_id: int) -> dict:
    """Create a circle, invite code, and owner membership."""

    invite_code = secrets.token_hex(4).upper()
    insert_circle = """
        INSERT INTO circles (name, invite_code, owner_id)
        VALUES (%s, %s, %s)
        RETURNING id, name, invite_code, owner_id, created_at
    """
    insert_member = """
        INSERT INTO circle_members (circle_id, user_id)
        VALUES (%s, %s)
    """
    with get_connection() as conn:
        circle = conn.execute(insert_circle, (name, invite_code, owner_id)).fetchone()
        conn.execute(insert_member, (circle["id"], owner_id))
        return circle


def join_circle_by_invite_code(invite_code: str, user_id: int) -> dict | None:
    """Join a circle once by invite code, or return ``None`` when invalid."""

    query = """
        INSERT INTO circle_members (circle_id, user_id)
        SELECT id, %s
        FROM circles
        WHERE invite_code = %s
        ON CONFLICT (circle_id, user_id) DO NOTHING
        RETURNING circle_id, user_id, joined_at
    """
    with get_connection() as conn:
        return conn.execute(query, (user_id, invite_code.upper())).fetchone()


def list_user_circles(user_id: int) -> list[dict]:
    """List circles that contain the requested user."""

    query = """
        SELECT c.id, c.name, c.invite_code, c.owner_id, c.created_at
        FROM circles c
        INNER JOIN circle_members cm ON cm.circle_id = c.id
        WHERE cm.user_id = %s
        ORDER BY c.created_at DESC
    """
    with get_connection() as conn:
        return conn.execute(query, (user_id,)).fetchall()

def get_circle_invite(circle_id: int, user_id: int) -> dict | None:
    """Return invite details only when the user belongs to the circle."""

    query = """
        SELECT c.id, c.name, c.invite_code
        FROM circles c
        INNER JOIN circle_members cm ON cm.circle_id = c.id
        WHERE c.id = %s AND cm.user_id = %s
    """
    with get_connection() as conn:
        return conn.execute(query, (circle_id, user_id)).fetchone()