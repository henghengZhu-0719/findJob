"""数据访问层（Repository）：只做 CRUD，不含业务规则，不管事务提交。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.job import Job


class JobRepo:
    def __init__(self, db: Session):
        self.db = db

    # ---- 读 ----
    def get_by_id(self, job_id: int) -> Optional[Job]:
        return self.db.get(Job, job_id)

    def get_by_fingerprint(self, fp: str) -> Optional[Job]:
        return self.db.scalar(select(Job).where(Job.fingerprint == fp))

    def exists(self, fp: str) -> bool:
        return self.db.scalar(
            select(func.count()).select_from(Job).where(Job.fingerprint == fp)) > 0

    def search(self, *, site: str = None, category: str = None, q: str = None,
               date_from: str = None, date_to: str = None,
               page: int = 1, size: int = 20):
        """返回 (total, items)。"""
        stmt = select(Job)
        if site:
            stmt = stmt.where(Job.site == site)
        if category:
            stmt = stmt.where(Job.category == category)
        if q:
            stmt = stmt.where(Job.title.contains(q))
        if date_from:
            stmt = stmt.where(Job.publish_date >= date_from)
        if date_to:
            stmt = stmt.where(Job.publish_date <= date_to)
        total = self.db.scalar(
            select(func.count()).select_from(stmt.subquery()))
        items = self.db.scalars(
            stmt.order_by(Job.publish_date.desc(), Job.source_id.desc())
                .offset((page - 1) * size).limit(size)).all()
        return total, items

    def all_rows(self, site: str = None) -> list:
        stmt = select(Job)
        if site:
            stmt = stmt.where(Job.site == site)
        return list(self.db.scalars(
            stmt.order_by(Job.publish_date.desc(), Job.source_id.desc())))

    def missing_content(self, site: str = None) -> list:
        stmt = select(Job).where(Job.content == "")
        if site:
            stmt = stmt.where(Job.site == site)
        return list(self.db.scalars(stmt))

    def facets(self) -> dict:
        """筛选项候选值：去重后的站点与分类。"""
        sites = [s for s in self.db.scalars(
            select(Job.site).distinct().order_by(Job.site)) if s]
        cats = [c for c in self.db.scalars(
            select(Job.category).distinct().order_by(Job.category)) if c]
        return {"sites": sites, "categories": cats}

    def stats(self) -> list:
        rows = self.db.execute(
            select(Job.site, func.count().label("total"),
                   func.min(Job.publish_date).label("earliest"),
                   func.max(Job.publish_date).label("latest"))
            .group_by(Job.site).order_by(Job.site)).all()
        return [dict(r._mapping) for r in rows]

    # ---- 写（不 commit，由 service 控制事务边界）----
    def insert(self, **fields) -> Job:
        job = Job(**fields)
        self.db.add(job)
        return job

    def update_content(self, job: Job, content: str, content_html: str) -> None:
        job.content = content
        job.content_html = content_html
