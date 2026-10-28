from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db import init_db
from app.queue import router as queue_router
from app.products import router as products_router
from app.catalog_api import router as catalog_router
from app.planner import router as planner_router
from app.ads import router as ads_router
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Marketing Brain", lifespan=lifespan)
app.include_router(queue_router)
app.include_router(products_router)
app.include_router(catalog_router)
app.include_router(planner_router)
app.include_router(ads_router)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/health")
def health():
    return {"status": "ok"}

from fastapi.responses import FileResponse

@app.get("/")
def home():
    return FileResponse("static/index.html")