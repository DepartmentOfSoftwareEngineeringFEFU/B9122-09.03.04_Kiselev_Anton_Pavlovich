import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.database import get_connection
from app.security import require_roles
from app.services.audit import write_audit_log

router = APIRouter(
    prefix="/api/dss",
    tags=["decision support"],
)


class RoutePoint(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class RouteEvaluationRequest(BaseModel):
    route_name: str = "Планируемый маршрут"
    points: List[RoutePoint]


def get_route_risk_level(risk_score: float) -> str:
    if risk_score >= 66:
        return "high"
    if risk_score >= 33:
        return "medium"
    return "low"


def build_recommendations(
    risk_level: str,
    risky_length_percent: float,
    high_segments_count: int,
    medium_segments_count: int,
    intersections_count: int,
) -> list[str]:
    """
    Формирование рекомендаций по результатам оценки маршрута.

    Формулировки сделаны в дипломном стиле: система не отдаёт жёсткую команду,
    а предлагает усилить контроль, скорректировать проблемные участки и
    использовать дополнительные средства наблюдения.
    """
    recommendations = []

    if risk_level == "high":
        recommendations.append(
            "Маршрут имеет высокий уровень навигационного риска. "
            "Рекомендуется выполнить дополнительную проверку маршрута, "
            "усилить контроль движения на проблемных участках и при необходимости "
            "скорректировать отдельные точки маршрута."
        )
    elif risk_level == "medium":
        recommendations.append(
            "Маршрут имеет средний уровень навигационного риска. "
            "Рекомендуется усилить контроль движения на проблемных участках "
            "и учитывать плотность судового трафика при прохождении маршрута."
        )
    else:
        recommendations.append(
            "Маршрут имеет низкий уровень навигационного риска. "
            "Маршрут может быть рассмотрен как допустимый при соблюдении "
            "стандартных мер навигационного контроля."
        )

    if high_segments_count > 0:
        recommendations.append(
            "На маршруте выявлены участки пересечения с зонами высокого риска. "
            "При прохождении данных участков рекомендуется обеспечить повышенное "
            "наблюдение, использовать данные АИС, визуальный контроль и радиосвязь, "
            "а также при необходимости скорректировать маршрут в пределах безопасной акватории."
        )

    if medium_segments_count > 0:
        recommendations.append(
            "На маршруте выявлены участки пересечения с зонами среднего риска. "
            "Рекомендуется снизить скорость на данных участках, контролировать дистанцию "
            "до других судов и учитывать возможное пересечение судовых потоков."
        )

    if risky_length_percent > 50:
        recommendations.append(
            "Значительная часть маршрута проходит через зоны навигационного риска. "
            "Рекомендуется обеспечить усиленное сопровождение прохождения маршрута "
            "и при необходимости локально скорректировать проблемные участки."
        )

    if intersections_count == 0:
        recommendations.append(
            "Пересечения с зонами риска не обнаружены. "
            "Рекомендуется продолжать движение с соблюдением стандартных требований "
            "навигационной безопасности."
        )

    return recommendations


def evaluate_route_logic(
    request: RouteEvaluationRequest,
    current_user: dict | None = None,
    write_log: bool = True,
):
    """
    Внутренняя логика оценки маршрута.
    Используется и endpoint-ом DSS, и подсистемой отчётности.
    """
    if len(request.points) < 2:
        raise HTTPException(
            status_code=400,
            detail="Маршрут должен содержать минимум две точки",
        )

    route_coordinates = [
        [point.longitude, point.latitude]
        for point in request.points
    ]

    route_geometry = {
        "type": "LineString",
        "coordinates": route_coordinates,
    }

    route_geometry_json = json.dumps(route_geometry)

    route_length_query = """
        SELECT
            ST_Length(
                ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)::geography
            ) AS route_length_m;
    """

    intersections_query = """
        WITH route AS (
            SELECT ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326) AS geom
        ),
        intersections AS (
            SELECT
                rz.id AS zone_id,
                rz.risk_level,
                rz.risk_score,
                rz.points_count,
                rz.description,
                ST_CollectionExtract(
                    ST_Intersection(route.geom, rz.geom),
                    2
                ) AS geom
            FROM risk_zones rz, route
            WHERE ST_Intersects(route.geom, rz.geom)
        )
        SELECT
            zone_id,
            risk_level,
            risk_score,
            points_count,
            description,
            ROUND(ST_Length(geom::geography)::numeric, 2) AS length_m,
            ST_AsGeoJSON(geom) AS geometry
        FROM intersections
        WHERE NOT ST_IsEmpty(geom)
          AND ST_Length(geom::geography) > 0
        ORDER BY zone_id;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(route_length_query, (route_geometry_json,))
            route_length_result = cur.fetchone()

            cur.execute(intersections_query, (route_geometry_json,))
            rows = cur.fetchall()

    route_length_m = round(float(route_length_result["route_length_m"] or 0), 2)

    if route_length_m <= 0:
        raise HTTPException(
            status_code=400,
            detail="Длина маршрута должна быть больше 0",
        )

    problem_features = []
    weighted_risk_sum = 0.0
    risky_length_m = 0.0
    low_segments_count = 0
    medium_segments_count = 0
    high_segments_count = 0

    for row in rows:
        length_m = float(row["length_m"])
        risk_score = float(row["risk_score"])
        risk_level = row["risk_level"]

        risky_length_m += length_m
        weighted_risk_sum += length_m * risk_score

        if risk_level == "high":
            high_segments_count += 1
        elif risk_level == "medium":
            medium_segments_count += 1
        else:
            low_segments_count += 1

        problem_features.append(
            {
                "type": "Feature",
                "geometry": json.loads(row["geometry"]),
                "properties": {
                    "zone_id": row["zone_id"],
                    "risk_level": risk_level,
                    "risk_score": risk_score,
                    "points_count": row["points_count"],
                    "description": row["description"],
                    "length_m": round(length_m, 2),
                },
            }
        )

    route_risk_score = round(weighted_risk_sum / route_length_m, 2)
    route_risk_level = get_route_risk_level(route_risk_score)

    risky_length_m = round(risky_length_m, 2)
    risky_length_percent = round((risky_length_m / route_length_m) * 100, 2)

    intersections_count = len(problem_features)

    recommendations = build_recommendations(
        risk_level=route_risk_level,
        risky_length_percent=risky_length_percent,
        high_segments_count=high_segments_count,
        medium_segments_count=medium_segments_count,
        intersections_count=intersections_count,
    )

    result = {
        "status": "ok",
        "route": {
            "type": "Feature",
            "geometry": route_geometry,
            "properties": {
                "route_name": request.route_name,
                "route_length_m": route_length_m,
            },
        },
        "problem_segments": {
            "type": "FeatureCollection",
            "features": problem_features,
        },
        "risk_summary": {
            "route_name": request.route_name,
            "route_length_m": route_length_m,
            "risky_length_m": risky_length_m,
            "risky_length_percent": risky_length_percent,
            "risk_score": route_risk_score,
            "risk_level": route_risk_level,
            "intersections_count": intersections_count,
            "low_segments_count": low_segments_count,
            "medium_segments_count": medium_segments_count,
            "high_segments_count": high_segments_count,
        },
        "recommendations": recommendations,
    }

    if write_log and current_user:
        write_audit_log(
            current_user,
            "evaluate_route",
            {
                "route_name": request.route_name,
                "risk_score": route_risk_score,
                "risk_level": route_risk_level,
                "intersections_count": intersections_count,
            },
        )

    return result


@router.post("/evaluate-route")
def evaluate_route(
    request: RouteEvaluationRequest,
    current_user: dict = Depends(require_roles("researcher")),
):
    """
    Оценка риска планируемого маршрута.
    Доступно только исследователю.
    """
    return evaluate_route_logic(
        request=request,
        current_user=current_user,
        write_log=True,
    )
