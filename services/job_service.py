"""业务逻辑层：入库规则（去重/元数据刷新/正文保护）、导出、回填。

既服务于 FastAPI 路由，也作为爬虫框架的存储管道（BaseSpider.store）。
事务边界在这一层：repo 只改对象，service 负责 commit。
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session, sessionmaker

from db.database import SessionLocal, init_db
from jobspider.core.models import JobPost
from repos.job_repo import JobRepo

_EXPORT_COLS = ["site", "source_id", "title", "url", "publish_date",
                "category", "content", "extra", "first_seen", "last_seen"]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class JobService:
    def __init__(self, session_factory: sessionmaker = None, db: Session = None):
        """爬虫/CLI 场景不传参自建长会话；FastAPI 场景传入请求级 db。"""
        if db is not None:
            self.db = db
        elif session_factory is not None:
            self.db = session_factory()   # 调用方自备 engine（如测试），不动全局库
        else:
            init_db()
            self.db = SessionLocal()
        self.repo = JobRepo(self.db)

    # ================= 爬虫管道接口 =================
    def has(self, fingerprint: str) -> bool:
        return self.repo.exists(fingerprint)

    def save(self, item: JobPost) -> bool:
        """入库。返回 True=新增；False=已存在（刷新元数据，空正文不覆盖旧正文）。"""
        now = _now()
        row = item.to_row()
        job = self.repo.get_by_fingerprint(row["fingerprint"])
        if job is None:
            self.repo.insert(**row, first_seen=now, last_seen=now)
            self.db.commit()
            return True
        job.title = row["title"]
        job.publish_date = row["publish_date"]
        job.category = row["category"]
        job.extra = row["extra"]
        job.last_seen = now
        if row["content"]:
            job.content = row["content"]
        if row["content_html"]:
            job.content_html = row["content_html"]
        self.db.commit()
        return False

    def rows_missing_content(self, site: str = None) -> list:
        return [{"fingerprint": j.fingerprint, "site": j.site,
                 "source_id": j.source_id, "title": j.title, "url": j.url}
                for j in self.repo.missing_content(site)]

    def set_content(self, fingerprint: str, content: str, content_html: str) -> None:
        job = self.repo.get_by_fingerprint(fingerprint)
        if job is not None:
            self.repo.update_content(job, content, content_html)
            self.db.commit()

    # ================= 查询 / 导出 =================
    def search(self, **kw):
        return self.repo.search(**kw)

    def get(self, job_id: int):
        return self.repo.get_by_id(job_id)

    def facets(self) -> dict:
        return self.repo.facets()

    def stats(self) -> list:
        return self.repo.stats()

    def rows(self, site: str = None) -> list:
        return [{c: getattr(j, c) for c in _EXPORT_COLS}
                for j in self.repo.all_rows(site)]

    def export(self, path, fmt: str = "csv", site: str = None) -> int:
        rows = self.rows(site)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "jsonl":
            with path.open("w", encoding="utf-8") as f:
                for r in rows:
                    r["extra"] = json.loads(r["extra"] or "{}")
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        elif fmt == "csv":
            with path.open("w", encoding="utf-8-sig", newline="") as f:  # sig: Excel 友好
                w = csv.DictWriter(f, fieldnames=_EXPORT_COLS)
                w.writeheader()
                w.writerows(rows)
        else:
            raise ValueError(f"不支持的格式: {fmt}")
        return len(rows)

    def close(self):
        self.db.close()
