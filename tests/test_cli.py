from pathlib import Path

from shop import cli


def test_json_search_updates_save_cache(monkeypatch, tmp_path: Path) -> None:
    cache_path = tmp_path / "last_naver.json"
    monkeypatch.setattr(cli, "_cache_path", lambda source: cache_path)
    monkeypatch.setenv("SHOP_MOCK", "1")

    cli.search("케찹 300g", source="naver", limit=1, json_out=True)

    cached = cli._read_last_search("naver")
    assert len(cached) == 1
    assert cached[0].title == "케찹 300g 테스트상품 1"
