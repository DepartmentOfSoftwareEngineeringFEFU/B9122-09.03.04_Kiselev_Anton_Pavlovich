import json
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.database import get_connection
from app.security import require_roles
from app.services.ais_processing import iter_clean_ais_csv_chunks
from app.services.audit import write_audit_log

router = APIRouter(
    prefix="/api/ais",
    tags=["AIS data"],
)

# Можно увеличить до 200_000–300_000, если оперативной памяти хватает.
UPLOAD_CHUNK_SIZE = 100_000


def ensure_navigation_tables_exist(cur) -> None:
    """
    Создаёт базовые таблицы навигационных данных.

    Важно: раньше upload мог упасть на TRUNCATE, если risk_zones или
    vessel_trajectories ещё не были созданы. Теперь загрузка работает даже
    на полностью чистой БД.
    """
    cur.execute(
        """
        CREATE EXTENSION IF NOT EXISTS postgis;

        CREATE TABLE IF NOT EXISTS ais_messages (
            id BIGSERIAL PRIMARY KEY,
            mmsi VARCHAR(20) NOT NULL,
            timestamp_utc TIMESTAMPTZ NOT NULL,
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL,
            speed DOUBLE PRECISION,
            course DOUBLE PRECISION,
            vessel_type VARCHAR(100),
            geom GEOMETRY(Point, 4326),
            UNIQUE (mmsi, timestamp_utc, latitude, longitude)
        );

        CREATE INDEX IF NOT EXISTS idx_ais_messages_geom
        ON ais_messages
        USING GIST (geom);

        CREATE INDEX IF NOT EXISTS idx_ais_messages_mmsi_time
        ON ais_messages (mmsi, timestamp_utc);

        CREATE INDEX IF NOT EXISTS idx_ais_messages_time
        ON ais_messages (timestamp_utc);

        CREATE INDEX IF NOT EXISTS idx_ais_messages_vessel_type
        ON ais_messages (vessel_type);

        CREATE TABLE IF NOT EXISTS vessel_trajectories (
            id BIGSERIAL PRIMARY KEY,
            mmsi VARCHAR(20) NOT NULL,
            start_time TIMESTAMPTZ NOT NULL,
            end_time TIMESTAMPTZ NOT NULL,
            points_count INTEGER NOT NULL,
            geom GEOMETRY(LineString, 4326)
        );

        CREATE INDEX IF NOT EXISTS idx_vessel_trajectories_geom
        ON vessel_trajectories
        USING GIST (geom);

        CREATE INDEX IF NOT EXISTS idx_vessel_trajectories_mmsi
        ON vessel_trajectories (mmsi);

        CREATE INDEX IF NOT EXISTS idx_vessel_trajectories_time
        ON vessel_trajectories (start_time, end_time);

        CREATE TABLE IF NOT EXISTS risk_zones (
            id BIGSERIAL PRIMARY KEY,
            risk_level VARCHAR(50) NOT NULL,
            risk_score DOUBLE PRECISION NOT NULL,
            points_count INTEGER NOT NULL,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            geom GEOMETRY(Geometry, 4326)
        );

        CREATE INDEX IF NOT EXISTS idx_risk_zones_geom
        ON risk_zones
        USING GIST (geom);

        CREATE INDEX IF NOT EXISTS idx_risk_zones_level
        ON risk_zones (risk_level);
        """
    )


def clear_previous_navigation_data(cur) -> None:
    """
    Очистка старого набора навигационных данных перед загрузкой нового CSV.

    Отчёты и журнал действий не удаляются: они являются сохранёнными
    результатами анализа и историей работы пользователя.
    """
    ensure_navigation_tables_exist(cur)
    cur.execute(
        """
        TRUNCATE TABLE
            risk_zones,
            vessel_trajectories,
            ais_messages
        RESTART IDENTITY CASCADE;
        """
    )


def create_temp_import_table(cur) -> None:
    cur.execute(
        """
        CREATE TEMP TABLE temp_ais_import (
            mmsi TEXT,
            timestamp_utc TIMESTAMPTZ,
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            speed DOUBLE PRECISION,
            course DOUBLE PRECISION,
            vessel_type TEXT
        ) ON COMMIT DROP;
        """
    )


