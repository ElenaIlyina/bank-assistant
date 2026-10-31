from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import router
from app.lifecycle import lifespan


def create_app() -> FastAPI:
    app = FastAPI(title="bank-assistant", lifespan=lifespan)
    app.include_router(router)

    @app.get("/live")
    async def live() -> JSONResponse:
        return JSONResponse(status_code=200, content={"status": "live"})

    @app.get("/ready")
    async def ready(request: Request) -> JSONResponse:
        db = getattr(request.app.state, "db", None)
        if db is None or not db.is_ready or db.pool is None:
            return JSONResponse(status_code=503, content={"status": "not ready"})
        try:
            await db.pool.fetchval("SELECT 1")
        except Exception:
            return JSONResponse(status_code=503, content={"status": "not ready"})
        return JSONResponse(status_code=200, content={"status": "ready"})

    return app


app = create_app()
