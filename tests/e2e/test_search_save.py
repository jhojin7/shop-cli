"""E2E: search + save to SQLite for grocery keywords.

Sandbox / CI:
  SHOP_MOCK=1 PYTHONPATH=src:.deps python3 -m pytest tests/e2e -v

Live (Pi):
  uv run pytest tests/e2e -v
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from shop.db import Database
from shop.providers import get_provider

KEYWORDS = [
    "케찹 300g",
    "홍초",
    "롤휴지",
    "김치 1kg",
    "소면 작은거",
    "천도복숭아",
]


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test_shop.db")


@pytest.mark.parametrize("query", KEYWORDS)
@pytest.mark.parametrize("source", ["naver", "emart"])
def test_search_and_save(db: Database, query: str, source: str, monkeypatch: pytest.MonkeyPatch) -> None:
    if os.environ.get("SHOP_MOCK") is None:
        monkeypatch.setenv("SHOP_MOCK", "1")

    provider = get_provider(source)  # type: ignore[arg-type]
    results = provider.search(query, limit=5)
    assert results, f"{source} search empty for {query!r}"
    item = db.save_product(results[0])
    assert item.id is not None
    assert item.title
    assert item.url
    assert item.source == source
    listed = db.list_items()
    assert any(x.id == item.id for x in listed)


def test_full_grocery_cart_pipeline(db: Database, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHOP_MOCK", "1")
    saved_ids: list[int] = []
    for source in ("naver", "emart"):
        provider = get_provider(source)  # type: ignore[arg-type]
        for query in KEYWORDS:
            results = provider.search(query, limit=3)
            assert results
            item = db.save_product(results[0], note=f"e2e:{query}")
            assert item.id is not None
            saved_ids.append(item.id)

    items = db.list_items()
    assert len(items) == len(KEYWORDS) * 2
    assert len(set(saved_ids)) == len(saved_ids)
