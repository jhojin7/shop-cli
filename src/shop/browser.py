from __future__ import annotations

"""Playwright helpers for Naver / Emart search.

Install once on the host:
  uv run playwright install chromium
"""

import re
from urllib.parse import quote

from shop.models import Product


def search_naver_with_playwright(query: str, *, limit: int = 10) -> list[Product]:
    from playwright.sync_api import sync_playwright

    url = f"https://search.shopping.naver.com/search/all?query={quote(query)}&sort=price_asc"
    captured: list[dict] = []
    products: list[Product] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            )
        )

        def on_response(response) -> None:
            try:
                u = response.url
                if "search" in u and response.status == 200:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct:
                        data = response.json()
                        if isinstance(data, dict):
                            captured.append(data)
            except Exception:
                pass

        page.on("response", on_response)
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000)

        for data in captured:
            products.extend(_products_from_naver_json(data, limit=limit - len(products)))
            if len(products) >= limit:
                browser.close()
                return products[:limit]

        cards = page.query_selector_all(
            "[class*='product_item'], [class*='basicList_item'], li[class*='item']"
        )
        for card in cards:
            if len(products) >= limit:
                break
            title_el = card.query_selector("a[class*='title'], a[class*='link']")
            price_el = card.query_selector(
                "[class*='price'], strong[class*='price'], span[class*='price']"
            )
            if not title_el:
                continue
            title = (title_el.inner_text() or "").strip()
            href = title_el.get_attribute("href") or ""
            if not title or not href:
                continue
            price = _parse_price(price_el.inner_text() if price_el else "")
            if not href.startswith("http"):
                href = f"https://search.shopping.naver.com{href}"
            products.append(Product(source="naver", title=title, price=price, url=href))
        browser.close()
    return products[:limit]


def search_emart_with_playwright(query: str, *, limit: int = 10) -> list[Product]:
    from playwright.sync_api import sync_playwright

    url = f"https://www.ssg.com/search.ssg?target=all&query={quote(query)}"
    products: list[Product] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            )
        )
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000)

        cards = page.query_selector_all(
            "[class*='cunit'], li[class*='item'], div[class*='product']"
        )
        for card in cards:
            if len(products) >= limit:
                break
            title_el = card.query_selector(
                "a[class*='title'], a[class*='name'], .title a, a[href*='item']"
            )
            price_el = card.query_selector(
                "[class*='price'], em[class*='ssg_price'], strong"
            )
            if not title_el:
                continue
            title = (title_el.inner_text() or "").strip()
            href = title_el.get_attribute("href") or ""
            if not title or not href:
                continue
            if not href.startswith("http"):
                href = f"https://www.ssg.com{href}"
            price = _parse_price(price_el.inner_text() if price_el else "")
            products.append(
                Product(
                    source="emart",
                    title=title,
                    price=price,
                    url=href,
                    mall_name="SSG/이마트",
                )
            )
        browser.close()
    return products[:limit]


def _products_from_naver_json(data: dict, *, limit: int) -> list[Product]:
    products: list[Product] = []
    candidates = (
        data.get("shoppingResult", {}).get("products")
        or data.get("data", {}).get("products")
        or data.get("products")
        or []
    )
    if not isinstance(candidates, list):
        return []

    for card in candidates:
        if len(products) >= limit:
            break
        if not isinstance(card, dict):
            continue
        title = str(
            card.get("productTitle")
            or card.get("productName")
            or card.get("title")
            or ""
        ).strip()
        title = re.sub(r"<[^>]+>", "", title)
        if not title:
            continue
        price_raw = (
            card.get("price")
            or card.get("lowPrice")
            or card.get("mobileLowPrice")
            or card.get("salePrice")
        )
        price = _parse_price(str(price_raw) if price_raw is not None else "")
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
            )
        )
    return products


def _parse_price(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None
