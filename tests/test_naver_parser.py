from shop.providers.naver import NaverProvider


def test_parse_current_naver_bff_payload() -> None:
    payload = {
        "data": [
            {
                "page": 1,
                "slots": [
                    {
                        "slotType": "CARD",
                        "data": {
                            "nvMid": 51929535391,
                            "productName": "오뚜기 토마토 <mark>케찹 300g</mark>, 10개",
                            "productUrl": {"pcUrl": "", "mobileUrl": ""},
                            "productClickUrl": {
                                "pcUrl": "https://example.test/naver/51929535391"
                            },
                            "images": [{"imageUrl": "https://example.test/image.jpg"}],
                            "mallName": "테스트몰",
                            "discountedSalePrice": 18400,
                        },
                    }
                ],
            }
        ]
    }

    products = NaverProvider()._parse_bff(payload, limit=5)

    assert len(products) == 1
    assert products[0].title == "오뚜기 토마토 케찹 300g, 10개"
    assert products[0].price == 18400
    assert products[0].url == "https://example.test/naver/51929535391"
    assert products[0].image_url == "https://example.test/image.jpg"
    assert products[0].mall_name == "테스트몰"
    assert products[0].product_id == "51929535391"