def copy_dataframe_to_temp_table(cur, dataframe) -> None:
    """
    Быстрая загрузка chunk-а через COPY вместо множества INSERT.
    На больших CSV это заметно быстрее, чем executemany().
    """
    columns = [
        "mmsi",
        "timestamp_utc",
        "latitude",
        "longitude",
        "speed",
        "course",
        "vessel_type",
    ]

    with cur.copy(
        """
        COPY temp_ais_import (
            mmsi,
            timestamp_utc,
            latitude,
            longitude,
            speed,
            course,
            vessel_type
        ) FROM STDIN
        """
    ) as copy:
        for row in dataframe[columns].itertuples(index=False, name=None):
            copy.write_row(row)


def insert_temp_rows_to_main_table(cur) -> int:
    """
    Переносит строки из временной таблицы в основную таблицу и очищает temp.
    Возвращает число реально вставленных строк.
    """
    cur.execute(
        """
        INSERT INTO ais_messages (
            mmsi,
            timestamp_utc,
            latitude,
            longitude,
            speed,
            course,
            vessel_type,
            geom
        )
        SELECT
            mmsi,
            timestamp_utc,
            latitude,
            longitude,
            speed,
            course,
            vessel_type,
            ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        FROM temp_ais_import
        ON CONFLICT (mmsi, timestamp_utc, latitude, longitude) DO NOTHING;
        """
    )
    inserted_rows = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    cur.execute("TRUNCATE TABLE temp_ais_import;")
    return inserted_rows


@router.post("/upload")
async def upload_ais_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_roles("admin")),
):
    """
    Загрузка архивных АИС-данных из CSV-файла в PostgreSQL/PostGIS.

    Оптимизация: CSV читается чанками, а вставка в БД выполняется через
    временную таблицу и COPY. Это сохраняет текущую кнопку загрузки, но
    ускоряет импорт для демонстрации.
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Поддерживается загрузка только CSV-файлов",
        )

    total_statistics = {
        "initial_rows": 0,
        "valid_rows": 0,
        "removed_rows": 0,
        "removed_duplicates": 0,
        "saved_rows": 0,
        "chunks_processed": 0,
    }

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                clear_previous_navigation_data(cur)
                create_temp_import_table(cur)

                for cleaned_dataframe, statistics in iter_clean_ais_csv_chunks(
                    file.file,
                    chunksize=UPLOAD_CHUNK_SIZE,
                ):
                    total_statistics["initial_rows"] += statistics["initial_rows"]
                    total_statistics["valid_rows"] += statistics["valid_rows"]
                    total_statistics["removed_rows"] += statistics["removed_rows"]
                    total_statistics["removed_duplicates"] += statistics["removed_duplicates"]
                    total_statistics["chunks_processed"] += 1

                    if cleaned_dataframe.empty:
                        continue

                    copy_dataframe_to_temp_table(cur, cleaned_dataframe)
                    total_statistics["saved_rows"] += insert_temp_rows_to_main_table(cur)

                if total_statistics["valid_rows"] == 0:
                    raise HTTPException(
                        status_code=400,
                        detail="После фильтрации не осталось корректных АИС-записей",
                    )

            conn.commit()

        write_audit_log(
            current_user,
            "upload_ais_file",
            {
                "filename": file.filename,
                "statistics": total_statistics,
            },
        )

        return {
            "status": "ok",
            "message": "АИС-данные успешно загружены",
            "filename": file.filename,
            "statistics": total_statistics,
        }

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при загрузке АИС-данных: {str(error)}",
        )


@router.get("/count")
def get_ais_messages_count(
    current_user: dict = Depends(require_roles("admin", "researcher")),
):
    """Получение количества загруженных АИС-сообщений."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM ais_messages;")
            result = cur.fetchone()

    return {
        "status": "ok",
        "count": result["count"],
    }


