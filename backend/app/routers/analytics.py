import json

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_connection
from app.security import require_roles
from app.services.audit import write_audit_log

router = APIRouter(
    prefix="/api/analytics",
    tags=["analytics"],
)

DEFAULT_CELL_SIZE = 0.03
DEFAULT_MAX_CELLS = 3000


def ensure_analytics_tables_exist(cur) -> None:
    """
    Таблицы аналитических слоёв.

    Идея для быстрой демонстрации: heatmap и risk_zones считаются один раз,
    сохраняются в БД, а кнопки на фронте потом просто получают готовые слои.
    """
    cur.execute(
        """
        CREATE EXTENSION IF NOT EXISTS postgis;

        CREATE TABLE IF NOT EXISTS heatmap_cells (
            id BIGSERIAL PRIMARY KEY,
            cell_size DOUBLE PRECISION NOT NULL,
            grid_lon DOUBLE PRECISION NOT NULL,
            grid_lat DOUBLE PRECISION NOT NULL,
            center_lon DOUBLE PRECISION NOT NULL,
            center_lat DOUBLE PRECISION NOT NULL,
            points_count INTEGER NOT NULL,
            intensity DOUBLE PRECISION NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            geom GEOMETRY(Point, 4326)
        );

        CREATE INDEX IF NOT EXISTS idx_heatmap_cells_geom
        ON heatmap_cells
        USING GIST (geom);

        CREATE INDEX IF NOT EXISTS idx_heatmap_cells_size_count
        ON heatmap_cells (cell_size, points_count DESC);

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


def build_heatmap_logic(cur, cell_size: float, max_cells: int) -> dict:
    """
    Строит и сохраняет heatmap по сетке.

    Сделано без тяжёлого ST_Union/ST_Buffer по всем траекториям, потому что для
    защиты важнее стабильная и быстрая демонстрация. Ограничение max_cells
    не даёт карте и браузеру зависнуть на огромном GeoJSON.
    """
    cur.execute("TRUNCATE TABLE heatmap_cells RESTART IDENTITY;")

    cur.execute(
        """
        WITH cells AS (
            SELECT
                FLOOR(longitude / %s) * %s AS grid_lon,
                FLOOR(latitude / %s) * %s AS grid_lat,
                COUNT(*)::INTEGER AS points_count,
                AVG(longitude) AS center_lon,
                AVG(latitude) AS center_lat
            FROM ais_messages
            WHERE latitude IS NOT NULL
              AND longitude IS NOT NULL
              AND geom IS NOT NULL
            GROUP BY grid_lon, grid_lat
        ),
        ranked AS (
            SELECT *
            FROM cells
            ORDER BY points_count DESC
            LIMIT %s
        ),
        max_value AS (
            SELECT COALESCE(MAX(points_count), 1) AS max_points_count
            FROM ranked
        )
        INSERT INTO heatmap_cells (
            cell_size,
            grid_lon,
            grid_lat,
            center_lon,
            center_lat,
            points_count,
            intensity,
            geom
        )
        SELECT
            %s AS cell_size,
            r.grid_lon,
            r.grid_lat,
            r.center_lon,
            r.center_lat,
            r.points_count,
            ROUND((r.points_count::numeric / m.max_points_count)::numeric, 3)::DOUBLE PRECISION AS intensity,
            ST_SetSRID(ST_MakePoint(r.center_lon, r.center_lat), 4326) AS geom
        FROM ranked r
        CROSS JOIN max_value m;
        """,
        (
            cell_size,
            cell_size,
            cell_size,
            cell_size,
            max_cells,
            cell_size,
        ),
    )

    cur.execute("SELECT COUNT(*) AS count FROM heatmap_cells;")
    result = cur.fetchone()

    return {
        "cells_count": int(result["count"]),
        "cell_size": cell_size,
        "max_cells": max_cells,
    }


@router.post("/build-heatmap")
def build_heatmap(
    cell_size: float = Query(default=DEFAULT_CELL_SIZE, gt=0),
    max_cells: int = Query(default=DEFAULT_MAX_CELLS, ge=100, le=50_000),
    current_user: dict = Depends(require_roles("admin")),
):
    """
    Предварительное построение heatmap.

    Эту кнопку лучше нажать один раз после загрузки AIS и построения траекторий.
    Потом /heatmap будет отдавать готовый слой быстро.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            ensure_analytics_tables_exist(cur)
            result = build_heatmap_logic(cur, cell_size, max_cells)
        conn.commit()

    write_audit_log(
        current_user,
        "build_heatmap",
        result,
    )

    return {
        "status": "ok",
        "message": "Тепловая карта успешно сформирована",
        **result,
    }


@router.get("/heatmap")
def get_heatmap(
    cell_size: float = Query(default=DEFAULT_CELL_SIZE, gt=0),
    max_cells: int = Query(default=DEFAULT_MAX_CELLS, ge=100, le=50_000),
    rebuild: bool = Query(default=False),
    current_user: dict = Depends(require_roles("admin", "researcher")),
):
    """
    Получение heatmap плотности движения судов.

    По умолчанию возвращается сохранённый слой. Если слоя ещё нет, он строится
    автоматически один раз. Это сильно быстрее, чем пересчитывать heatmap на
    каждый запрос карты.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            ensure_analytics_tables_exist(cur)

            if rebuild:
                build_heatmap_logic(cur, cell_size, max_cells)
                conn.commit()

            cur.execute("SELECT COUNT(*) AS count FROM heatmap_cells;")
            cells_count_result = cur.fetchone()

            if int(cells_count_result["count"]) == 0:
                build_heatmap_logic(cur, cell_size, max_cells)
                conn.commit()

            cur.execute(
                """
                SELECT
                    center_lat,
                    center_lon,
                    points_count,
                    intensity
                FROM heatmap_cells
                ORDER BY points_count DESC
                LIMIT %s;
                """,
                (max_cells,),
            )
            rows = cur.fetchall()

    heatmap = [
        {
            "latitude": round(float(row["center_lat"]), 6),
            "longitude": round(float(row["center_lon"]), 6),
            "points_count": int(row["points_count"]),
            "intensity": round(float(row["intensity"]), 3),
        }
        for row in rows
    ]

    return {
        "status": "ok",
        "cell_size": cell_size,
        "count": len(heatmap),
        "heatmap": heatmap,
    }


@router.post("/build-risk-zones")
def build_risk_zones(
    cell_size: float = Query(default=DEFAULT_CELL_SIZE, gt=0),
    low_threshold: int = Query(default=1, ge=1),
    medium_threshold: int = Query(default=2, ge=1),
    high_threshold: int = Query(default=3, ge=1),
    max_zones: int = Query(default=1500, ge=10, le=50_000),
    current_user: dict = Depends(require_roles("admin")),
):
    """
    Формирование зон навигационного риска по уже рассчитанной heatmap.

    Это быстрее старой схемы, где зоны строились через коридор, ST_Union,
    ST_Buffer и пересечение геометрий. Для демонстрации сохраняется смысл:
    ячейки с большей плотностью движения получают более высокий риск.
    """
    if not (low_threshold <= medium_threshold <= high_threshold):
        raise HTTPException(
            status_code=400,
            detail="Пороги должны удовлетворять условию: low <= medium <= high",
        )

    with get_connection() as conn:
        with conn.cursor() as cur:
            ensure_analytics_tables_exist(cur)

            cur.execute("SELECT COUNT(*) AS count FROM heatmap_cells;")
            heatmap_count = int(cur.fetchone()["count"])
            if heatmap_count == 0:
                build_heatmap_logic(cur, cell_size, DEFAULT_MAX_CELLS)

            cur.execute("TRUNCATE TABLE risk_zones RESTART IDENTITY;")

            cur.execute(
                """
                WITH selected_cells AS (
                    SELECT
                        grid_lon,
                        grid_lat,
                        points_count
                    FROM heatmap_cells
                    WHERE points_count >= %s
                    ORDER BY points_count DESC
                    LIMIT %s
                )
                INSERT INTO risk_zones (
                    risk_level,
                    risk_score,
                    points_count,
                    description,
                    geom
                )
                SELECT
                    CASE
                        WHEN points_count >= %s THEN 'high'
                        WHEN points_count >= %s THEN 'medium'
                        ELSE 'low'
                    END AS risk_level,
                    CASE
                        WHEN points_count >= %s THEN 100
                        WHEN points_count >= %s THEN 60
                        ELSE 30
                    END AS risk_score,
                    points_count,
                    'Зона навигационного риска, сформированная по плотности ретроспективных АИС-точек. Количество точек в ячейке: '
                        || points_count::TEXT AS description,
                    ST_MakeEnvelope(
                        grid_lon,
                        grid_lat,
                        grid_lon + %s,
                        grid_lat + %s,
                        4326
                    ) AS geom
                FROM selected_cells;
                """,
                (
                    low_threshold,
                    max_zones,
                    high_threshold,
                    medium_threshold,
                    high_threshold,
                    medium_threshold,
                    cell_size,
                    cell_size,
                ),
            )

            cur.execute(
                """
                SELECT
                    COUNT(*) AS zones_count,
                    COUNT(*) FILTER (WHERE risk_level = 'low') AS low_zones_count,
                    COUNT(*) FILTER (WHERE risk_level = 'medium') AS medium_zones_count,
                    COUNT(*) FILTER (WHERE risk_level = 'high') AS high_zones_count
                FROM risk_zones;
                """
            )
            counters = cur.fetchone()
        conn.commit()

    result = {
        "cell_size": cell_size,
        "low_threshold": low_threshold,
        "medium_threshold": medium_threshold,
        "high_threshold": high_threshold,
        "zones_count": int(counters["zones_count"]),
        "low_zones_count": int(counters["low_zones_count"]),
        "medium_zones_count": int(counters["medium_zones_count"]),
        "high_zones_count": int(counters["high_zones_count"]),
        "max_zones": max_zones,
    }

    write_audit_log(
        current_user,
        "build_risk_zones",
        result,
    )

    return {
        "status": "ok",
        "message": "Зоны риска успешно сформированы",
        **result,
    }


@router.get("/risk-zones")
def get_risk_zones(
    limit: int = Query(default=5000, ge=1, le=50_000),
    simplify_tolerance: float = Query(default=0.0, ge=0),
    current_user: dict = Depends(require_roles("admin", "researcher")),
):
    """Получение зон риска в формате GeoJSON."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            ensure_analytics_tables_exist(cur)
            cur.execute(
                """
                SELECT
                    id,
                    risk_level,
                    risk_score,
                    points_count,
                    description,
                    created_at,
                    ST_AsGeoJSON(
                        CASE
                            WHEN %s > 0 THEN ST_SimplifyPreserveTopology(geom, %s)
                            ELSE geom
                        END
                    ) AS geometry
                FROM risk_zones
                WHERE geom IS NOT NULL
                  AND NOT ST_IsEmpty(geom)
                ORDER BY id
                LIMIT %s;
                """,
                (simplify_tolerance, simplify_tolerance, limit),
            )
            rows = cur.fetchall()

    features = []

    for row in rows:
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(row["geometry"]),
                "properties": {
                    "id": row["id"],
                    "risk_level": row["risk_level"],
                    "risk_score": row["risk_score"],
                    "points_count": row["points_count"],
                    "description": row["description"],
                    "created_at": row["created_at"].isoformat(),
                },
            }
        )

    return {
        "status": "ok",
        "count": len(features),
        "type": "FeatureCollection",
        "features": features,
    }
