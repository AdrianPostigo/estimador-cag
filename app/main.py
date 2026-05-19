from fastapi import FastAPI

from app.observability import configure_logging
from app.routers.estimations import router as estimations_router
from app.routers.sessions import router as sessions_router

configure_logging()

app = FastAPI(
    title="Software Estimation API",
    description="API para generar estimaciones de proyectos software a partir de transcripciones usando IA.",
    version="1.0.0",
)

app.include_router(estimations_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "service": "Software Estimation API",
        "version": "1.0.0"
    }
