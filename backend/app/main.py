from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import get_connection
from app.routers import ais, analytics, dss, reports, auth

app = FastAPI(
    title="Marine DSS API",
    description="API программного средства поддержки принятия решений при обеспечении безопасности движения морских судов",
    version="0.1.0",
    openapi_version="3.0.3",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ais.router)
app.include_router(analytics.router)
app.include_router(dss.router)
app.include_router(reports.router)
app.include_router(auth.router)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "Marine DSS backend is running"
    }


@app.get("/db-health")
def database_health_check():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT PostGIS_Version() AS version;")
                result = cur.fetchone()

        return {
            "status": "ok",
            "database": "connected",
            "postgis_version": result["version"]
        }

    except Exception as error:
        return {
            "status": "error",
            "database": "not connected",
            "detail": str(error)
        }