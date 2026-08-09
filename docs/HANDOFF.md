# Handoff: shop CLI (Naver / Emart price tracker)

**Date:** 2026-08-09  
**From:** Grok sandbox session  
**To:** Hermes (Pi)  
**Repo path (zip):** `shop.zip` → extract to e.g. `~/shop` or project dir

---

## Goal

Personal shopping **search → save to local SQLite → track lowest price**.

- Sources: **Naver Shopping**, **Emart/SSG**
- "Cart" = **SQLite wishlist**, not site cart / login
- Stack: **uv + Python 3.12**, Typer CLI, httpx, Playwright, Pydantic, SQLite
- Hermes should call CLI via shell (JSON flags available)

E2E grocery keywords:
- 케찹 300g
- 홍초
- 롤휴지
- 김치 1kg
- 소면 작은거
- 천도복숭아

---

## What is already done

| Area | Status |
|------|--------|
| Project layout (`uv` / hatch, `src/shop`) | Done |
| Models (`Product`, `TrackedItem`, `PriceSnapshot`) | Done |
| SQLite (`items`, `price_history`, WAL) | Done + smoke-tested |
| CLI: `search`, `save`, `save-url`, `list`, `check`, `rm` | Done |
| Provider protocol + `get_provider()` | Done |
| Naver: BFF → internal search API → Playwright fallback | Implemented |
| Emart: SSG structured search API | Implemented; uses the endpoint exposed by the Emart mobile frontend |
| Mock provider (`SHOP_MOCK=1`) for offline/CI | Done |
| E2E test file for 6 keywords × 2 sources | Done |
| Sandbox live HTTP to Naver/SSG | **Blocked** (418 / 403 from datacenter IP) |

### CLI summary

```bash
shop search "케찹 300g" -s naver
shop search "홍초" -s emart -n 5
shop save naver 1 --target 3000          # save N-th result from last search
shop save-url URL --title "..." --price 2500 -s naver
shop list
shop list --json
shop check                               # refresh prices, flag target hits
shop rm <id>
```

Default DB: `data/shop.db`  
Last search cache (for `save <source> <index>`): `~/.cache/shop/last_{source}.json`

### Env flags

| Env | Effect |
|-----|--------|
| `SHOP_MOCK=1` | Deterministic mock products (no network). Use for pipeline tests when blocked. |

---

## Setup on Pi

```bash
cd ~/shop   # or wherever you extracted the zip
uv sync
uv run playwright install chromium
```

Optional: add `shop` to PATH via `uv sync` scripts entry (`shop = shop.cli:app`).

---

## How to run tests

### A. Offline pipeline (always works)

```bash
SHOP_MOCK=1 uv run python -c "
from pathlib import Path
import tempfile
from shop.db import Database
from shop.providers import get_provider

KEYWORDS = ['케찹 300g','홍초','롤휴지','김치 1kg','소면 작은거','천도복숭아']
db = Database(Path(tempfile.mkdtemp()) / 't.db')
for source in ('naver', 'emart'):
    for q in KEYWORDS:
        r = get_provider(source).search(q, limit=3)
        assert r, (source, q)
        db.save_product(r[0], note=f'e2e:{q}')
assert len(db.list_items()) == 12
print('MOCK E2E PASS')
"
```

Or pytest (if `pytest` in dev group):

```bash
SHOP_MOCK=1 uv run pytest tests/e2e -v
```

### B. Live search (what we need from Hermes on home IP)

```bash
# Naver
uv run shop search "케찹 300g" -s naver -n 5
uv run shop search "홍초" -s naver -n 5

# Emart
uv run shop search "케찹 300g" -s emart -n 5

# Full save path
uv run shop search "롤휴지" -s naver
uv run shop save naver 1 --target 10000
uv run shop list
```

### C. Live E2E (no mock)

```bash
# unset SHOP_MOCK
uv run python -c "
from shop.providers import get_provider
KEYWORDS = ['케찹 300g','홍초','롤휴지','김치 1kg','소면 작은거','천도복숭아']
for source in ('naver', 'emart'):
    p = get_provider(source)
    for q in KEYWORDS:
        r = p.search(q, limit=3)
        print(source, q, '→', len(r), (r[0].title[:40], r[0].price) if r else 'EMPTY')
"
```

---

## Known issues (sandbox findings)

1. **Naver HTTP from cloud IP:**  
   - `ns-portal.../shopping-paged-slot` → `200` but `{"data":[]}`  
   - `search.shopping.naver.com/api/search/all` → **418** bot block HTML  
2. **SSG HTML search pages** → **403** from the current environment. The Emart mobile frontend exposes a structured search endpoint that is usable without loading the blocked HTML page.
3. The active Emart provider uses that structured endpoint; the legacy Playwright selectors in `browser.py` are no longer on the normal search path.
4. Prefer structured JSON responses over brittle DOM selectors when available.

Reference for Naver public surface (may drift):  
[NomaDamas/k-skill naver-shopping-search](https://github.com/NomaDamas/k-skill/blob/main/docs/features/naver-shopping-search.md)  
BFF: `https://ns-portal.shopping.naver.com/api/v2/shopping-paged-slot?query=...&source=shp_gui`

---

## What Hermes should report back

Please run on the **Pi** and paste results:

### 1. Environment
- `uv --version`, `python --version`
- `uv sync` success? `playwright install chromium` success?

### 2. Mock sanity (must pass)
```bash
SHOP_MOCK=1 uv run shop search "케찹 300g" -s naver
SHOP_MOCK=1 uv run shop save naver 1
SHOP_MOCK=1 uv run shop list
```
Report: OK / fail + error text.

### 3. Live Naver (critical)
For each keyword, one line:
```
naver | <keyword> | count=<n> | first_title=... | first_price=... | method=? 
```
If empty/blocked: include status (418? timeout? empty DOM?) and a short screenshot path or page title if easy.

Keywords: 케찹 300g, 홍초, 롤휴지, 김치 1kg, 소면 작은거, 천도복숭아

### 4. Live Emart
Same table for ` -s emart` (at least 2–3 keywords if slow).

### 5. Save + check path
```bash
uv run shop search "롤휴지" -s naver
uv run shop save naver 1 --target 999999
uv run shop check
uv run shop list --json
```
Report whether `check` refreshed `last_price`.

### 6. Broken pieces to fix next
- Which provider worked: BFF / API / Playwright DOM / Playwright XHR?
- Selector or block errors (exact exception / status code)
- Pi resource notes (RAM, chromium crash?)

### 7. Suggested next commits (Hermes opinion)
- Structured API schema-drift fixes?
- Persistent browser context / storage_state?
- Cron for `shop check` + Discord notify via gateway?

---

## File map

```
shop/
├── HANDOFF.md          ← this file
├── README.md
├── pyproject.toml
├── data/               ← shop.db created at runtime
├── src/shop/
│   ├── cli.py
│   ├── db.py
│   ├── models.py
│   ├── browser.py      ← Playwright
│   └── providers/
│       ├── base.py
│       ├── naver.py
│       ├── emart.py
│       └── mock.py
└── tests/e2e/test_search_save.py
```

---

## Out of scope (for later)

- Real site cart / login
- Coupang / other malls (add as new Provider)
- Discord notification wiring (Hermes gateway can wrap `shop check`)
- Browserbase cloud (optional if local Chromium is flaky)
