"""定时采集单测：时刻解析、下次触发计算、互斥。不起线程跑真实爬虫。"""
from datetime import datetime, time

import pytest

from services.crawl_scheduler import CrawlScheduler, next_run, parse_times


def test_parse_times_sorted_and_deduped():
    assert parse_times(" 20:30,08:00,08:00 ") == [time(8, 0), time(20, 30)]


def test_parse_times_empty_disables():
    assert parse_times("") == []
    assert CrawlScheduler("").times == []


def test_parse_times_rejects_bad_format():
    with pytest.raises(ValueError):
        parse_times("8点")


@pytest.mark.parametrize("now, expected", [
    ("2026-10-13 07:00:00", "2026-10-13 08:00:00"),  # 当天第一个之前
    ("2026-10-13 08:00:00", "2026-10-13 20:30:00"),  # 恰好到点：已触发，取下一个
    ("2026-10-13 12:00:00", "2026-10-13 20:30:00"),  # 两个时刻之间
    ("2026-10-13 23:00:00", "2026-10-14 08:00:00"),  # 当天都过了，顺延次日
])
def test_next_run(now, expected):
    times = [time(8, 0), time(20, 30)]
    assert next_run(times, datetime.fromisoformat(now)) == datetime.fromisoformat(expected)


def test_trigger_refused_while_running():
    sch = CrawlScheduler("08:00")
    sch._lock.acquire()          # 模拟正在采集
    try:
        assert sch.running is True
        assert sch.trigger() is False
    finally:
        sch._lock.release()
    assert sch.status()["schedule"] == ["08:00"]
