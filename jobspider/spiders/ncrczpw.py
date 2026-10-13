"""南昌人才招聘网 (www.ncrczpw.com) 公告采集。

列表接口: /index.php?m=&c=notice&a=notice_list&count=20&page=N&type_id=T
  - 无需 Cookie / 登录；
  - type_id 留空返回全部分类的混合流（默认用法）；data.total 此时是假值
    （恒等于 count*100），故翻页终止以 list 为空为准，不看 total；
  - 限流时 HTTP 仍是 200，返回 {"code":-1,"msg":"系统忙，请稍后再试！"}。

详情页两种形态，均为服务端渲染：
  - /kaoshi/<id>.html                （专题专栏，正文在 div.content）
  - index.php?...a=notice_show&id=N  （普通公告，正文在 div.mce-content-body）
  限流时任意详情 URL 都 200 返回首页，靠 <title> 校验识别。
"""
from __future__ import annotations

import re
from typing import Iterator

from bs4 import BeautifulSoup

from ..core import BaseSpider, JobPost, register
from ..core.exceptions import SoftBanError


@register
class NcrczpwSpider(BaseSpider):
    name = "ncrczpw"
    site_name = "南昌人才招聘网"
    base_url = "https://www.ncrczpw.com"
    delay = (2.0, 5.0)   # 该站限流较严，间隔放宽
    default_headers = {
        "Referer": "https://www.ncrczpw.com/index.php?m=home&c=notice&a=special",
        "X-Requested-With": "XMLHttpRequest",
    }

    PAGE_SIZE = 20

    def __init__(self, *args, type_id: str = "", **kwargs):
        kwargs.setdefault("stop_after_seen", self.PAGE_SIZE)
        super().__init__(*args, **kwargs)
        self.type_id = type_id

    # ---------- 反爬识别 ----------
    def check_response(self, resp) -> None:
        """限流时接口返回 {"code":-1,"msg":"系统忙，请稍后再试！"}，HTTP 仍是 200。"""
        body = resp.text.lstrip()
        if not body.startswith("{"):
            return
        try:
            data = resp.json()
        except ValueError:
            return
        if data.get("code") != 1:
            raise SoftBanError(f"接口拒绝：code={data.get('code')} msg={data.get('msg')}")

    def _assert_detail_page(self, resp, item: JobPost) -> None:
        """详情页被限流时会 200 返回首页，用 <title> 是否含公告标题识别。"""
        m = re.search(r"<title>(.*?)</title>", resp.text, re.S)
        page_title = (m.group(1) if m else "").strip()
        key = item.title[:6]
        if key and key not in page_title:
            raise SoftBanError(f"非详情页（title={page_title[:24]!r}），疑似被限流")

    # ---------- 列表 ----------
    def crawl(self) -> Iterator[JobPost]:
        """type_id 默认空串 = 全部分类的混合流，每天跑一次即可覆盖新增。"""
        page = 1
        while True:
            data = self.get_json(
                f"{self.base_url}/index.php",
                params={"m": "", "c": "notice", "a": "notice_list",
                        "count": self.PAGE_SIZE, "page": page,
                        "type_id": self.type_id})
            payload = data.get("data")
            if not isinstance(payload, dict):
                raise SoftBanError(f"列表接口返回异常结构: {str(payload)[:60]}")
            rows = payload.get("list") or []
            self.log.info("第 %d 页：%d 条", page, len(rows))
            if not rows:
                break
            items = [self.parse_item(r) for r in rows]
            yield from items
            if self.should_stop(items):
                break
            if self.max_pages and page >= self.max_pages:
                break
            page += 1

    def parse_item(self, r: dict) -> JobPost:
        url = r.get("url", "")
        if url.startswith("/"):
            url = self.base_url + url
        # 两个板块 id 各自独立自增会撞号，source_id 带板块前缀区分
        board = "kaoshi" if "/kaoshi/" in url else "notice"
        return JobPost(
            site=self.name,
            source_id=f"{board}:{r['id']}",
            title=r.get("title", "").strip(),
            url=url,
            publish_date=r.get("addtime", ""),
            category=r.get("type_name", ""),
            extra={"click": r.get("click"), "type_id": r.get("type_id"),
                   "_type_id": r.get("_type_id")},
        )

    # ---------- 详情 ----------
    def fetch_detail(self, item: JobPost) -> None:
        html = self.get_html(item.url,
                             validate=lambda r: self._assert_detail_page(r, item))
        soup = BeautifulSoup(html, "lxml")
        node = soup.select_one("div.mce-content-body") or soup.select_one("div.content")
        if node is None:
            return
        item.content_html = str(node)
        item.content = node.get_text("\n", strip=True)
