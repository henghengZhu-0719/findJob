"""统一的数据模型（Item）。所有站点的公告都归一化成 JobPost 入库。"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field


@dataclass
class JobPost:
    """一条招聘公告。

    site       : 爬虫名（Spider.name）
    source_id  : 站内唯一 id（同站不同板块可能撞 id，建议带板块前缀，如 "kaoshi:485"）
    title      : 标题
    url        : 详情页绝对地址
    publish_date : 发布日期 YYYY-MM-DD（尽量归一化）
    category   : 站内分类名
    content    : 详情正文纯文本（可选，需 fetch_detail）
    content_html : 详情正文原始 HTML（可选）
    extra      : 站点特有字段，原样存 JSON
    """

    site: str
    source_id: str
    title: str
    url: str
    publish_date: str = ""
    category: str = ""
    content: str = ""
    content_html: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        """去重指纹：站点 + 站内 id。"""
        return hashlib.sha1(f"{self.site}:{self.source_id}".encode()).hexdigest()

    def to_row(self) -> dict:
        d = asdict(self)
        d["extra"] = json.dumps(self.extra, ensure_ascii=False)
        d["fingerprint"] = self.fingerprint
        return d
