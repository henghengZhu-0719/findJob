"""Pydantic 模型层：API 出入参。"""
from __future__ import annotations

import json
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class JobBrief(BaseModel):
    """列表项：不带正文。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    site: str
    source_id: str
    title: str
    url: str
    publish_date: str = ""
    category: str = ""
    first_seen: str = ""
    last_seen: str = ""


class JobOut(JobBrief):
    """详情：含正文与站点扩展字段。"""
    content: str = ""
    content_html: str = ""   # 原站正文 HTML，前端消毒后渲染
    extra: dict = {}

    @field_validator("extra", mode="before")
    @classmethod
    def _parse_extra(cls, v):
        if isinstance(v, str):
            return json.loads(v or "{}")
        return v or {}


class PageOut(BaseModel):
    total: int
    page: int
    size: int
    items: List[JobBrief]


class FacetsOut(BaseModel):
    """前端筛选下拉框的候选值。"""
    sites: List[str] = []
    categories: List[str] = []


class SiteStats(BaseModel):
    site: str
    total: int
    earliest: Optional[str] = None
    latest: Optional[str] = None
