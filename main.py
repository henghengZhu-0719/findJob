"""FastAPI 入口。

  uv run python -m uvicorn main:app --reload      # API + 前端（构建产物）
前端开发模式另开一个终端：cd frontend && npm run dev （5173 端口，/api 走代理）
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from db.database import init_db
from routes.job_route import router

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="findJob API", description="招聘公告采集与查询", lifespan=lifespan)
app.include_router(router)

# 前端构建产物（npm run build 生成）。放在路由注册之后，避免吃掉 /api
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html")
