import json
from typing import Any

from app.database import get_connection


def write_audit_log(user: dict | None, action: str, details: Any = None) -> None:
    """
    Записывает действие пользователя в журнал.
    Ошибка журналирования не должна ломать основную бизнес-операцию.
    """

    try:
        details_text = None

        if details is not None:
            if isinstance(details, str):
                details_text = details
            else:
                details_text = json.dumps(details, ensure_ascii=False)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_logs (
                        user_id,
                        username,
                        role,
                        action,
                        details
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        user["id"] if user else None,
                        user["username"] if user else None,
                        user["role"] if user else None,
                        action,
                        details_text,
                    ),
                )
                conn.commit()

    except Exception as error:
        print(f"[AUDIT LOG ERROR] {error}")