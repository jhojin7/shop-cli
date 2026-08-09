from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from shop.models import PriceSnapshot, Product, TrackedItem

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "shop.db"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path | str = DEFAULT_DB_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                product_id TEXT,
                mall_name TEXT,
                target_price INTEGER,
                last_price INTEGER,
                last_checked_at TEXT,
                created_at TEXT NOT NULL,
                note TEXT
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                price INTEGER NOT NULL,
                checked_at TEXT NOT NULL,
                FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_price_history_item
                ON price_history(item_id, checked_at);
            """
        )
        self._conn.commit()

    def save_product(
        self,
        product: Product,
        *,
        target_price: int | None = None,
        note: str | None = None,
    ) -> TrackedItem:
        """Insert or update tracked item by URL. Returns the row."""
        now = _utc_now()
        existing = self._conn.execute(
            "SELECT id FROM items WHERE url = ?", (product.url,)
        ).fetchone()

        if existing:
            self._conn.execute(
                """
                UPDATE items SET
                    title = ?,
                    product_id = ?,
                    mall_name = ?,
                    last_price = COALESCE(?, last_price),
                    target_price = COALESCE(?, target_price),
                    note = COALESCE(?, note),
                    last_checked_at = ?
                WHERE id = ?
                """,
                (
                    product.title,
                    product.product_id,
                    product.mall_name,
                    product.price,
                    target_price,
                    note,
                    now if product.price is not None else None,
                    existing["id"],
                ),
            )
            item_id = existing["id"]
        else:
            cur = self._conn.execute(
                """
                INSERT INTO items (
                    source, title, url, product_id, mall_name,
                    target_price, last_price, last_checked_at, created_at, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product.source,
                    product.title,
                    product.url,
                    product.product_id,
                    product.mall_name,
                    target_price,
                    product.price,
                    now if product.price is not None else None,
                    now,
                    note,
                ),
            )
            item_id = cur.lastrowid

        if product.price is not None:
            self._conn.execute(
                """
                INSERT INTO price_history (item_id, price, checked_at)
                VALUES (?, ?, ?)
                """,
                (item_id, product.price, now),
            )

        self._conn.commit()
        return self.get_item(item_id)  # type: ignore[return-value]

    def list_items(self) -> list[TrackedItem]:
        rows = self._conn.execute(
            "SELECT * FROM items ORDER BY id DESC"
        ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def get_item(self, item_id: int) -> TrackedItem | None:
        row = self._conn.execute(
            "SELECT * FROM items WHERE id = ?", (item_id,)
        ).fetchone()
        return self._row_to_item(row) if row else None

    def update_price(self, item_id: int, price: int) -> None:
        now = _utc_now()
        self._conn.execute(
            """
            UPDATE items SET last_price = ?, last_checked_at = ? WHERE id = ?
            """,
            (price, now, item_id),
        )
        self._conn.execute(
            """
            INSERT INTO price_history (item_id, price, checked_at)
            VALUES (?, ?, ?)
            """,
            (item_id, price, now),
        )
        self._conn.commit()

    def history(self, item_id: int, limit: int = 50) -> list[PriceSnapshot]:
        rows = self._conn.execute(
            """
            SELECT item_id, price, checked_at FROM price_history
            WHERE item_id = ?
            ORDER BY checked_at DESC
            LIMIT ?
            """,
            (item_id, limit),
        ).fetchall()
        return [
            PriceSnapshot(
                item_id=r["item_id"],
                price=r["price"],
                checked_at=datetime.fromisoformat(r["checked_at"]),
            )
            for r in rows
        ]

    def delete_item(self, item_id: int) -> bool:
        cur = self._conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        self._conn.commit()
        return cur.rowcount > 0

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> TrackedItem:
        return TrackedItem(
            id=row["id"],
            source=row["source"],
            title=row["title"],
            url=row["url"],
            product_id=row["product_id"],
            mall_name=row["mall_name"],
            target_price=row["target_price"],
            last_price=row["last_price"],
            last_checked_at=(
                datetime.fromisoformat(row["last_checked_at"])
                if row["last_checked_at"]
                else None
            ),
            created_at=(
                datetime.fromisoformat(row["created_at"])
                if row["created_at"]
                else None
            ),
            note=row["note"],
        )

    def close(self) -> None:
        self._conn.close()
