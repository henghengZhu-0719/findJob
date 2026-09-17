"""爬虫注册表：@register 装饰的 Spider 自动可被 CLI 按名调用。"""
from __future__ import annotations

_REGISTRY: dict = {}


def register(cls):
    """类装饰器。要求类定义了唯一的 name。"""
    name = getattr(cls, "name", "")
    if not name:
        raise ValueError(f"{cls.__name__} 缺少 name 属性")
    if name in _REGISTRY:
        raise ValueError(f"爬虫名重复: {name}")
    _REGISTRY[name] = cls
    return cls


def get_spider(name: str):
    _load_spiders()
    if name not in _REGISTRY:
        raise KeyError(f"未找到爬虫 {name!r}，可用: {', '.join(sorted(_REGISTRY))}")
    return _REGISTRY[name]


def all_spiders() -> dict:
    _load_spiders()
    return dict(_REGISTRY)


def _load_spiders():
    """导入 spiders 包内所有模块，触发 @register。"""
    import importlib
    import pkgutil

    from .. import spiders

    for m in pkgutil.iter_modules(spiders.__path__):
        importlib.import_module(f"{spiders.__name__}.{m.name}")
