# SetStatus Architecture

SetStatus uses FastAPI for HTTP handling, Pydantic for payload validation,
PostgreSQL for persistence, and a small domain/repository split for status rules
and database operations.

## Layers

### API

`src/main.py` defines the FastAPI application, request models, routes, and HTTP
error mapping. It performs no direct SQL. Route functions delegate to
repositories and domain validation.

### Domain

`src/domain/status_rules.py` validates status input and resolves effective
status precedence. It is timezone-aware and treats an exact expiration boundary
as inactive.

### Repositories

`src/repositories/circle_repository.py` handles users, circles, memberships,
and invite lookup.

`src/repositories/status_repository.py` handles scoped status upserts and circle
feed assembly.

### Database

`src/config/db.py` loads `DATABASE_URL` from environment variables and exposes a
context-managed `psycopg` connection.

## Database Model

```text
users
  id
  username
  display_name
  password_hash
  created_at

circles
  id
  name
  invite_code
  owner_id -> users.id
  created_at

circle_members
  circle_id -> circles.id
  user_id -> users.id
  joined_at

user_statuses
  id
  user_id -> users.id
  circle_id -> circles.id or NULL
  activity
  availability
  expires_at
  updated_at
```

`circle_id IS NULL` identifies a global status. The database uses partial unique
indexes to ensure at most one global status and at most one status per
`(user_id, circle_id)` pair.

## Status Resolution

The effective status for a circle feed is resolved as follows:

1. If the active circle status exists and is not expired, return it with
   `scope="circle"`.
2. Otherwise, if the active global status exists and is not expired, return it
   with `scope="global"`.
3. If neither status is active, return `null`.

A status with `expires_at = NULL` does not expire. An expiration equal to the
current timestamp is inactive.

## Request Flow

```text
HTTP request
  -> Pydantic model validation
  -> FastAPI route
  -> domain validation or status resolution
  -> repository query
  -> PostgreSQL
  -> dict/list response
  -> HTTP response
```

## Upsert Behavior

Global statuses use a partial unique index on `user_id` where `circle_id IS NULL`.
Circle statuses use a partial unique index on `(user_id, circle_id)` where
`circle_id IS NOT NULL`. Repository upserts update the activity, availability,
expiration, and updated timestamp instead of inserting duplicate rows.

## Testing

`tests/test_status_rules.py` covers domain validation and timezone boundaries.
`tests/test_api_integration.py` uses FastAPI `TestClient` and real PostgreSQL
connections. Its autouse fixture truncates all application tables before and
after each test with `RESTART IDENTITY CASCADE`.
