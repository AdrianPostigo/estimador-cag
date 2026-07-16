from contextlib import asynccontextmanager

import logfire
from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.observability import configure_logging
from app.routers.agent import router as agent_router
from app.routers.estimations import router as estimations_router
from app.routers.graph import router as graph_router
from app.routers.sessions import router as sessions_router
from embedding_pipeline.router import router as embeddings_router
from graph.build import build_graph
from graph.checkpointer import checkpointer_conn_string
from graph.observability import configure_logfire

configure_logging()
configure_logfire()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open the graph checkpointer on the project Postgres for the app lifetime.

    The async checkpointer pairs with the FastAPI async stack. setup() creates the
    checkpointer's own tables on first run; it is idempotent afterwards.
    """
    async with AsyncPostgresSaver.from_conn_string(checkpointer_conn_string()) as checkpointer:
        await checkpointer.setup()
        app.state.graph = build_graph(checkpointer)
        yield


app = FastAPI(
    title="Software Estimation API",
    description="API para generar estimaciones de proyectos software a partir de transcripciones usando IA.",
    version="1.0.0",
    lifespan=lifespan,
)

logfire.instrument_fastapi(app)

app.include_router(estimations_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")
app.include_router(embeddings_router, prefix="/api/v1/embeddings")
app.include_router(agent_router, prefix="/api/v1/agent")
app.include_router(graph_router, prefix="/api/v1/graph")


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "service": "Software Estimation API",
        "version": "1.0.0"
    }
