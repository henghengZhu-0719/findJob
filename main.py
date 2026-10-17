"""FastAPI 入口。

  uv run python -m uvicorn main:app --reload      # API + 前端（构建产物）+ 定时采集
前端开发模式另开一个终端：cd frontend && npm run dev （5173 端口，/api 走代理）
定时采集时刻见 jobspider/settings.py 的 CRAWL_AT（环境变量 JOBSPIDER_CRAWL_AT 覆盖）
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from db.database import init_db
from jobspider import settings
from routes.crawl_route import router as crawl_router
from routes.job_route import router
from services.crawl_scheduler import CrawlScheduler

STATIC_DIR = Path(__file__).parent / "static"

# uvicorn 只给自己的 logger 配 handler，不配 root 的话爬虫/调度日志不会输出
logging.basicConfig(level=logging.INFO, format=settings.LOG_FORMAT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.scheduler = CrawlScheduler()
    app.state.scheduler.start()
    yield
    app.state.scheduler.stop()


app = FastAPI(title="findJob API", description="招聘公告采集与查询", lifespan=lifespan)
app.include_router(router)
app.include_router(crawl_router)

# 前端构建产物（npm run build 生成）。放在路由注册之后，避免吃掉 /api
# 判断具体文件而非目录：构建中途被杀会留下不完整的 static/
if (STATIC_DIR / "index.html").is_file() and (STATIC_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html")
