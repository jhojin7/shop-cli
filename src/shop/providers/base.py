from __future__ import annotations

from typing import Protocol, runtime_checkable

from shop.models import Product, Source


@runtime_checkable
class ShoppingProvider(Protocol):
    """Search + optional price refresh for one shopping source."""

    name: Source

    def search(self, query: str, *, limit: int = 10) -> list[Product]:
        """Return normalized product candidates for a query."""
        ...

    def fetch_price(self, product: Product) -> int | None:
        """Refresh current price for a known product. Return KRW or None."""
        ...
