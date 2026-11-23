"""Database operations for global and circle-specific statuses."""

from src.config.db import get_connection
from src.domain.status_rules import resolve_effective_status


def upsert_status(
    user_id: int,
    activity: str,
    availability: str,
    expires_at,
    circle_id: int | None = None,
) -> dict:
    """Insert or update one global or circle-specific status."""

    if circle_id is None:
        query = """
            INSERT INTO user_statuses (user_id, circle_id, activity, availability, expires_at, updated_at)
            VALUES (%s, NULL, %s, %s, %s, NOW())
            ON CONFLICT (user_id) WHERE circle_id IS NULL
            DO UPDATE SET
                activity = EXCLUDED.activity,
                availability = EXCLUDED.availability,
                expires_at = EXCLUDED.expires_at,
                updated_at = NOW()
            RETURNING id, user_id, circle_id, activity, availability, expires_at, updated_at
        """
        params = (user_id, activity, availability, expires_at)
    else:
        query = """
            INSERT INTO user_statuses (user_id, circle_id, activity, availability, expires_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (user_id, circle_id) WHERE circle_id IS NOT NULL
            DO UPDATE SET
                activity = EXCLUDED.activity,
                availability = EXCLUDED.availability,
                expires_at = EXCLUDED.expires_at,
                updated_at = NOW()
            RETURNING id, user_id, circle_id, activity, availability, expires_at, updated_at
        """
        params = (user_id, circle_id, activity, availability, expires_at)

    with get_connection() as conn:
        return conn.execute(query, params).fetchone()


def get_circle_feed(circle_id: int) -> list[dict]:
    """Build a circle feed with effective global or circle status precedence."""

    query = """
        SELECT
            u.id AS user_id,
            u.username,
            u.display_name,
            cs.activity AS circle_activity,
            cs.availability AS circle_availability,
            cs.expires_at AS circle_expires_at,
            cs.updated_at AS circle_updated_at,
            gs.activity AS global_activity,
            gs.availability AS global_availability,
            gs.expires_at AS global_expires_at,
            gs.updated_at AS global_updated_at
        FROM circle_members cm
        INNER JOIN users u ON u.id = cm.user_id
        LEFT JOIN user_statuses cs
            ON cs.user_id = u.id AND cs.circle_id = cm.circle_id
        LEFT JOIN user_statuses gs
            ON gs.user_id = u.id AND gs.circle_id IS NULL
        WHERE cm.circle_id = %s
        ORDER BY u.display_name ASC
    """
    with get_connection() as conn:
        rows = conn.execute(query, (circle_id,)).fetchall()

    feed = []
    for row in rows:
        circle_status = (
            {
                "activity": row["circle_activity"],
                "availability": row["circle_availability"],
                "expires_at": row["circle_expires_at"],
                "updated_at": row["circle_updated_at"],
            }
            if row["circle_activity"] is not None
            else None
        )
        global_status = (
            {
                "activity": row["global_activity"],
                "availability": row["global_availability"],
                "expires_at": row["global_expires_at"],
                "updated_at": row["global_updated_at"],
            }
            if row["global_activity"] is not None
            else None
        )

        feed.append(
            {
                "user_id": row["user_id"],
                "username": row["username"],
                "display_name": row["display_name"],
                "status": resolve_effective_status(circle_status, global_status),
            }
        )

    return feed