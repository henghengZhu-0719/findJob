"""全局配置。站点级配置放在各 Spider 类属性里，这里只放框架级默认值。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "jobs.db"

# HTTP 默认值（可被 Spider 类属性覆盖）
DEFAULT_TIMEOUT = 20.0        # 秒
DEFAULT_DELAY = (1.5, 4.0)    # 请求间隔随机区间（秒），避免固定节奏被识别
DEFAULT_RETRIES = 3
RETRY_BACKOFF = 2.0           # 网络错误退避基数（秒），按 2^n 递增

# 软封（HTTP 200 但返回限流提示）后的冷却：60s / 120s / 240s ...
SOFT_BAN_BACKOFF = 60.0
SOFT_BAN_RETRIES = 3

# 只采最近 N 天发布的公告（按 publish_date），0 = 不限。
# 增量停止靠“连续 N 条已入库”，首次运行或库里数据稀疏时永远凑不满，
# 没有这道下限就会一路翻到站点最早的历史。环境变量 JOBSPIDER_MAX_AGE_DAYS 覆盖
MAX_AGE_DAYS = int(os.environ.get("JOBSPIDER_MAX_AGE_DAYS", "30"))

# curl_cffi 浏览器指纹（TLS/JA3 + 对应 UA），"chrome" = 最新版 Chrome
IMPERSONATE = "chrome"

# 本机 http(s)_proxy 指向的代理不可用，默认忽略环境变量代理、直连
TRUST_ENV_PROXY = False

LOG_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"

# 定时采集（FastAPI 进程内后台线程）：每天本地时间几点跑，逗号分隔可配多个，
# 如 "08:00,20:30"。环境变量 JOBSPIDER_CRAWL_AT 覆盖，设为空串则关闭
CRAWL_AT = os.environ.get("JOBSPIDER_CRAWL_AT", "08:00")
