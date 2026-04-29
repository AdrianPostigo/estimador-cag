from fastapi import FastAPI

from app.routers.estimations import router as estimations_router

app = FastAPI(
    title="Software Estimation API",
    version="1.0.0",
)

app.include_router(estimations_router)