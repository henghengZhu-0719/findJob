"""Pydantic 模型层：定时采集状态。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class CrawlStatus(BaseModel):
    schedule: List[str] = []          # 每天触发时刻 HH:MM，空 = 定时关闭
    running: bool = False
    next_at: Optional[str] = None
    last_started: Optional[str] = None
    last_finished: Optional[str] = None
    last_result: dict = {}            # 爬虫名 -> {new, dup, old, detail_fail, errors}


class CrawlTriggered(BaseModel):
    msg: str
