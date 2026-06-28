from app.database import get_connection
from app.security import hash_password


def main():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'researcher')),
                    full_name VARCHAR(255),
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_users_username
                ON users (username);
                """
            )

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_users_role
                ON users (role);
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    username VARCHAR(100),
                    role VARCHAR(20),
                    action VARCHAR(100) NOT NULL,
                    details TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at
                ON audit_logs (created_at);
                """
            )

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_audit_logs_action
                ON audit_logs (action);
                """
            )

            users = [
                {
                    "username": "admin",
                    "password": "admin123",
                    "role": "admin",
                    "full_name": "Администратор системы",
                },
                {
                    "username": "researcher",
                    "password": "researcher123",
                    "role": "researcher",
                    "full_name": "Исследователь",
                },
            ]

            for user in users:
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
                    ON CONFLICT (username)
                    DO UPDATE SET
                        password_hash = EXCLUDED.password_hash,
                        role = EXCLUDED.role,
                        full_name = EXCLUDED.full_name,
                        is_active = TRUE
                    """,
                    (
                        user["username"],
                        hash_password(user["password"]),
                        user["role"],
                        user["full_name"],
                    ),
                )

            conn.commit()

    print("Auth tables created successfully.")
    print("Users:")
    print("admin / admin123")
    print("researcher / researcher123")


if __name__ == "__main__":
    main()