"""路由层：定时采集的状态查询与手动触发。调度器实例挂在 app.state 上，由 main.py 生命周期创建。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from schemas.crawl import CrawlStatus, CrawlTriggered
from services.crawl_scheduler import CrawlScheduler

router = APIRouter(prefix="/api/crawl", tags=["crawl"])


def get_scheduler(request: Request) -> CrawlScheduler:
    return request.app.state.scheduler


@router.get("/status", response_model=CrawlStatus, summary="定时采集状态")
def status(sch: CrawlScheduler = Depends(get_scheduler)):
    return sch.status()


@router.post("/run", response_model=CrawlTriggered, status_code=202,
             summary="立即采集一轮（后台执行，进度看 /status）")
def run_now(sch: CrawlScheduler = Depends(get_scheduler)):
    if not sch.trigger():
        raise HTTPException(409, "已有一轮采集在进行中")
    return {"msg": "已开始采集"}
