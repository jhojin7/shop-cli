from shop.providers.emart import EmartProvider
from shop.providers import emart


def test_parse_emart_search_api_response() -> None:
    payload = {
        "res_code": "200",
        "data": {
            "dataList": [
                {
                    "unitType": "ITEM_UNIT",
                    "item": {
                        "itemId": "0000006609429",
                        "itemNm": "토마토케찹 300g",
                        "displayPrc": "2480",
                        "itemLnkd": (
                            "https://m-emart.ssg.com/item/itemView.ssg?"
                            "itemId=0000006609429&siteNo=6001&salestrNo=2037"
                        ),
                        "itemImgUrl": "https://sitem.ssgcdn.com/item.jpg",
                        "siteNo": "6001",
                        "siteNm": "이마트",
                        "salestrNm": "월계점",
                    },
                }
            ]
        },
    }

    products = EmartProvider._parse_search_response(payload, limit=5)

    assert len(products) == 1
    assert products[0].title == "토마토케찹 300g"
    assert products[0].price == 2480
    assert products[0].url.startswith("https://m-emart.ssg.com/item/itemView.ssg")
    assert products[0].image_url == "https://sitem.ssgcdn.com/item.jpg"
    assert products[0].mall_name == "이마트 · 월계점"
    assert products[0].product_id == "0000006609429"


def test_search_retries_with_first_term_when_full_query_is_empty(monkeypatch) -> None:
    queries: list[str] = []

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self.payload

    def fake_post(url: str, *, json: dict, headers: dict, timeout: float) -> FakeResponse:
        query = json["params"]["query"]
        queries.append(query)
        if query == "소면 작은거":
            return FakeResponse({"res_code": "200", "data": {"dataList": []}})
        return FakeResponse(
            {
                "res_code": "200",
                "data": {
                    "dataList": [
                        {
                            "unitType": "ITEM_UNIT",
                            "item": {
                                "itemId": "noodle-1",
                                "itemNm": "소면 500g",
                                "displayPrc": "1980",
                                "itemLnkd": "https://m-emart.ssg.com/item/noodle-1",
                            },
                        }
                    ]
                },
            }
        )

    monkeypatch.setattr(emart.httpx, "post", fake_post)

    products = EmartProvider().search("소면 작은거", limit=3)

    assert queries == ["소면 작은거", "소면"]
    assert products[0].title == "소면 500g"
