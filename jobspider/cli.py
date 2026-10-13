"""命令行入口。

  uv run python -m jobspider list
  uv run python -m jobspider crawl ncrczpw --pages 3
  uv run python -m jobspider crawl ncrczpw --full --no-detail
  uv run python -m jobspider export --site ncrczpw --fmt csv -o data/ncrczpw.csv
  uv run python -m jobspider stats
"""
from __future__ import annotations

import argparse
import logging
import sys

from . import settings
from .core.registry import all_spiders, get_spider
from services.job_service import JobService


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format=settings.LOG_FORMAT)
    p = argparse.ArgumentParser(prog="jobspider", description="招聘公告采集框架")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="列出已注册的爬虫")

    pc = sub.add_parser("crawl", help="运行指定爬虫")
    pc.add_argument("name", help="爬虫名（见 list）")
    pc.add_argument("--pages", type=int, default=None, help="最多翻页数")
    pc.add_argument("--full", action="store_true",
                    help="全量模式：不因连续已见数据提前停止（仍受 --days 约束）")
    pc.add_argument("--days", type=int, default=None,
                    help=f"只采最近 N 天发布的，默认 {settings.MAX_AGE_DAYS}，0 = 不限")
    pc.add_argument("--no-detail", action="store_true", help="不抓详情正文")
    pc.add_argument("--type-id", default="", help="站点分类参数（站点自定义）")

    pe = sub.add_parser("export", help="导出数据")
    pe.add_argument("--site", default=None, help="只导出某站点")
    pe.add_argument("--fmt", choices=["csv", "jsonl"], default="csv")
    pe.add_argument("-o", "--output", default=None)

    pb = sub.add_parser("backfill", help="补抓缺失的详情正文")
    pb.add_argument("--site", default=None, help="只处理某站点")

    sub.add_parser("stats", help="入库统计")

    args = p.parse_args(argv)

    if args.cmd == "list":
        for name, cls in sorted(all_spiders().items()):
            print(f"  {name:<16} {cls.site_name:<12} {cls.base_url}")
        return 0

    if args.cmd == "crawl":
        cls = get_spider(args.name)
        kwargs = dict(max_pages=args.pages,
                      incremental=not args.full,
                      with_detail=not args.no_detail)
        if args.type_id:
            kwargs["type_id"] = args.type_id
        if args.days is not None:
            kwargs["max_age_days"] = args.days
        spider = cls(**kwargs)
        stats = spider.run()
        return 0 if not stats.errors else 1

    store = JobService()
    if args.cmd == "export":
        site = args.site
        out = args.output or str(
            settings.DATA_DIR / f"{site or 'all'}.{args.fmt}")
        n = store.export(out, fmt=args.fmt, site=site)
        print(f"已导出 {n} 条 -> {out}")
        return 0

    if args.cmd == "backfill":
        from .core.models import JobPost
        rows = store.rows_missing_content(args.site)
        print(f"待补抓 {len(rows)} 条")
        spiders_cache = {}
        ok = fail = 0
        for r in rows:
            if r["site"] not in spiders_cache:
                spiders_cache[r["site"]] = get_spider(r["site"])(store)
            sp = spiders_cache[r["site"]]
            item = JobPost(site=r["site"], source_id=r["source_id"],
                           title=r["title"], url=r["url"])
            try:
                sp.fetch_detail(item)
            except Exception as e:
                fail += 1
                print(f"  失败 {r['title'][:24]}: {e}")
                continue
            if item.content:
                store.set_content(r["fingerprint"], item.content, item.content_html)
                ok += 1
            else:
                fail += 1
        print(f"补抓完成：成功 {ok}，失败 {fail}")
        return 0 if fail == 0 else 1

    if args.cmd == "stats":
        rows = store.stats()
        if not rows:
            print("库中暂无数据")
        for r in rows:
            print(f"  {r['site']:<16} {r['total']:>6} 条   "
                  f"{r['earliest']} ~ {r['latest']}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
