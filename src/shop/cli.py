from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from shop.db import DEFAULT_DB_PATH, Database
from shop.models import Source
from shop.providers import get_provider

app = typer.Typer(help="Personal shopping search & lowest-price tracker", no_args_is_help=True)
console = Console()


def _db(path: Optional[Path]) -> Database:
    return Database(path or DEFAULT_DB_PATH)


@app.command()
def search(
    query: str = typer.Argument(..., help="검색어"),
    source: Source = typer.Option("naver", "--source", "-s", help="naver | emart"),
    limit: int = typer.Option(10, "--limit", "-n"),
    json_out: bool = typer.Option(False, "--json", help="JSON 출력"),
) -> None:
    """검색 결과를 출력한다."""
    provider = get_provider(source)
    results = provider.search(query, limit=limit)
    _write_last_search(source, results)

    if json_out:
        import json

        console.print_json(json.dumps([r.model_dump() for r in results], ensure_ascii=False))
        return

    if not results:
        console.print(f"[yellow]결과 없음[/yellow] source={source} query={query!r}")
        raise typer.Exit(code=1)

    table = Table(title=f"{source} · {query}")
    table.add_column("#", style="dim", width=4)
    table.add_column("가격", justify="right")
    table.add_column("상품명")
    table.add_column("판매처", style="dim")
    table.add_column("URL", style="dim", overflow="fold")

    for i, p in enumerate(results, 1):
        price = f"{p.price:,}원" if p.price is not None else "-"
        table.add_row(str(i), price, p.title[:60], p.mall_name or "-", p.url[:80])

    console.print(table)
    console.print(
        f"\n저장: [cyan]shop save {source} <index>[/cyan]  "
        f"또는 [cyan]shop save-url <url>[/cyan]"
    )


@app.command("save")
def save_by_index(
    source: Source = typer.Argument(..., help="방금 search 한 source"),
    index: int = typer.Argument(..., help="검색 결과 번호 (1-based)"),
    target: Optional[int] = typer.Option(None, "--target", "-t", help="목표가 (원)"),
    note: Optional[str] = typer.Option(None, "--note"),
    db_path: Optional[Path] = typer.Option(None, "--db"),
) -> None:
    """마지막 search 결과에서 index 번째를 SQLite에 저장."""
    results = _read_last_search(source)
    if not results:
        console.print("[red]최근 검색 결과 없음. 먼저 shop search 실행.[/red]")
        raise typer.Exit(1)
    if index < 1 or index > len(results):
        console.print(f"[red]index 범위 오류 (1..{len(results)})[/red]")
        raise typer.Exit(1)

    product = results[index - 1]
    db = _db(db_path)
    item = db.save_product(product, target_price=target, note=note)
    db.close()
    console.print(
        f"[green]저장됨[/green] id={item.id}  {item.title[:50]}  "
        f"last={item.last_price}  target={item.target_price}"
    )


@app.command("save-url")
def save_url(
    url: str = typer.Argument(...),
    source: Source = typer.Option("naver", "--source", "-s"),
    title: str = typer.Option(..., "--title", help="상품명"),
    price: Optional[int] = typer.Option(None, "--price"),
    target: Optional[int] = typer.Option(None, "--target", "-t"),
    db_path: Optional[Path] = typer.Option(None, "--db"),
) -> None:
    """URL을 직접 추적 목록에 넣는다."""
    from shop.models import Product

    product = Product(source=source, title=title, url=url, price=price)
    db = _db(db_path)
    item = db.save_product(product, target_price=target)
    db.close()
    console.print(f"[green]저장됨[/green] id={item.id}  {item.title}")


@app.command("list")
def list_items(
    db_path: Optional[Path] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """추적 중인 상품 목록."""
    db = _db(db_path)
    items = db.list_items()
    db.close()

    if json_out:
        import json

        console.print_json(
            json.dumps([i.model_dump(mode="json") for i in items], ensure_ascii=False)
        )
        return

    if not items:
        console.print("[dim]저장된 상품 없음[/dim]")
        return

    table = Table(title="Tracked items")
    table.add_column("ID", style="cyan")
    table.add_column("Source")
    table.add_column("현재가", justify="right")
    table.add_column("목표가", justify="right")
    table.add_column("상품명")

    for it in items:
        last = f"{it.last_price:,}" if it.last_price is not None else "-"
        tgt = f"{it.target_price:,}" if it.target_price is not None else "-"
        table.add_row(str(it.id), it.source, last, tgt, it.title[:50])

    console.print(table)


@app.command()
def check(
    db_path: Optional[Path] = typer.Option(None, "--db"),
) -> None:
    """저장된 상품 가격을 다시 조회하고 갱신."""
    db = _db(db_path)
    items = db.list_items()
    if not items:
        console.print("[dim]추적 상품 없음[/dim]")
        db.close()
        return

    drops: list[str] = []
    for it in items:
        provider = get_provider(it.source)  # type: ignore[arg-type]
        from shop.models import Product

        product = Product(
            source=it.source,  # type: ignore[arg-type]
            title=it.title,
            url=it.url,
            product_id=it.product_id,
            price=it.last_price,
        )
        new_price = provider.fetch_price(product)
        if new_price is None:
            console.print(f"[yellow]id={it.id} 가격 조회 실패[/yellow] {it.title[:40]}")
            continue
        old = it.last_price
        db.update_price(it.id, new_price)  # type: ignore[arg-type]
        mark = ""
        if it.target_price is not None and new_price <= it.target_price:
            mark = " [bold green]TARGET HIT[/bold green]"
            drops.append(f"id={it.id} {it.title[:40]} → {new_price:,}원")
        console.print(
            f"id={it.id}  {old} → {new_price:,}원  {it.title[:40]}{mark}"
        )

    db.close()
    if drops:
        console.print("\n[bold]목표가 이하[/bold]")
        for d in drops:
            console.print(f"  • {d}")


@app.command()
def rm(
    item_id: int = typer.Argument(...),
    db_path: Optional[Path] = typer.Option(None, "--db"),
) -> None:
    """추적 상품 삭제."""
    db = _db(db_path)
    ok = db.delete_item(item_id)
    db.close()
    if ok:
        console.print(f"[green]삭제[/green] id={item_id}")
    else:
        console.print(f"[red]없음[/red] id={item_id}")
        raise typer.Exit(1)


# --- last-search cache (for save-by-index) ---

def _cache_path(source: str) -> Path:
    return Path.home() / ".cache" / "shop" / f"last_{source}.json"


def _write_last_search(source: str, results: list) -> None:
    import json

    path = _cache_path(source)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([r.model_dump() for r in results], ensure_ascii=False),
        encoding="utf-8",
    )


def _read_last_search(source: str) -> list:
    import json

    from shop.models import Product

    path = _cache_path(source)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Product(**row) for row in data]


if __name__ == "__main__":
    app()
