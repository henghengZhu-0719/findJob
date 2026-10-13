# jobspider — 招聘公告采集框架

`BaseSpider` 基类 + 站点插件式爬虫。每个站点一个模块，注册后由统一 CLI 调度；
数据归一化为 `JobPost` 存 SQLite（按指纹增量去重），可导出 CSV / JSONL。

## 结构

```
jobspider/
├── settings.py          # 框架级配置（路径、超时、限速、指纹）
├── cli.py               # 命令行入口
├── core/
│   ├── models.py        # JobPost 数据模型（Item）
│   ├── http.py          # curl_cffi 会话：Chrome TLS 指纹、直连
│   ├── base.py          # BaseSpider：限速/重试/增量停止/入库/统计
│   ├── pipeline.py      # SQLiteStore：去重入库、导出、正文回填
│   └── registry.py      # @register 爬虫注册表
└── spiders/
    └── ncrczpw.py       # 南昌人才招聘网
```

## 使用

注释写在命令上一行 —— zsh 交互模式默认不认行尾的 `#`，跟在命令后面会被当成参数。

### 启动服务（API + 前端 + 定时采集）

```bash
# 一键启动：同步依赖、前端有改动自动重新构建，然后起服务
./start.sh

# 开发模式：后端 --reload + 前端 vite 热更新，页面走 http://127.0.0.1:5173
./start.sh dev

# 换端口
PORT=9000 ./start.sh
```

手动等价于：`uv sync` → `cd frontend && npm install && npm run build` → `uv run python -m uvicorn main:app`。

- 页面：http://127.0.0.1:8000
- 接口文档：http://127.0.0.1:8000/docs

### 定时采集

服务启动后有一个后台线程，每天按本地时间定点把所有已注册爬虫增量跑一轮（等同 `crawl <name>` 默认参数）。
时刻在 `jobspider/settings.py` 的 `CRAWL_AT`，默认 `08:00`，也可用环境变量覆盖：

```bash
# 每天 9:30 和 21:00 各跑一次
JOBSPIDER_CRAWL_AT="09:30,21:00" uv run python -m uvicorn main:app

# 关闭定时
JOBSPIDER_CRAWL_AT="" uv run python -m uvicorn main:app

# 查看下次触发时间、上一轮结果
curl http://127.0.0.1:8000/api/crawl/status

# 不等定时，立即后台跑一轮（已在跑时返回 409）
curl -X POST http://127.0.0.1:8000/api/crawl/run
```

- 只在服务运行期间生效，到点时服务没开就错过当次，不补跑。
- `--reload` 下改代码会重启进程，正在跑的采集随之中断（已入库的不丢）。
- 保持单 worker；`--workers N` 会每个进程各跑一份。

### 采集

```bash
# 列出可用爬虫
uv run python -m jobspider list

# 增量抓取（日常用这个）：连续 20 条已入库、或整页早于 30 天前，先到先停
uv run python -m jobspider crawl ncrczpw

# 只抓 2 页，含详情正文
uv run python -m jobspider crawl ncrczpw --pages 2

# 回溯 90 天
uv run python -m jobspider crawl ncrczpw --days 90

# 真·全量：不因已入库停、不限日期，只抓列表不抓正文
uv run python -m jobspider crawl ncrczpw --full --days 0 --no-detail

# 补抓 content 为空的记录
uv run python -m jobspider backfill

# 入库统计
uv run python -m jobspider stats

# 导出 data/all.csv
uv run python -m jobspider export --fmt csv

# 导出指定站点为 jsonl
uv run python -m jobspider export --site ncrczpw --fmt jsonl -o data/nc.jsonl
```

数据落在 `data/jobs.db`（SQLite，表 `jobs`，`fingerprint` = sha1(site:source_id) 唯一去重）。

### 前端开发

```bash
cd frontend
npm install
npm run dev
```

开发服务器在 5173 端口，`/api` 自动代理到 8000。改完构建：

```bash
npm run build
```

产物输出到 `../static/`，由 FastAPI 直接托管。

## 架构

五层（FastAPI 惯例），爬虫的存储管道复用 service 层：

```
db/database.py     engine / SessionLocal / Base / get_db
models/job.py      ORM 模型
repos/job_repo.py  数据访问，只做 CRUD，不提交事务
services/          业务逻辑 + 事务边界；同时是爬虫的 store
schemas/job.py     Pydantic 出入参
routes/job_route.py 路由
main.py            应用入口，兼托管前端
```

Session 的开法分两种场景：API 请求由 `get_db()` 按请求开关、注入给 service；爬虫和 CLI 没有请求生命周期，由 service 自持一个长会话。

## 新增一个站点

在 `jobspider/spiders/` 下建模块，三步：

```python
from ..core import BaseSpider, JobPost, register

@register
class XxxSpider(BaseSpider):
    name = "xxx"                 # CLI 用的唯一名
    site_name = "某某人才网"
    base_url = "https://..."
    delay = 1.0                  # 站点级限速

    def crawl(self):             # 必须实现：翻页并逐条 yield JobPost
        page = 1
        while True:
            rows = self.get_json(...)["data"]["list"]
            if not rows:
                break
            items = [JobPost(site=self.name, source_id=str(r["id"]),
                             title=r["title"], url=r["url"],
                             publish_date=r["date"], extra=r) for r in rows]
            yield from items
            # 传本页 items：整页早于日期下限也会停（过旧条目基类已自动跳过）
            if self.should_stop(items) or (self.max_pages and page >= self.max_pages):
                break
            page += 1

    def fetch_detail(self, item):  # 可选：填充 item.content / content_html
        ...
```

保存即生效（registry 自动发现），`uv run python -m jobspider crawl xxx` 即可跑。

## 已踩过的坑（ncrczpw）

- 列表接口 `data.total` 恒等于 `count*100`，不可信；翻页终止以 `list` 为空为准。
- `kaoshi` 与 `notice` 两板块 id 独立自增会撞号，source_id 带板块前缀。
- 专题专栏（kaoshi）更新后 `addtime` 会被刷新、整条顶到列表前面，所以列表只是大致按日期倒序；
  日期下限按“整页都过旧”才停，不在碰到第一条旧的时就停。
- 只靠“连续 N 条已入库”停止不可靠：首次运行、或库里只有零散旧数据（比如之前只抓过 2 页）时永远凑不满，
  会一路翻到站点最早的历史，故有 `MAX_AGE_DAYS`（默认 30 天）兜底。
- 站点有 TLS 指纹反爬：普通 requests/curl 会被 200 兜底回首页，须用 curl_cffi
  模拟 Chrome 指纹；高频访问后仍可能被临时软封（任意 URL 都返回首页），
  `fetch_detail` 里用页面 `<title>` 校验识别，等冷却后 `backfill` 补正文。
- 本机 `https_proxy` 环境变量指向的代理不可用，`http.py` 会在进程内清掉直连。
