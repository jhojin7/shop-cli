from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


Source = Literal["naver", "emart"]


class Product(BaseModel):
    """Normalized product candidate from a provider search."""

    source: Source
    title: str
    price: int | None = None  # KRW, integer won
    url: str
    image_url: str | None = None
    mall_name: str | None = None
    product_id: str | None = None  # provider-specific id when available
    raw: dict | None = Field(default=None, exclude=True)


class TrackedItem(BaseModel):
    """Item saved to local SQLite wishlist / price tracker."""

    id: int | None = None
    source: Source
    title: str
    url: str
    product_id: str | None = None
    mall_name: str | None = None
    target_price: int | None = None  # alert when current <= target
    last_price: int | None = None
    last_checked_at: datetime | None = None
    created_at: datetime | None = None
    note: str | None = None


class PriceSnapshot(BaseModel):
    item_id: int
    price: int
    checked_at: datetime
