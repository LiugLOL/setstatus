# SetStatus API Reference

## Health

`GET /health`

Returns `{"status":"ok"}`.

## Users

### Create a user

`POST /users`

```json
{
  "username": "alice",
  "display_name": "Alice",
  "password": "secret1"
}
```

- Returns `201` with the public user record.
- Returns `409` for a duplicate username.
- Returns `422` for invalid Pydantic fields.

### Get a user

`GET /users/{user_id}`

- Returns `200` with the public user record.
- Returns `404` if the user does not exist.

## Circles

### Create a circle

`POST /circles`

```json
{
  "name": "Friends",
  "owner_id": 1
}
```

- Returns `201` with the circle, including an eight-character uppercase
  `invite_code`.
- The owner is automatically added as a member.

### Join a circle

`POST /circles/join`

```json
{
  "invite_code": "A1B2C3D4",
  "user_id": 2
}
```

- Returns `200` with the membership.
- Returns `400` for an invalid code or duplicate membership.

### List user circles

`GET /users/{user_id}/circles`

Returns circles where the user is a member.

### Get invite details

`GET /circles/{circle_id}/invite?user_id={user_id}`

- Returns `200` only for a member.
- Returns `404` for a non-member or unknown circle.

## Statuses

### Upsert a status

`PUT /users/{user_id}/status`

```json
{
  "activity": "Working",
  "availability": "open",
  "expires_in_minutes": 60,
  "circle_id": null
}
```

Set `circle_id` to a circle ID for a circle-specific status. Omit expiration or
set `expires_in_minutes` to `null` for a non-expiring status.

- Returns `200` with the upserted status.
- Returns `404` if the user or circle does not exist.
- Returns `422` for invalid status fields.

Valid availability values:

- `open`
- `essential_only`
- `dnd`

### Get a circle feed

`GET /circles/{circle_id}/feed`

Returns one resolved status entry per circle member. A resolved status includes:

- `scope`: `circle` or `global`
- `activity`
- `availability`
- `expires_at`
- `updated_at`
