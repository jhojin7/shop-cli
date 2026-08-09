from __future__ import annotations

from shop.models import Product


class EmartProvider:
    """SSG / Emart mall search via Playwright (no public API)."""

    name = "emart"

    def search(self, query: str, *, limit: int = 10) -> list[Product]:
        try:
            from shop.browser import search_emart_with_playwright
        except ImportError:
            return []
        return search_emart_with_playwright(query, limit=limit)

    def fetch_price(self, product: Product) -> int | None:
        results = self.search(product.title, limit=20)
        for r in results:
            if product.product_id and r.product_id == product.product_id:
                return r.price
            if r.url == product.url:
                return r.price
        return None
