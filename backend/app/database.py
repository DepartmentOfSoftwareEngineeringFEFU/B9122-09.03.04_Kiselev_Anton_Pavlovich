import psycopg
from psycopg.rows import dict_row

DB_CONFIG = {
    "dbname": "marine_dss",
    "user": "marine_user",
    "password": "marine_password",
    "host": "127.0.0.1",
    "port": 5433,
}


def get_connection():
    return psycopg.connect(**DB_CONFIG, row_factory=dict_row)