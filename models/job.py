"""ORM 模型层。"""
from sqlalchemy import Column, Integer, String, Text

from db.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fingerprint = Column(String(40), unique=True, index=True, nullable=False,
                         comment="sha1(site:source_id)，去重指纹")
    site = Column(String(32), index=True, nullable=False, comment="爬虫名")
    source_id = Column(String(64), nullable=False, comment="站内 id，含板块前缀")
    title = Column(String(256), nullable=False)
    url = Column(String(512), nullable=False)
    publish_date = Column(String(10), default="", index=True, comment="YYYY-MM-DD")
    category = Column(String(32), default="", comment="站内分类名")
    content = Column(Text, default="", comment="详情正文纯文本")
    content_html = Column(Text, default="", comment="详情正文原始 HTML")
    extra = Column(Text, default="{}", comment="站点特有字段 JSON")
    first_seen = Column(String(19), nullable=False)
    last_seen = Column(String(19), nullable=False)

    def __repr__(self):
        return f"<Job {self.site}:{self.source_id} {self.title[:20]}>"
