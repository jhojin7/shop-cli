from __future__ import annotations

import os
import re
from datetime import datetime

import httpx

from shop.models import Product


class EmartProvider:
    """Emart mall search through SSG's structured frontend search endpoint."""

    name = "emart"
    SEARCH_URL = "https://search.ssg.com/api/searchItem"
    DEFAULT_SITE_NO = "7018"  # Emart mall frontend site number

    def search(self, query: str, *, limit: int = 10) -> list[Product]:
        queries = [query]
        first_term = query.strip().split(maxsplit=1)[0] if query.strip() else ""
        if first_term and first_term != query.strip():
            queries.append(first_term)

        for search_query in queries:
            try:
                response = httpx.post(
                    self.SEARCH_URL,
                    json=self._request_body(search_query, limit=limit),
                    headers=self._headers(),
                    timeout=20.0,
                )
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError):
                continue

            if payload.get("res_code") not in (None, "200", 200):
                continue
            products = self._parse_search_response(payload, limit=limit)
            if products:
                return products
        return []

    def fetch_price(self, product: Product) -> int | None:
        results = self.search(product.title, limit=20)
        for r in results:
            if product.product_id and r.product_id == product.product_id:
                return r.price
            if r.url == product.url:
                return r.price
        return None

    @classmethod
    def _request_body(cls, query: str, *, limit: int) -> dict:
        site_no = os.environ.get("SHOP_EMART_SITE_NO", cls.DEFAULT_SITE_NO)
        count = min(max(limit, 1), 40)
        now = datetime.now().strftime("%Y%m%d%H%M%S")
        return {
            "common": {
                "ts": now,
                "mobil_app_no": "12",
                "apl_ver": "2.8.2",
                "os_cd": "20",
                "viewSiteNo": site_no,
            },
            "params": {
                "siteNo": site_no,
                "count": str(count),
                "adYn": "Y",
                "target": "mobile_api_filter",
                "unitInx": 0,
                "page": 1,
                "query": query,
            },
        }

    @staticmethod
    def _headers() -> dict[str, str]:
        return {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/json; charset=utf-8",
            "Origin": "https://m-emart.ssg.com",
            "Referer": "https://m-emart.ssg.com/",
        }

    @classmethod
    def _parse_search_response(cls, payload: object, *, limit: int) -> list[Product]:
        if not isinstance(payload, dict):
            return []
        data = payload.get("data")
        if not isinstance(data, dict):
            return []
        data_list = data.get("dataList")
        if not isinstance(data_list, list):
            return []

        products: list[Product] = []
        for unit in data_list:
            if len(products) >= limit or not isinstance(unit, dict):
                break
            if unit.get("unitType") != "ITEM_UNIT":
                continue
            item = unit.get("item")
            if not isinstance(item, dict):
                continue

            title = str(item.get("itemNm") or "").strip()
            url = str(item.get("itemLnkd") or "").strip()
            if not title or not url:
                continue
            if not url.startswith("http"):
                url = f"https://m-emart.ssg.com{url}"

            mall = str(item.get("siteNm") or "이마트").strip()
            store = str(item.get("salestrNm") or "").strip()
            mall_name = f"{mall} · {store}" if store else mall

            products.append(
                Product(
                    source="emart",
                    title=title,
                    price=cls._to_int(
                        item.get("displayPrc")
                        or item.get("salesPrc")
                        or item.get("salePrc")
                    ),
                    url=url,
                    image_url=item.get("itemImgUrl"),
                    mall_name=mall_name,
                    product_id=str(item.get("itemId")) if item.get("itemId") else None,
                    raw=item,
                )
            )
        return products

    @staticmethod
    def _to_int(value: object) -> int | None:
        if value is None:
            return None
        digits = re.sub(r"[^\d]", "", str(value))
        return int(digits) if digits else None
