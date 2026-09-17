"""路由层：只做参数校验与编排，业务全部下沉 service。"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.database import get_db
from schemas.job import FacetsOut, JobOut, PageOut, SiteStats
from services.job_service import JobService

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def get_service(db: Session = Depends(get_db)) -> JobService:
    return JobService(db=db)


@router.get("", response_model=PageOut, summary="分页查询公告")
def list_jobs(site: Optional[str] = None,
              category: Optional[str] = None,
              q: Optional[str] = Query(None, description="标题关键词"),
              date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
              date_to: Optional[str] = None,
              page: int = Query(1, ge=1),
              size: int = Query(20, ge=1, le=100),
              svc: JobService = Depends(get_service)):
    total, items = svc.search(site=site, category=category, q=q,
                              date_from=date_from, date_to=date_to,
                              page=page, size=size)
    return PageOut(total=total, page=page, size=size, items=items)


@router.get("/stats", response_model=List[SiteStats], summary="各站点入库统计")
def stats(svc: JobService = Depends(get_service)):
    return svc.stats()


@router.get("/facets", response_model=FacetsOut, summary="筛选项候选值")
def facets(svc: JobService = Depends(get_service)):
    return svc.facets()


# 放在最后：动态段 /{job_id} 会吃掉上面所有静态路径
@router.get("/{job_id}", response_model=JobOut, summary="公告详情（含正文）")
def get_job(job_id: int, svc: JobService = Depends(get_service)):
    job = svc.get(job_id)
    if job is None:
        raise HTTPException(404, "公告不存在")
    return job
