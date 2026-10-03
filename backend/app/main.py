import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import auth, files, pipeline, storage
from app.db import engine, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    await storage.ensure_bucket()
    await pipeline.resume_pending()
    yield
    await engine.dispose()


app = FastAPI(title="Gnani audio summarizer", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(files.router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
