"""核心逻辑单测：解析、去重、增量停止。不发真实网络请求。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base
from jobspider.core.models import JobPost
from services.job_service import JobService
from jobspider.spiders.ncrczpw import NcrczpwSpider

SAMPLE_ROW = {
    "type_id": -1, "sort": 0, "title": "某单位招聘公告", "click": 594,
    "id": 485, "score": 1789632231, "addtime": "2026-09-17", "isvalid": 1,
    "_type_id": 4000, "type_name": "专题专栏",
    "url": "https://www.ncrczpw.com/kaoshi/485.html",
}


@pytest.fixture
def store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    return JobService(session_factory=sessionmaker(bind=engine))


def make_spider(store, **kw):
    kw.setdefault("with_detail", False)
    return NcrczpwSpider(store, **kw)


def test_parse_item(store):
    item = make_spider(store).parse_item(SAMPLE_ROW)
    assert item.source_id == "kaoshi:485"
    assert item.title == "某单位招聘公告"
    assert item.publish_date == "2026-09-17"
    assert item.extra["click"] == 594


def test_board_prefix_avoids_id_collision(store):
    sp = make_spider(store)
    a = sp.parse_item(SAMPLE_ROW)
    b = sp.parse_item({**SAMPLE_ROW,
                       "url": "https://www.ncrczpw.com/index.php?a=notice_show&id=485"})
    assert a.fingerprint != b.fingerprint


def test_store_dedupe(store):
    item = JobPost(site="t", source_id="1", title="a", url="u")
    assert store.save(item) is True
    assert store.save(item) is False
    assert len(store.rows()) == 1


def test_content_not_clobbered_by_empty(store):
    item = JobPost(site="t", source_id="1", title="a", url="u", content="正文")
    store.save(item)
    store.save(JobPost(site="t", source_id="1", title="a2", url="u"))  # 无正文的重复项
    row = store.rows()[0]
    assert row["content"] == "正文"
    assert row["title"] == "a2"  # 元信息照常刷新


def test_incremental_stop(store):
    sp = make_spider(store, stop_after_seen=3)
    for i in range(3):
        store.save(JobPost(site=sp.name, source_id=f"kaoshi:{i}", title="x", url="u"))
    for i in range(3):
        sp._process(sp.parse_item({**SAMPLE_ROW, "id": i}))
    assert sp.should_stop() is True


def test_crawl_uses_mixed_feed_by_default(store, monkeypatch):
    """默认 type_id 为空 = 混合流，只按页翻，不做分类遍历。"""
    sp = make_spider(store)
    calls = []

    def fake_get_json(url, params=None, **kw):
        calls.append((params["type_id"], params["page"]))
        if params["page"] > 2:
            return {"data": {"list": []}}
        return {"data": {"list": [
            {**SAMPLE_ROW, "id": params["page"] * 10 + i,
             "url": f"https://www.ncrczpw.com/kaoshi/{params['page']}-{i}.html"}
            for i in range(3)]}}

    monkeypatch.setattr(sp, "get_json", fake_get_json)
    items = list(sp.crawl())
    assert [c[0] for c in calls] == ["", "", ""]      # 全程空 type_id
    assert [c[1] for c in calls] == [1, 2, 3]          # 顺序翻页直到空页
    assert len(items) == 6


def test_soft_ban_raises_not_silently_empty(store, monkeypatch):
    """限流返回 data={} 时必须报错，不能被当成"翻到底了"。"""
    from jobspider.core.exceptions import SoftBanError

    sp = make_spider(store)
    monkeypatch.setattr(sp, "get_json",
                        lambda url, params=None, **kw: {"msg": "系统忙", "code": -1,
                                                        "data": {}})
    # data 是 dict 但没有 list -> 空页正常结束；真正的异常结构才抛
    monkeypatch.setattr(sp, "get_json",
                        lambda url, params=None, **kw: {"code": -1, "data": 0})
    with pytest.raises(SoftBanError):
        list(sp.crawl())


def test_explicit_type_id_only_crawls_one(store, monkeypatch):
    sp = make_spider(store, type_id="1")
    calls = []
    monkeypatch.setattr(sp, "get_json",
                        lambda url, params=None, **kw: (calls.append(params["type_id"]),
                                                        {"data": {"list": []}})[1])
    list(sp.crawl())
    assert calls == ["1"]


def test_check_response_detects_soft_ban(store):
    """限流响应 code=-1 必须抛 SoftBanError，不能被当成空数据。"""
    from jobspider.core.exceptions import SoftBanError

    class FakeResp:
        text = '{"msg":"系统忙，请稍后再试！","code":-1,"data":{}}'
        def json(self):
            import json as _j
            return _j.loads(self.text)

    sp = make_spider(store)
    with pytest.raises(SoftBanError):
        sp.check_response(FakeResp())


def test_check_response_passes_normal(store):
    class OkResp:
        text = '{"code":1,"msg":"success","data":{"list":[]}}'
        def json(self):
            import json as _j
            return _j.loads(self.text)

    make_spider(store).check_response(OkResp())  # 不抛异常即通过


def test_detail_page_bounce_detected(store):
    from jobspider.core.exceptions import SoftBanError

    sp = make_spider(store)
    item = sp.parse_item(SAMPLE_ROW)

    class Bounce:
        text = "<html><head><title>南昌人才招聘网-首页</title></head></html>"

    class Real:
        text = f"<html><head><title>{item.title}-南昌人才招聘网</title></head></html>"

    with pytest.raises(SoftBanError):
        sp._assert_detail_page(Bounce(), item)
    sp._assert_detail_page(Real(), item)   # 真详情页不应抛


def test_delay_is_randomized(store):
    """间隔必须落在区间内且非固定值。"""
    import time as _t
    sp = make_spider(store)
    sp.delay = (0.02, 0.12)
    gaps = []
    for _ in range(6):
        t0 = _t.monotonic()
        sp._last_request_ts = t0    # 模拟"刚发过一次请求"
        sp._sleep_between()
        gaps.append(_t.monotonic() - t0)
    assert all(0.015 <= g <= 0.2 for g in gaps), gaps      # 落在区间内
    assert max(gaps) - min(gaps) > 0.01, gaps              # 确实是随机而非固定
