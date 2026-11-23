"""FastAPI application for SetStatus users, circles, and statuses."""

import hashlib
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from psycopg.errors import UniqueViolation, ForeignKeyViolation

from src.domain.status_rules import validate_status_input
from src.repositories.circle_repository import (
    create_user,
    get_user_by_id,
    create_circle,
    join_circle_by_invite_code,
    list_user_circles,
    get_circle_invite,
)
from src.repositories.status_repository import upsert_status, get_circle_feed

app = FastAPI(title="SetStatus API", version="0.1.0")




class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_]+$")
    display_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class CircleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    owner_id: int = Field(gt=0)


class CircleJoin(BaseModel):
    invite_code: str = Field(min_length=4, max_length=12)
    user_id: int = Field(gt=0)

class StatusUpsert(BaseModel):
    activity: str
    availability: str
    expires_in_minutes: int | float | None = None
    circle_id: int | None = None


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/users", status_code=201)
def api_create_user(payload: UserCreate):
    password_hash = hashlib.sha256(payload.password.encode()).hexdigest()
    try:
        return create_user(payload.username.strip(), payload.display_name.strip(), password_hash)
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="Username already exists")


@app.get("/users/{user_id}")
def api_get_user(user_id: int):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/circles", status_code=201)
def api_create_circle(payload: CircleCreate):
    try:
        return create_circle(payload.name.strip(), payload.owner_id)
    except ForeignKeyViolation:
        raise HTTPException(status_code=404, detail="Owner user not found")


@app.post("/circles/join")
def api_join_circle(payload: CircleJoin):
    try:
        membership = join_circle_by_invite_code(payload.invite_code.strip(), payload.user_id)
    except ForeignKeyViolation:
        raise HTTPException(status_code=404, detail="User not found")

    if not membership:
        raise HTTPException(status_code=400, detail="Invalid invite code or already a member")
    return membership


@app.get("/users/{user_id}/circles")
def api_list_user_circles(user_id: int):
    return list_user_circles(user_id)


@app.put("/users/{user_id}/status")
def api_upsert_status(user_id: int, payload: StatusUpsert):
    try:
        clean = validate_status_input(payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        return upsert_status(
            user_id=user_id,
            activity=clean["activity"],
            availability=clean["availability"],
            expires_at=clean["expires_at"],
            circle_id=payload.circle_id,
        )
    except ForeignKeyViolation:
        raise HTTPException(status_code=404, detail="User or circle not found")


@app.get("/circles/{circle_id}/feed")
def api_get_circle_feed(circle_id: int):
    return get_circle_feed(circle_id)

@app.get("/circles/{circle_id}/invite")
def api_get_circle_invite(circle_id: int, user_id: int):
    invite = get_circle_invite(circle_id, user_id)
    if not invite:
        raise HTTPException(status_code=404, detail="Circle not found or user is not a member")
    return invite