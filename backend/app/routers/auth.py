from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.database import get_connection
from app.security import (
    create_access_token,
    get_current_user,
    get_user_by_username,
    hash_password,
    require_roles,
    verify_password,
)
from app.services.audit import write_audit_log

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=3)


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)
    role: Literal["admin", "researcher"]
    full_name: str | None = None


class UpdateUserStatusRequest(BaseModel):
    is_active: bool


@router.post("/login")
def login(request: LoginRequest):
    user = get_user_by_username(request.username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Учётная запись отключена",
        )

    if not verify_password(request.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )

    access_token = create_access_token(
        {
            "sub": str(user["id"]),
            "username": user["username"],
            "role": user["role"],
        }
    )

    user_data = {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "full_name": user["full_name"],
    }

    write_audit_log(user, "login", "Вход пользователя в систему")

    return {
        "status": "ok",
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_data,
    }


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "status": "ok",
        "user": {
            "id": current_user["id"],
            "username": current_user["username"],
            "role": current_user["role"],
            "full_name": current_user["full_name"],
        },
    }


@router.get("/users")
def get_users(current_user: dict = Depends(require_roles("admin"))):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    username,
                    role,
                    full_name,
                    is_active,
                    created_at
                FROM users
                ORDER BY id
                """
            )
            users = cur.fetchall()

    write_audit_log(current_user, "view_users", "Просмотр списка пользователей")

    return {
        "status": "ok",
        "count": len(users),
        "users": users,
    }


@router.post("/users")
def create_user(
    request: CreateUserRequest,
    current_user: dict = Depends(require_roles("admin")),
):
    existing_user = get_user_by_username(request.username)

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким логином уже существует",
        )

    password_hash = hash_password(request.password)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (
                    username,
                    password_hash,
                    role,
                    full_name,
                    is_active
                )
                VALUES (%s, %s, %s, %s, TRUE)
                RETURNING id, username, role, full_name, is_active, created_at
                """,
                (
                    request.username,
                    password_hash,
                    request.role,
                    request.full_name,
                ),
            )
            user = cur.fetchone()
            conn.commit()

    write_audit_log(
        current_user,
        "create_user",
        {
            "created_username": user["username"],
            "created_role": user["role"],
        },
    )

    return {
        "status": "ok",
        "message": "Пользователь создан",
        "user": user,
    }


@router.patch("/users/{user_id}/status")
def update_user_status(
    user_id: int,
    request: UpdateUserStatusRequest,
    current_user: dict = Depends(require_roles("admin")),
):
    if user_id == current_user["id"] and request.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя отключить собственную учётную запись",
        )

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET is_active = %s
                WHERE id = %s
                RETURNING id, username, role, full_name, is_active, created_at
                """,
                (request.is_active, user_id),
            )
            user = cur.fetchone()
            conn.commit()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )

    write_audit_log(
        current_user,
        "update_user_status",
        {
            "target_user_id": user_id,
            "is_active": request.is_active,
        },
    )

    return {
        "status": "ok",
        "message": "Статус пользователя обновлён",
        "user": user,
    }


@router.get("/audit-logs")
def get_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    current_user: dict = Depends(require_roles("admin")),
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    user_id,
                    username,
                    role,
                    action,
                    details,
                    created_at
                FROM audit_logs
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            logs = cur.fetchall()

    return {
        "status": "ok",
        "count": len(logs),
        "logs": logs,
    }