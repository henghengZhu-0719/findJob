"""BaseSpider：所有站点爬虫的基类。

子类只需要：
  1. 定义 name / site_name / base_url 等类属性；
  2. 实现 crawl() 生成器，逐条 yield JobPost；
  3. （可选）实现 fetch_detail(item) 抓取详情正文。

翻页终止、增量去重、限速、入库、统计都由基类 run() 统一处理。
"""
from __future__ import annotations

import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterator, Optional

from .. import settings
from .exceptions import SoftBanError
from .http import build_session
from .models import JobPost


@dataclass
class CrawlStats:
    new: int = 0
    dup: int = 0
    old: int = 0          # 早于 since 被跳过的
    detail_ok: int = 0
    detail_fail: int = 0
    errors: list = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.new + self.dup


class BaseSpider(ABC):
    # ---- 子类必填 ----
    name: str = ""                 # 唯一英文名，CLI 用它调用
    site_name: str = ""            # 站点中文名
    base_url: str = ""

    # ---- 子类可覆盖的站点级配置 ----
    default_headers: dict = {}     # 追加到会话的请求头
    delay = settings.DEFAULT_DELAY  # float 或 (min, max) 区间，区间内随机取值
    timeout: float = settings.DEFAULT_TIMEOUT

    def __init__(self, store=None, *,
                 max_pages: Optional[int] = None,
                 incremental: bool = True,
                 with_detail: bool = True,
                 stop_after_seen: int = 20,
                 max_age_days: Optional[int] = settings.MAX_AGE_DAYS):
        """
        max_pages       : 最多翻多少页（None = 不限，直到列表为空）
        incremental     : True 时连续遇到 stop_after_seen 条已入库数据就提前停
        with_detail     : 是否抓详情正文
        stop_after_seen : 增量模式的“连续已见”阈值，通常设为一页的条数
        max_age_days    : 只采最近 N 天发布的（0/None = 不限）；与增量模式无关，--full 也受它约束
        """
        if store is None:
            from services.job_service import JobService  # 延迟 import 防循环依赖
            store = JobService()
        self.store = store
        self.max_pages = max_pages
        self.incremental = incremental
        self.with_detail = with_detail
        self.stop_after_seen = stop_after_seen
        # YYYY-MM-DD，与 publish_date 直接按字符串比较；空串 = 不限
        self.since = ((date.today() - timedelta(days=max_age_days)).isoformat()
                      if max_age_days else "")
        self.session = build_session(self.default_headers)
        self.log = logging.getLogger(self.name or self.__class__.__name__)
        self.stats = CrawlStats()
        self._seen_streak = 0
        self._last_request_ts = 0.0

    # ================= 子类接口 =================
    @abstractmethod
    def crawl(self) -> Iterator[JobPost]:
        """逐条产出列表页解析出的 JobPost。每页末尾应检查 self.should_stop(本页 items)。"""

    def fetch_detail(self, item: JobPost) -> None:
        """抓取并填充 item.content / item.content_html。默认不抓，子类按需实现。"""

    # ================= 框架逻辑 =================
    def run(self) -> CrawlStats:
        self.log.info("开始采集 %s (%s)  incremental=%s max_pages=%s since=%s",
                      self.site_name, self.name, self.incremental, self.max_pages,
                      self.since or "不限")
        try:
            # 停止时机由 crawl() 的翻页循环通过 should_stop() 自行决定，
            # 这样多分组（如多分类/多城市）的爬虫可以分组重置计数
            for item in self.crawl():
                self._process(item)
        except KeyboardInterrupt:
            self.log.warning("手动中断，已入库数据保留")
        except SoftBanError as e:
            # 冷却后仍被封，停止而不是继续骚扰站点
            self.stats.errors.append(str(e))
            self.log.error("多次冷却后仍被限流，停止采集：%s", e)
        s = self.stats
        self.log.info("完成：新增 %d，已存在 %d，过旧跳过 %d，详情成功 %d，详情失败 %d",
                      s.new, s.dup, s.old, s.detail_ok, s.detail_fail)
        return s

    def is_too_old(self, item: JobPost) -> bool:
        """发布日期早于 since。日期缺失的不算旧（宁可多采）。"""
        return bool(self.since and item.publish_date
                    and item.publish_date[:10] < self.since)

    def _process(self, item: JobPost) -> None:
        if self.is_too_old(item):
            # 不抓详情、不入库、不计入连续已见
            self.stats.old += 1
            return
        is_known = self.store.has(item.fingerprint)
        if is_known:
            self._seen_streak += 1
        else:
            self._seen_streak = 0
            if self.with_detail:
                try:
                    self.fetch_detail(item)
                    if item.content:
                        self.stats.detail_ok += 1
                except Exception as e:  # 单条详情失败不影响整体
                    self.stats.detail_fail += 1
                    self.stats.errors.append(f"{item.url}: {e}")
                    self.log.warning("详情抓取失败 %s: %s", item.url, e)
        if self.store.save(item):
            self.stats.new += 1
            self.log.info("新增 [%s] %s", item.publish_date, item.title)
        else:
            self.stats.dup += 1

    def should_stop(self, page: Optional[list] = None) -> bool:
        """翻页循环每页末尾调用。传入本页 JobPost 列表时，整页都早于 since 也停。

        只看整页而不是碰到第一条旧的就停：列表并非严格按日期排序
        （如 ncrczpw 专题专栏更新后发布日期会被刷新、顶到前面）。
        """
        if self.incremental and self._seen_streak >= self.stop_after_seen:
            self.log.info("连续 %d 条已入库，增量结束", self.stop_after_seen)
            return True
        if page and all(self.is_too_old(it) for it in page):
            self.log.info("整页均早于 %s，结束", self.since)
            return True
        return False

    def reset_seen_streak(self) -> None:
        """分组抓取（多分类/多板块）切组时调用，使增量停止只作用于当前组。"""
        self._seen_streak = 0

    # ================= HTTP 助手 =================
    def _sleep_between(self) -> None:
        """两次请求之间的随机间隔（区间内均匀取值，避免固定节奏）。"""
        d = self.delay
        lo, hi = d if isinstance(d, (tuple, list)) else (d, d)
        gap = random.uniform(lo, hi) - (time.monotonic() - self._last_request_ts)
        if gap > 0:
            time.sleep(gap)

    def check_response(self, resp) -> None:
        """子类钩子：识别 HTTP 200 的软封响应，命中则 raise SoftBanError。"""

    def request(self, url: str, *, method: str = "GET", validate=None, **kw):
        """带随机限速、超时、重试的请求。

        validate: 可选回调，收到响应后调用，可 raise SoftBanError 触发长冷却重试。
        """
        kw.setdefault("timeout", self.timeout)
        soft_bans = 0
        attempt = 0
        last_exc: Exception = RuntimeError("unreachable")
        while True:
            self._sleep_between()
            try:
                resp = self.session.request(method, url, **kw)
                self._last_request_ts = time.monotonic()
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise IOError(f"HTTP {resp.status_code}")
                resp.raise_for_status()
                self.check_response(resp)
                if validate is not None:
                    validate(resp)
                return resp
            except SoftBanError as e:
                self._last_request_ts = time.monotonic()
                last_exc = e
                if soft_bans >= settings.SOFT_BAN_RETRIES:
                    raise
                cooldown = settings.SOFT_BAN_BACKOFF * (2 ** soft_bans)
                soft_bans += 1
                self.log.warning("被限流(%s)，冷却 %.0fs 后重试（第 %d 次）",
                                 e, cooldown, soft_bans)
                time.sleep(cooldown)
            except Exception as e:
                self._last_request_ts = time.monotonic()
                last_exc = e
                if attempt >= settings.DEFAULT_RETRIES:
                    raise last_exc
                backoff = settings.RETRY_BACKOFF * (2 ** attempt)
                attempt += 1
                self.log.warning("请求失败(%s)，%.0fs 后重试 %s", e, backoff, url)
                time.sleep(backoff)

    def get_json(self, url: str, **kw) -> dict:
        return self.request(url, **kw).json()

    def get_html(self, url: str, **kw) -> str:
        return self.request(url, **kw).text
