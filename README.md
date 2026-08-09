# shop

개인용 쇼핑 검색 + 최저가 추적 CLI (네이버 / 이마트).

- 검색 결과를 **로컬 SQLite**에 저장 (wishlist / tracker)
- Hermes / Discord 게이트웨이에서 쉘 tool로 호출하기 좋게 CLI 중심
- Naver: public BFF JSON 우선 → Playwright fallback
- Emart/SSG: structured search API used by the Emart mobile frontend

## Setup (uv)

```bash
cd shop
uv sync
uv run playwright install chromium   # Naver browser fallback
```

## Commands

```bash
# 검색
uv run shop search "케찹 300g" -s naver
uv run shop search "홍초" -s emart -n 5

# 검색 결과 N번째를 SQLite에 저장
uv run shop save naver 1 --target 3000

# URL 직접 저장
uv run shop save-url "https://..." --title "케찹" --price 2500 -s naver

# 목록 / 가격 재조회 / 삭제
uv run shop list
uv run shop check
uv run shop rm 1
```

DB 기본 경로: `data/shop.db`

## E2E keywords

케찹 300g · 홍초 · 롤휴지 · 김치 1kg · 소면 작은거 · 천도복숭아

```bash
uv run pytest tests/e2e -v
```

## Hermes

```text
shop search "..." -s naver --json
shop list --json
shop check
```
