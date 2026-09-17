"""HTTP 会话构建（curl_cffi）：模拟 Chrome TLS 指纹，绕过 JA3 反爬。"""
from __future__ import annotations

import os

from curl_cffi import requests as creq

from .. import settings


def _scrub_proxy_env():
    """本机环境变量里的代理不可用，libcurl 会读它们导致超时，进程内清掉直连。"""
    if settings.TRUST_ENV_PROXY:
        return
    for k in ("http_proxy", "https_proxy", "all_proxy",
              "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        os.environ.pop(k, None)


def build_session(headers: dict | None = None) -> creq.Session:
    _scrub_proxy_env()
    # impersonate 会带上与指纹匹配的 UA/加密套件，不要再自定义 User-Agent
    s = creq.Session(impersonate=settings.IMPERSONATE)
    if headers:
        s.headers.update(headers)
    return s
