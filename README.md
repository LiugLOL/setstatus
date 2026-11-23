# SetStatus API

A FastAPI and PostgreSQL service for sharing availability and activity within
global and circle-specific social contexts.

> **Project status: active development.** User, circle, membership, status,
> and feed flows are implemented. Authentication and real-time updates are
> planned for future releases.

## Overview

SetStatus lets users publish an activity, choose an availability level, and
optionally assign an expiration time. Statuses can apply globally or to a
specific contact circle. Circle feeds prefer an active circle status over an
active global status and fall back to the global status when the circle status
is missing or expired.

## Features

- User creation and lookup
- Pydantic request validation
- Circle creation with generated invite codes
- Circle membership and invite access
- Global and circle-specific status upserts
- Active-status resolution with circle-over-global precedence
- PostgreSQL upsert constraints that prevent duplicate scoped statuses
- Unit and end-to-end API test coverage

## Project Structure

```text
src/
├── main.py                  # FastAPI routes and request models
├── config/
│   └── db.py                # PostgreSQL connection setup
├── domain/
│   └── status_rules.py      # Validation and status precedence
└── repositories/
    ├── circle_repository.py # Users, circles, memberships, invites
    └── status_repository.py # Status upserts and circle feed queries

db/
└── schema.sql               # PostgreSQL schema and constraints

tests/
├── test_status_rules.py     # Domain boundary and precedence tests
└── test_api_integration.py  # FastAPI and PostgreSQL integration tests
```

## Installation

### Clone the repository

```bash
git clone https://github.com/LiugLOL/setstatus.git
cd setstatus
```

### Create and activate a virtual environment

**Windows**

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

**macOS/Linux**

```bash
python -m venv .venv
source .venv/bin/activate
```

### Install dependencies

```bash
python -m pip install -r requirements.txt
```

### Configure PostgreSQL

Set `DATABASE_URL` in a local `.env` file:

```dotenv
DATABASE_URL=postgresql://user:password@localhost:5432/setstatus
```

Create the database tables using the repository schema:

```bash
psql -d setstatus -f db/schema.sql
```

Do not commit `.env`; it is excluded by `.gitignore`.

## Running the API

```bash
python -m uvicorn src.main:app --reload
```

The interactive documentation is available at:

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

## Running Tests

```bash
python -m pytest -q
```

The suite includes timezone and expiration boundary tests, Pydantic validation
tests, real PostgreSQL integration tests, and database cleanup between runs.

## Basic Usage

Create a user:

```bash
curl -X POST http://127.0.0.1:8000/users \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","display_name":"Alice","password":"secret1"}'
```

Create a circle:

```bash
curl -X POST http://127.0.0.1:8000/circles \
  -H "Content-Type: application/json" \
  -d '{"name":"Friends","owner_id":1}'
```

Set a global status:

```bash
curl -X PUT http://127.0.0.1:8000/users/1/status \
  -H "Content-Type: application/json" \
  -d '{"activity":"Working","availability":"open","expires_in_minutes":60,"circle_id":null}'
```

Set a circle status:

```bash
curl -X PUT http://127.0.0.1:8000/users/1/status \
  -H "Content-Type: application/json" \
  -d '{"activity":"Lunch with friends","availability":"dnd","expires_in_minutes":30,"circle_id":1}'
```

Read the effective feed:

```bash
curl http://127.0.0.1:8000/circles/1/feed
```

An active circle status produces a response with `"scope": "circle"`; otherwise
the feed resolves to an active global status with `"scope": "global"`.

## Architecture

- **API**: FastAPI routes, Pydantic payload models, HTTP status mapping
- **Domain**: Status validation, timezone-aware expiration checks, precedence
- **Repositories**: Parameterized PostgreSQL reads and upserts
- **Database**: Partial unique indexes for one global status and one status per
  user/circle pair

The runtime flow is:

1. FastAPI validates and normalizes the incoming request.
2. The route calls a repository function for the database operation.
3. PostgreSQL applies constraints and scoped upsert rules.
4. Feed queries join circle members with global and circle statuses.
5. The domain resolver chooses the active circle status or global fallback.

See [ARCHITECTURE.md](ARCHITECTURE.md) for database and request-flow details.

## API Summary

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/health` | Service health |
| `POST` | `/users` | Create a user |
| `GET` | `/users/{user_id}` | Get a public user |
| `POST` | `/circles` | Create a circle |
| `GET` | `/users/{user_id}/circles` | List circle memberships |
| `POST` | `/circles/join` | Join using an invite code |
| `GET` | `/circles/{circle_id}/invite` | Get invite details as a member |
| `PUT` | `/users/{user_id}/status` | Upsert a global or circle status |
| `GET` | `/circles/{circle_id}/feed` | Resolve effective circle statuses |

## Status Rules

Valid activities contain 1 to 80 characters after trimming. Valid availability
values are `open`, `essential_only`, and `dnd`. Expiration minutes must be a
finite positive number or `null` for no expiration.

## Roadmap

- [x] User creation and lookup
- [x] Circle creation and invite membership
- [x] Global and circle status upserts
- [x] Circle-over-global precedence
- [x] Expired-status fallback
- [x] Domain and API integration tests
- [ ] Authentication and access tokens
- [ ] Status subscriptions and real-time updates
- [ ] Pagination and cursor-based feed queries
- [ ] Deployment and migration tooling

## License

This project is licensed under the [MIT License](LICENSE).
