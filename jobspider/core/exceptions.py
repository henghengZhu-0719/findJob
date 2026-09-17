"""框架异常。"""


class SpiderError(Exception):
    """爬虫基础异常。"""


class SoftBanError(SpiderError):
    """站点软封：HTTP 200 但返回限流提示 / 兜底页。

    与网络错误区分开——它需要更长的冷却时间，退避基数单独配置。
    """
