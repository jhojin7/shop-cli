from __future__ import annotations

import re
from urllib.parse import quote

import httpx

from shop.models import Product


class NaverBlockedError(RuntimeError):
    """Raised when Naver returns bot-block (418) or empty protected responses."""


class NaverProvider:
    """Naver Shopping search.

    Strategy order:
    1. Public BFF JSON (k-skill style)
    2. search.shopping internal API
    3. Playwright page render + optional response intercept
    """

    name = "naver"
    BFF_URL = "https://ns-portal.shopping.naver.com/api/v2/shopping-paged-slot"
    SEARCH_API = "https://search.shopping.naver.com/api/search/all"

    def search(self, query: str, *, limit: int = 10) -> list[Product]:
        for fn in (self._search_bff, self._search_api):
            try:
                products = fn(query, limit=limit)
                if products:
                    return products
            except NaverBlockedError:
                continue
            except Exception:
                continue

        # Playwright last
        try:
            return self._search_playwright(query, limit=limit)
        except Exception:
            return []

    def fetch_price(self, product: Product) -> int | None:
        results = self.search(product.title, limit=20)
        for r in results:
            if product.product_id and r.product_id == product.product_id:
                return r.price
            if r.url == product.url:
                return r.price
        return None

    def _headers(self, query: str) -> dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": f"https://search.shopping.naver.com/search/all?query={quote(query)}",
        }

    def _search_bff(self, query: str, *, limit: int) -> list[Product]:
        params = {"query": query, "source": "shp_gui"}
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(self.BFF_URL, params=params, headers=self._headers(query))
            if resp.status_code == 418:
                raise NaverBlockedError("BFF 418")
            resp.raise_for_status()
            data = resp.json()
        products = self._parse_bff(data, limit=limit)
        return products

    def _search_api(self, query: str, *, limit: int) -> list[Product]:
        params = {
            "sort": "rel",
            "pagingIndex": 1,
            "pagingSize": min(limit, 40),
            "viewType": "list",
            "productSet": "total",
            "query": query,
        }
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(self.SEARCH_API, params=params, headers=self._headers(query))
            if resp.status_code == 418:
                raise NaverBlockedError("search API 418")
            if "text/html" in resp.headers.get("content-type", ""):
                raise NaverBlockedError("search API returned HTML block page")
            resp.raise_for_status()
            data = resp.json()
        return self._parse_search_api(data, limit=limit)

    def _parse_search_api(self, data: dict, *, limit: int) -> list[Product]:
        products: list[Product] = []
        # Common shapes: shoppingResult.products / data.products / products
        candidates = (
            data.get("shoppingResult", {}).get("products")
            or data.get("data", {}).get("products")
            or data.get("products")
            or []
        )
        if not isinstance(candidates, list):
            candidates = self._extract_cards(data)

        for card in candidates:
            if len(products) >= limit:
                break
            if not isinstance(card, dict):
                continue
            title = _strip_html(
                str(
                    card.get("productTitle")
                    or card.get("productName")
                    or card.get("title")
                    or card.get("name")
                    or ""
                )
            ).strip()
            if not title:
                continue
            price = _to_int(
                card.get("price")
                or card.get("lowPrice")
                or card.get("mobileLowPrice")
                or card.get("salePrice")
            )
            url = (
                card.get("productUrl")
                or card.get("mallProductUrl")
                or card.get("link")
                or card.get("url")
                or ""
            )
            nv_mid = card.get("nvMid") or card.get("id")
            if not url and nv_mid:
                url = f"https://search.shopping.naver.com/catalog/{nv_mid}"
            if not url:
                continue
            products.append(
                Product(
                    source="naver",
                    title=title,
                    price=price,
                    url=str(url),
                    image_url=card.get("imageUrl") or card.get("image"),
                    mall_name=card.get("mallName") or card.get("mall"),
                    product_id=str(nv_mid) if nv_mid else None,
                    raw=card,
                )
            )
        return products

    def _parse_bff(self, data: dict, *, limit: int) -> list[Product]:
        return self._parse_search_api(data, limit=limit)

    def _extract_cards(self, data: object) -> list[dict]:
        found: list[dict] = []

        def walk(node: object) -> None:
            if isinstance(node, dict):
                keys = set(node.keys())
                if {"productTitle", "price"} & keys or {"title", "lowPrice"} & keys:
                    if any(k in keys for k in ("productUrl", "link", "nvMid", "url")):
                        found.append(node)
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(data)
        return found

    def _search_playwright(self, query: str, *, limit: int) -> list[Product]:
        from shop.browser import search_naver_with_playwright

        return search_naver_with_playwright(query, limit=limit)


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def _to_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    s = re.sub(r"[^\d]", "", str(value))
    return int(s) if s else None
