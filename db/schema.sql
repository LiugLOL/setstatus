-- 1. User accounts (identity only; status lives in user_statuses)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(32) UNIQUE NOT NULL,
    display_name VARCHAR(64) NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Contact circles (e.g., "College", "Friends", "Family")
CREATE TABLE circles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    invite_code VARCHAR(12) UNIQUE NOT NULL,
    owner_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Many-to-many membership between users and circles
CREATE TABLE circle_members (
    circle_id INT NOT NULL REFERENCES circles(id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (circle_id, user_id)
);

-- 4. Scoped user statuses (circle_id IS NULL = Global; otherwise circle-specific)
CREATE TABLE user_statuses (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    circle_id INT REFERENCES circles(id) ON DELETE CASCADE,
    activity VARCHAR(80) NOT NULL,
    availability VARCHAR(16) NOT NULL
        CHECK (availability IN ('open', 'essential_only', 'dnd')),
    expires_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enforce at most ONE global status per user (when circle_id IS NULL)
CREATE UNIQUE INDEX idx_user_global_status
    ON user_statuses(user_id)
    WHERE circle_id IS NULL;

-- Enforce at most ONE status per (user, circle) pair
CREATE UNIQUE INDEX idx_user_circle_status
    ON user_statuses(user_id, circle_id)
    WHERE circle_id IS NOT NULL;

-- Speed up circle feed lookups
CREATE INDEX idx_circle_members_user ON circle_members(user_id);