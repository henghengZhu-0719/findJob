"""定时采集：FastAPI 进程内的后台线程，每天固定时刻依次跑所有已注册爬虫。

时刻取 settings.CRAWL_AT（本地时间），空串则不启动线程。
只在服务运行期间生效：到点时服务没开着就错过当次，不补跑。
uvicorn --workers N 会每个 worker 各起一个线程重复采集，须保持单 worker。
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, time, timedelta
from typing import List, Optional

from jobspider import settings
from jobspider.core.registry import all_spiders
from services.job_service import JobService

log = logging.getLogger("scheduler")

# 分段等待并比对墙钟，而不是一次 wait 到点：
# macOS 休眠期间单调时钟不走，一次长 wait 会被休眠时长整体推迟
_POLL_SECONDS = 60.0


def parse_times(spec: str) -> List[time]:
    """"08:00,20:30" -> [08:00, 20:30]（排序去重）；空串返回 []，格式错误抛 ValueError。"""
    out = {datetime.strptime(p.strip(), "%H:%M").time()
           for p in spec.split(",") if p.strip()}
    return sorted(out)


def next_run(times: List[time], now: datetime) -> datetime:
    """now 之后（严格大于）最近的一个触发时刻。"""
    for t in times:
        at = datetime.combine(now.date(), t)
        if at > now:
            return at
    return datetime.combine(now.date() + timedelta(days=1), times[0])


def _fmt(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat(timespec="seconds") if dt else None


class CrawlScheduler:
    def __init__(self, spec: Optional[str] = None):
        self.times = parse_times(settings.CRAWL_AT if spec is None else spec)
        self.next_at: Optional[datetime] = None
        self.last_started: Optional[datetime] = None
        self.last_finished: Optional[datetime] = None
        self.last_result: dict = {}
        self._stop = threading.Event()
        # 定时与手动触发互斥，同一时刻只跑一轮；持锁即“正在采集”
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._lock.locked()

    # ================= 生命周期 =================
    def start(self) -> None:
        if not self.times:
            log.info("CRAWL_AT 为空，定时采集关闭")
            return
        threading.Thread(target=self._loop, name="crawl-scheduler", daemon=True).start()

    def stop(self) -> None:
        """通知线程退出。正在跑的爬虫不会被打断，守护线程随进程结束；已入库数据逐条提交不丢。"""
        self._stop.set()

    def _loop(self) -> None:
        self.next_at = next_run(self.times, datetime.now())
        log.info("定时采集已启动，下次 %s", _fmt(self.next_at))
        while not self._stop.is_set():
            remaining = (self.next_at - datetime.now()).total_seconds()
            if remaining > 0:
                self._stop.wait(min(remaining, _POLL_SECONDS))
                continue
            if self._lock.acquire(blocking=False):
                self._run_locked()
            else:
                log.warning("手动触发的采集尚未结束，跳过本次定时")
            self.next_at = next_run(self.times, datetime.now())
            log.info("下次定时采集 %s", _fmt(self.next_at))

    # ================= 采集 =================
    def trigger(self) -> bool:
        """手动触发一轮，后台执行不阻塞调用方。已有一轮在跑返回 False。"""
        if not self._lock.acquire(blocking=False):
            return False
        threading.Thread(target=self._run_locked, name="crawl-manual", daemon=True).start()
        return True

    def _run_locked(self) -> None:
        """调用方已持锁，跑完释放。每个站点增量 + 抓详情，与 CLI `crawl <name>` 默认参数一致。"""
        try:
            self.last_started = datetime.now()
            result = {}
            for name, cls in sorted(all_spiders().items()):
                if self._stop.is_set():
                    break
                store = JobService()
                try:
                    s = cls(store).run()
                    result[name] = {"new": s.new, "dup": s.dup, "old": s.old,
                                    "detail_fail": s.detail_fail, "errors": s.errors[-5:]}
                except Exception as e:  # 单站点崩溃不影响其他站点和调度线程
                    log.exception("采集 %s 异常", name)
                    result[name] = {"errors": [str(e)]}
                finally:
                    store.close()
            self.last_result = result
            self.last_finished = datetime.now()
        finally:
            self._lock.release()

    def status(self) -> dict:
        return {
            "schedule": [t.strftime("%H:%M") for t in self.times],
            "running": self.running,
            "next_at": _fmt(self.next_at),
            "last_started": _fmt(self.last_started),
            "last_finished": _fmt(self.last_finished),
            "last_result": self.last_result,
        }
