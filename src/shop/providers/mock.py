from __future__ import annotations

"""Deterministic mock provider for offline / sandbox tests."""

from shop.models import Product, Source


class MockProvider:
    name: Source = "naver"

    def __init__(self, source: Source = "naver") -> None:
        self.name = source

    def search(self, query: str, *, limit: int = 10) -> list[Product]:
        base_price = 1000 + (sum(ord(c) for c in query) % 9000)
        items = []
        for i in range(min(limit, 3)):
            items.append(
                Product(
                    source=self.name,
                    title=f"{query} 테스트상품 {i + 1}",
                    price=base_price + i * 100,
                    url=f"https://example.com/{self.name}/{hash(query) % 100000}/{i}",
                    mall_name=f"{self.name}-mock-mall",
                    product_id=f"mock-{self.name}-{hash(query) % 100000}-{i}",
                )
            )
        return items

    def fetch_price(self, product: Product) -> int | None:
        return product.price
