from __future__ import annotations

import os

from shop.models import Source
from shop.providers.base import ShoppingProvider
from shop.providers.emart import EmartProvider
from shop.providers.naver import NaverProvider


def get_provider(source: Source) -> ShoppingProvider:
    # SHOP_MOCK=1 → offline deterministic results (sandbox / CI)
    if os.environ.get("SHOP_MOCK") == "1":
        from shop.providers.mock import MockProvider

        return MockProvider(source=source)

    if source == "naver":
        return NaverProvider()
    if source == "emart":
        return EmartProvider()
    raise ValueError(f"unknown source: {source}")


__all__ = ["ShoppingProvider", "NaverProvider", "EmartProvider", "get_provider"]