def ensure_trajectory_table_exists():
    """
    Создание таблицы траекторий, если она ещё не создана.
    """
    create_table_query = """
        CREATE TABLE IF NOT EXISTS vessel_trajectories (
            id SERIAL PRIMARY KEY,
            mmsi VARCHAR(20) NOT NULL,
            start_time TIMESTAMPTZ NOT NULL,
            end_time TIMESTAMPTZ NOT NULL,
            points_count INTEGER NOT NULL,
            geom GEOMETRY(LineString, 4326)
        );

        CREATE INDEX IF NOT EXISTS idx_vessel_trajectories_geom
        ON vessel_trajectories
        USING GIST (geom);

        CREATE INDEX IF NOT EXISTS idx_vessel_trajectories_mmsi
        ON vessel_trajectories (mmsi);

        CREATE INDEX IF NOT EXISTS idx_vessel_trajectories_time
        ON vessel_trajectories (start_time, end_time);
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(create_table_query)
        conn.commit()

@router.post("/build-trajectories")
def build_vessel_trajectories(
    current_user: dict = Depends(require_roles("admin")),
):
    """
    Формирование траекторий движения судов по MMSI на основе загруженных АИС-сообщений.
    Доступно только администратору.
    """
    try:
        ensure_trajectory_table_exists()

        truncate_query = """
            TRUNCATE TABLE vessel_trajectories RESTART IDENTITY;
        """

        build_query = """
            WITH valid_mmsi AS (
                SELECT
                    mmsi
                FROM ais_messages
                WHERE geom IS NOT NULL
                  AND timestamp_utc IS NOT NULL
                GROUP BY mmsi
                HAVING COUNT(*) >= 2
                   AND COUNT(DISTINCT ST_AsText(geom)) >= 2
            )
            INSERT INTO vessel_trajectories (
                mmsi,
                start_time,
                end_time,
                points_count,
                geom
            )
            SELECT
                a.mmsi,
                MIN(a.timestamp_utc) AS start_time,
                MAX(a.timestamp_utc) AS end_time,
                COUNT(*) AS points_count,
                ST_MakeLine(a.geom ORDER BY a.timestamp_utc)::GEOMETRY(LineString, 4326) AS geom
            FROM ais_messages a
            JOIN valid_mmsi v
              ON a.mmsi = v.mmsi
            WHERE a.geom IS NOT NULL
              AND a.timestamp_utc IS NOT NULL
            GROUP BY a.mmsi;
        """

        count_query = """
            SELECT COUNT(*) AS count
            FROM vessel_trajectories;
        """

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(truncate_query)
                cur.execute(build_query)
                cur.execute(count_query)
                result = cur.fetchone()
            conn.commit()

        trajectories_count = int(result["count"])

        write_audit_log(
            current_user,
            "build_trajectories",
            {
                "trajectories_count": trajectories_count,
            },
        )

        return {
            "status": "ok",
            "message": "Траектории судов успешно сформированы",
            "trajectories_count": trajectories_count,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при формировании траекторий: {str(error)}",
        )





@router.get("/trajectories")
def get_vessel_trajectories(
    limit: int = Query(default=500, ge=1, le=5000),
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    min_lon: Optional[float] = None,
    min_lat: Optional[float] = None,
    max_lon: Optional[float] = None,
    max_lat: Optional[float] = None,
    simplify_tolerance: float = Query(default=0.001, ge=0),
    current_user: dict = Depends(require_roles("admin", "researcher")),
):
    """
    Получение подготовленных траекторий судов.

    Для карты отдаём упрощённую геометрию через ST_SimplifyPreserveTopology —
    визуально маршрут остаётся понятным, а GeoJSON становится легче.
    """
    conditions = []
    params = []

    if start_time:
        conditions.append("end_time >= %s")
        params.append(start_time)

    if end_time:
        conditions.append("start_time <= %s")
        params.append(end_time)

    bbox_is_set = all(
        value is not None
        for value in [min_lon, min_lat, max_lon, max_lat]
    )

    if bbox_is_set:
        conditions.append(
            """
            ST_Intersects(
                geom,
                ST_MakeEnvelope(%s, %s, %s, %s, 4326)
            )
            """
        )
        params.extend([min_lon, min_lat, max_lon, max_lat])

    where_sql = ""
    if conditions:
        where_sql = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT
            id,
            mmsi,
            start_time,
            end_time,
            points_count,
            ST_AsGeoJSON(
                CASE
                    WHEN %s > 0 THEN ST_SimplifyPreserveTopology(geom, %s)
                    ELSE geom
                END
            ) AS geometry
        FROM vessel_trajectories
        {where_sql}
        ORDER BY points_count DESC
        LIMIT %s;
    """

    query_params = [simplify_tolerance, simplify_tolerance] + params + [limit]

    with get_connection() as conn:
        with conn.cursor() as cur:
            ensure_navigation_tables_exist(cur)
            cur.execute(query, query_params)
            rows = cur.fetchall()

    features = []

    for row in rows:
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(row["geometry"]),
                "properties": {
                    "id": row["id"],
                    "mmsi": row["mmsi"],
                    "start_time": row["start_time"].isoformat(),
                    "end_time": row["end_time"].isoformat(),
                    "points_count": row["points_count"],
                },
            }
        )

    return {
        "status": "ok",
        "count": len(features),
        "type": "FeatureCollection",
        "features": features,
    }
