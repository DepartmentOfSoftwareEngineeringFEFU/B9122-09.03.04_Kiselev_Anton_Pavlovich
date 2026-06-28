import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from app.database import get_connection
from app.routers.dss import RouteEvaluationRequest, evaluate_route_logic
from app.security import require_roles
from app.services.audit import write_audit_log

router = APIRouter(
    prefix="/api/reports",
    tags=["reports"],
)


def ensure_reports_table_exists():
    create_table_query = """
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            route_name VARCHAR(255),
            risk_level VARCHAR(50),
            risk_score DOUBLE PRECISION,
            content TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(create_table_query)
        conn.commit()


def risk_level_ru(level: str) -> str:
    if level == "high":
        return "высокий"
    if level == "medium":
        return "средний"
    if level == "low":
        return "низкий"
    return "не определён"


def format_report_date(value) -> str:
    """Возвращает дату в читаемом виде без технического +00:00."""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y %H:%M")

    try:
        prepared = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(prepared)
        return parsed.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(value)


def build_report_recommendations(summary: dict) -> list[str]:
    risk_level = summary.get("risk_level")
    risky_length_percent = float(summary.get("risky_length_percent") or 0)
    high_segments_count = int(summary.get("high_segments_count") or 0)
    medium_segments_count = int(summary.get("medium_segments_count") or 0)
    intersections_count = int(summary.get("intersections_count") or 0)

    recommendations = []

    recommendations.append(
        f"Маршрут имеет {risk_level_ru(risk_level)} уровень навигационного риска. "
        "Рекомендуется учитывать результаты оценки при планировании прохождения маршрута."
    )

    if high_segments_count > 0:
        recommendations.append(
            "На маршруте выявлены участки высокого риска. "
            "Рекомендуется по возможности скорректировать отдельные точки маршрута в этих районах; "
            "если изменение маршрута невозможно — обеспечить усиленное наблюдение, контроль по АИС и радиосвязь."
        )

    if medium_segments_count > 0:
        recommendations.append(
            "На участках среднего риска рекомендуется снизить скорость, контролировать дистанцию до других судов "
            "и учитывать повышенную плотность движения."
        )

    if risky_length_percent >= 50:
        recommendations.append(
            "Значительная часть маршрута проходит через зоны риска. "
            "Рекомендуется усилить контроль прохождения данных участков и при необходимости скорректировать отдельные точки маршрута."
        )

    if intersections_count == 0:
        recommendations.append(
            "Пересечения с зонами риска не выявлены. Маршрут может быть использован при стандартном контроле навигационной обстановки."
        )

    return recommendations


def build_report_text(report: dict) -> str:
    content = json.loads(report["content"])
    summary = content["risk_summary"]

    route_name = report["route_name"] or report["title"]
    report_date = format_report_date(report["created_at"])
    recommendations = build_report_recommendations(summary)

    lines = [
        "ОТЧЁТ",
        "",
        f"Наименование: {route_name}",
        f"Дата оформления: {report_date}",
        "",
        "ОЦЕНКА РИСКА МАРШРУТА",
        f"Длина маршрута: {summary['route_length_m']} м",
        f"Длина маршрута в зонах риска: {summary['risky_length_m']} м",
        f"Доля маршрута в зонах риска: {summary['risky_length_percent']}%",
        f"Интегральная оценка риска: {summary['risk_score']} / 100",
        f"Уровень риска: {risk_level_ru(summary['risk_level'])}",
        "",
        "ПРОБЛЕМНЫЕ СЕГМЕНТЫ",
        f"Количество пересечений с зонами риска: {summary['intersections_count']}",
        f"Сегменты низкого риска: {summary['low_segments_count']}",
        f"Сегменты среднего риска: {summary['medium_segments_count']}",
        f"Сегменты высокого риска: {summary['high_segments_count']}",
        "",
        "РЕКОМЕНДАЦИИ",
    ]

    for index, recommendation in enumerate(recommendations, start=1):
        lines.append(f"{index}. {recommendation}")

    lines.extend(
        [
            "",
            "ПРИМЕЧАНИЕ",
            "Результаты работы системы используются для поддержки принятия решений "
            "и не заменяют ответственность лица, принимающего решение.",
        ]
    )

    return "\n".join(lines)


@router.post("/route-report")
def create_route_report(
    request: RouteEvaluationRequest,
    current_user: dict = Depends(require_roles("researcher")),
):
    """
    Формирование отчёта по результатам оценки маршрута.
    Доступно только исследователю.
    """
    ensure_reports_table_exists()

    evaluation = evaluate_route_logic(
        request=request,
        current_user=current_user,
        write_log=False,
    )

    summary = evaluation["risk_summary"]

    title = request.route_name
    content = json.dumps(evaluation, ensure_ascii=False, default=str)

    insert_query = """
        INSERT INTO reports (
            title,
            route_name,
            risk_level,
            risk_score,
            content
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                insert_query,
                (
                    title,
                    request.route_name,
                    summary["risk_level"],
                    summary["risk_score"],
                    content,
                ),
            )
            report = cur.fetchone()
        conn.commit()

    report_id = report["id"]

    write_audit_log(
        current_user,
        "create_route_report",
        {
            "report_id": report_id,
            "route_name": request.route_name,
            "risk_score": summary["risk_score"],
            "risk_level": summary["risk_level"],
        },
    )

    return {
        "status": "ok",
        "message": "Отчёт успешно сформирован",
        "report_id": report_id,
        "route_name": request.route_name,
        "risk_score": summary["risk_score"],
        "risk_level": summary["risk_level"],
        "evaluation": evaluation,
    }


@router.get("")
def get_reports(
    current_user: dict = Depends(require_roles("researcher")),
):
    """
    Получение списка сформированных отчётов.
    Доступно только исследователю.
    """
    ensure_reports_table_exists()

    query = """
        SELECT
            id,
            title,
            route_name,
            risk_level,
            risk_score,
            created_at
        FROM reports
        ORDER BY created_at DESC;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()

    return {
        "status": "ok",
        "count": len(rows),
        "reports": rows,
    }


@router.get("/{report_id}")
def get_report(
    report_id: int,
    current_user: dict = Depends(require_roles("researcher")),
):
    """
    Получение одного отчёта по идентификатору.
    Доступно только исследователю.
    """
    ensure_reports_table_exists()

    query = """
        SELECT
            id,
            title,
            route_name,
            risk_level,
            risk_score,
            content,
            created_at
        FROM reports
        WHERE id = %s;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (report_id,))
            report = cur.fetchone()

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Отчёт не найден",
        )

    return {
        "status": "ok",
        "report": report,
    }


@router.get("/{report_id}/export-txt")
def export_report_txt(
    report_id: int,
    current_user: dict = Depends(require_roles("researcher")),
):
    """
    Экспорт отчёта в TXT.
    Доступно только исследователю.
    """
    ensure_reports_table_exists()

    query = """
        SELECT
            id,
            title,
            route_name,
            risk_level,
            risk_score,
            content,
            created_at
        FROM reports
        WHERE id = %s;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (report_id,))
            report = cur.fetchone()

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Отчёт не найден",
        )

    write_audit_log(
        current_user,
        "export_report_txt",
        {
            "report_id": report_id,
            "route_name": report["route_name"],
        },
    )

    report_text = build_report_text(report)

    filename = f"route_report_{report_id}.txt"

    return PlainTextResponse(
        content=report_text,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
