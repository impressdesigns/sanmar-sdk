"""Testing SanMar's own product information service against its recorded WSDL."""

from datetime import date
from decimal import Decimal

import pytest

from sanmar_sdk import AuthenticationError, NotFoundError, StyleQuery

from .replay import CUSTOMER_NUMBER, PASSWORD, USERNAME, envelope, replay_client, sent

LOGIN = {"sanMarCustomerNumber": str(CUSTOMER_NUMBER), "sanMarUserName": USERNAME, "sanMarUserPassword": PASSWORD}

PC61 = envelope(
    """<ns2:getProductInfoByStyleColorSizeResponse xmlns:ns2="http://impl.webservice.integration.sanmar.com/">
      <return>
        <errorOccured>false</errorOccured>
        <listResponse>
          <productBasicInfo>
            <availableSizes>Adult Sizes: S-6XL</availableSizes><brandName>Port &amp; Company</brandName>
            <caseSize>72</caseSize><catalogColor>Athletic Hthr</catalogColor><color>Athletic Heather</color>
            <inventoryKey>11803</inventoryKey><keywords>tee, tees, t-shirt</keywords><pieceWeight>0.4200</pieceWeight>
            <productDescription>A 6.1-ounce cotton tee.</productDescription><productStatus>Active</productStatus>
            <productTitle>Port &amp; Company Essential Tee. PC61</productTitle><size>S</size><sizeIndex>2</sizeIndex>
            <style>PC61</style><uniqueKey>118032</uniqueKey><category>T-Shirts</category>
          </productBasicInfo>
          <productImageInfo>
            <colorProductImage>https://cdnm.sanmar.com/imglib/PC61_front.jpg</colorProductImage>
            <productImage>https://cdnm.sanmar.com/catalog/images/PC61.jpg</productImage>
            <threeQModel>https://cdnm.sanmar.com/imglib/PC61_3q.jpg</threeQModel>
          </productImageInfo>
          <productPriceInfo>
            <casePrice>1.76</casePrice><caseSalePrice>1.38</caseSalePrice><dozenPrice>2.76</dozenPrice>
            <piecePrice>2.76</piecePrice><pieceSalePrice>1.38</pieceSalePrice><priceCode>A/P</priceCode>
            <priceText>Price applies to sizes XS-XL</priceText><saleEndDate>2015-09-20</saleEndDate>
            <saleStartDate>2015-09-14</saleStartDate><mapPrice>1.38</mapPrice>
          </productPriceInfo>
        </listResponse>
        <message>Product Info sent successfully.</message>
      </return>
    </ns2:getProductInfoByStyleColorSizeResponse>""",
)


def _answer(error: str) -> str:
    return envelope(
        f"""<ns2:getProductInfoByStyleColorSizeResponse xmlns:ns2="http://impl.webservice.integration.sanmar.com/">
          <return><errorOccured>true</errorOccured><message>{error}</message></return>
        </ns2:getProductInfoByStyleColorSizeResponse>""",
    )


def test_lookup_sends_the_catalog_color_and_the_login() -> None:
    """A lookup sends the style, color and size SanMar matches on, with the account's login."""
    sanmar, transport = replay_client()
    transport.queue(PC61)

    sanmar.products.get("PC61", catalog_color="Athletic Hthr", size="S")

    assert sent(transport) == (
        "getProductInfoByStyleColorSize",
        {"arg0": {"color": "Athletic Hthr", "size": "S", "style": "PC61"}, "arg1": LOGIN},
    )


def test_lookup_leaves_out_what_it_was_not_given() -> None:
    """A style-only lookup sends only the style; several lookups share one call."""
    sanmar, transport = replay_client()
    transport.queue(PC61)

    sanmar.products.get_many([StyleQuery(style="PC61"), StyleQuery(style="K500", size="L")])

    assert sent(transport)[1]["arg0"] == [{"style": "PC61"}, {"size": "L", "style": "K500"}]


def test_product_is_flattened_and_typed() -> None:
    """Basic, image and price information come back as one typed product."""
    sanmar, transport = replay_client()
    transport.queue(PC61)

    [product] = sanmar.products.get("PC61")

    assert (product.style, product.catalog_color, product.color_name, product.size) == (
        "PC61",
        "Athletic Hthr",
        "Athletic Heather",
        "S",
    )
    assert (product.unique_key, product.inventory_key, product.size_index) == ("118032", 11803, 2)
    assert (product.brand, product.keywords, product.piece_weight) == (
        "Port & Company",
        ["tee", "tees", "t-shirt"],
        Decimal("0.42"),
    )
    assert (product.prices.case_price, product.prices.piece_sale_price, product.prices.price_code) == (
        Decimal("1.76"),
        Decimal("1.38"),
        "A/P",
    )
    assert product.prices.sale_start_date == date(2015, 9, 14)
    assert product.images.three_quarter_model == "https://cdnm.sanmar.com/imglib/PC61_3q.jpg"


def test_unknown_color_explains_catalog_colors() -> None:
    """When SanMar cannot match a color, the error says which color name SanMar wants."""
    sanmar, transport = replay_client()
    transport.queue(_answer("Invalid Style + Color + Size specified."))

    with pytest.raises(NotFoundError, match="SANMAR_MAINFRAME_COLOR"):
        sanmar.products.get("PC61", catalog_color="Athletic Heather")


def test_rejected_login_is_an_authentication_error() -> None:
    """SanMar's authentication failure is raised as such."""
    sanmar, transport = replay_client()
    transport.queue(_answer("ERROR: User authenticating failed "))

    with pytest.raises(AuthenticationError, match="User authenticating failed"):
        sanmar.products.get("PC61")


def test_no_lookups_make_no_call() -> None:
    """An empty batch returns nothing without calling SanMar."""
    sanmar, transport = replay_client()
    assert sanmar.products.get_many([]) == []
    assert transport.sent == []


@pytest.mark.parametrize(
    ("method", "operation", "arguments", "file_pattern"),
    [
        ("request_bulk_file", "getProductBulkInfo", (), f"SanMarPI-Bulk-{CUSTOMER_NUMBER}.csv"),
        ("request_delta_file", "getProductDeltaInfo", (), f"SanMarPI-Delta-{CUSTOMER_NUMBER}.csv"),
        ("request_brand_file", "getProductInfoByBrand", ("OGIO",), "Brand_OGIO_*.csv"),
        ("request_category_file", "getProductInfoByCategory", ("Caps",), "Category_Caps_*.csv"),
    ],
)
def test_file_requests(method: str, operation: str, arguments: tuple[str, ...], file_pattern: str) -> None:
    """Asking for a product file says where it will appear."""
    sanmar, transport = replay_client()
    transport.queue(
        envelope(
            f"""<ns2:{operation}Response xmlns:ns2="http://impl.webservice.integration.sanmar.com/">
              <return><errorOccured>false</errorOccured>
              <message>Your file will be available shortly in the SanMarPI folder on our FTP server</message></return>
            </ns2:{operation}Response>""",
        ),
    )

    request = getattr(sanmar.products, method)(*arguments)

    assert (request.folder, request.file_pattern) == ("SanMarPDD/SanMarPI", file_pattern)
    assert request.message.startswith("Your file will be available")
    name, payload = sent(transport)
    assert name == operation
    if arguments:
        assert payload["arg1"] == LOGIN
        assert next(iter(payload["arg0"].values())) == arguments[0]
    else:
        assert payload == {"arg0": LOGIN}
