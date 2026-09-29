"""Testing SanMar's PromoStandards Product Data service against its recorded WSDL."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from sanmar_sdk import NotFoundError, Warehouse

from .replay import PASSWORD, USERNAME, envelope, replay_client, sent, service_message

NAMESPACES = (
    'xmlns:ns2="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/" '
    'xmlns="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/SharedObjects/"'
)
LOGIN = {"wsVersion": "2.0.0", "id": USERNAME, "password": PASSWORD}

# The Web Services Integration Guide's own sample response, trimmed.
PRODUCT = envelope(
    f"""<ns2:GetProductResponse {NAMESPACES}>
      <ns2:Product>
        <productId>MM1000</productId>
        <productName>MERCER+METTLE Stretch Heavyweight Pique Polo MM1000</productName>
        <description>Crafted in a heavier knit.</description>
        <description>8.1-ounce, 58/39/3 cotton/poly/spandex diamond pique</description>
        <priceExpiresDate xsi:nil="true" />
        <ns2:ProductKeywordArray>
          <ProductKeyword><keyword>Stretch</keyword></ProductKeyword>
          <ProductKeyword><keyword>Pique</keyword></ProductKeyword>
        </ns2:ProductKeywordArray>
        <productBrand>Mercer+Mettle</productBrand>
        <ns2:export>false</ns2:export>
        <ns2:ProductCategoryArray>
          <ProductCategory>
            <category>Polos/Knits</category><subCategory>Cotton, Easy Care</subCategory>
          </ProductCategory>
        </ns2:ProductCategoryArray>
        <ns2:RelatedProductArray>
          <RelatedProduct><relationType>Companion Sell</relationType><productId>MM1001</productId></RelatedProduct>
        </ns2:RelatedProductArray>
        <primaryImageUrl>https://cdnm.sanmar.com/catalog/images/MM1000.jpg</primaryImageUrl>
        <ns2:ProductPriceGroupArray>
          <ProductPriceGroup>
            <ProductPriceArray>
              <ProductPrice><quantityMin>1</quantityMin><quantityMax>2147483647</quantityMax><price>24.98</price></ProductPrice>
            </ProductPriceArray>
            <groupName>MSRP</groupName><currency>USD</currency>
          </ProductPriceGroup>
        </ns2:ProductPriceGroupArray>
        <complianceInfoAvailable xsi:nil="true" />
        <ns2:ProductPartArray>
          <ns2:ProductPart>
            <partId>1878771</partId>
            <ns2:primaryColor>
              <Color><standardColorName>Deep Black</standardColorName><colorName>DeepBlack</colorName></Color>
            </ns2:primaryColor>
            <ns2:ColorArray>
              <Color>
                <standardColorName>Deep Black</standardColorName><approximatePms>BLACK C</approximatePms>
                <colorName>DeepBlack</colorName>
              </Color>
            </ns2:ColorArray>
            <ApparelSize><apparelStyle>Mens</apparelStyle><labelSize>S</labelSize></ApparelSize>
            <Dimension>
              <dimensionUom>FT</dimensionUom><depth>0</depth><height>0</height><width>0</width>
              <weightUom>OZ</weightUom><weight>11.52</weight>
            </Dimension>
            <gtin>00191265938235</gtin>
            <isRushService>false</isRushService>
            <ns2:ShippingPackageArray>
              <ShippingPackage>
                <packageType>Box</packageType><quantity>36</quantity><dimensionUom>IN</dimensionUom>
                <depth>23.50</depth><height>10.00</height><width>16.50</width>
                <weightUom>LB</weightUom><weight>26.00</weight>
              </ShippingPackage>
            </ns2:ShippingPackageArray>
            <endDate xsi:nil="true" />
            <effectiveDate>2023-04-20T16:35:43.653</effectiveDate>
            <isCloseout>false</isCloseout><isCaution>false</isCaution>
            <isOnDemand>false</isOnDemand><isHazmat>false</isHazmat>
          </ns2:ProductPart>
        </ns2:ProductPartArray>
        <ns2:lastChangeDate>2023-04-20T16:35:43.653</ns2:lastChangeDate>
        <ns2:creationDate>2021-09-01T08:05:34.297</ns2:creationDate>
        <endDate xsi:nil="true" />
        <effectiveDate>2023-04-20T16:35:43.653</effectiveDate>
        <isCaution>false</isCaution>
        <isCloseout>false</isCloseout>
        <FobPointArray>
          <FobPoint>
            <fobId>6</fobId><fobCity>Jacksonville</fobCity><fobState>FL</fobState>
            <fobPostalCode>32219</fobPostalCode><fobCountry>USA</fobCountry>
          </FobPoint>
          <FobPoint>
            <fobId>40</fobId><fobCity>Somewhere New</fobCity><fobState>TX</fobState>
            <fobPostalCode>75000</fobPostalCode><fobCountry>USA</fobCountry>
          </FobPoint>
        </FobPointArray>
      </ns2:Product>
    </ns2:GetProductResponse>""",
)


def test_product_is_typed_and_flattened() -> None:
    """A product comes back with its parts, colors, sizes and prices typed."""
    sanmar, transport = replay_client()
    transport.queue(PRODUCT)

    product = sanmar.promostandards.product_data.get("MM1000", part_id="1878771", catalog_color="DeepBlack")

    assert sent(transport) == (
        "GetProductRequest",
        {
            **LOGIN,
            "localizationCountry": "US",
            "localizationLanguage": "en",
            "productId": "MM1000",
            "partId": "1878771",
            "colorName": "DeepBlack",
        },
    )
    assert (product.product_id, product.brand, product.keywords) == ("MM1000", "Mercer+Mettle", ["Stretch", "Pique"])
    assert len(product.descriptions) == 2  # noqa: PLR2004
    assert [(category.category, category.subcategory) for category in product.categories] == [
        ("Polos/Knits", "Cotton, Easy Care"),
    ]
    assert product.related_products[0].product_id == "MM1001"
    [group] = product.price_groups
    assert (group.name, group.prices[0].price) == ("MSRP", Decimal("24.98"))
    assert product.compliance_info_available is None
    assert product.creation_date == datetime(2021, 9, 1, 8, 5, 34, 297000)  # noqa: DTZ001 - SanMar sends no zone
    [part] = product.parts
    assert (part.part_id, part.catalog_color, part.gtin) == ("1878771", "DeepBlack", "00191265938235")
    assert part.colors[0].color_name == "Deep Black"
    assert part.apparel_size is not None
    assert part.apparel_size.size == "S"
    assert part.dimension is not None
    assert part.dimension.weight == Decimal("11.52")
    assert part.shipping_packages[0].quantity == 36  # noqa: PLR2004
    assert part.end_date is None
    assert [point.warehouse for point in product.fob_points] == [Warehouse.JACKSONVILLE, 40]


def test_missing_product_is_not_found() -> None:
    """A style SanMar does not have is a NotFoundError carrying its code."""
    sanmar, transport = replay_client()
    transport.queue(
        envelope(
            f"""<ns2:GetProductResponse {NAMESPACES}>
              {service_message(130, "Product Id not found")}
            </ns2:GetProductResponse>""",
        ),
    )

    with pytest.raises(NotFoundError, match="130: Product Id not found") as raised:
        sanmar.promostandards.product_data.get("NOPE")
    assert raised.value.code == 130  # noqa: PLR2004


def test_empty_product_response_is_not_found() -> None:
    """A response with neither a product nor an error is a NotFoundError too."""
    sanmar, transport = replay_client()
    transport.queue(envelope(f"<ns2:GetProductResponse {NAMESPACES}/>"))

    with pytest.raises(NotFoundError, match="NOPE"):
        sanmar.promostandards.product_data.get("NOPE")


def _references(response: str, array: str, item: str) -> str:
    return envelope(
        f"""<ns2:{response} {NAMESPACES}>
          <ns2:{array}>
            <ns2:{item}><productId>PC61</productId><partId>175762</partId></ns2:{item}>
            <ns2:{item}><productId>K500</productId></ns2:{item}>
          </ns2:{array}>
        </ns2:{response}>""",
    )


def test_closeouts() -> None:
    """Closeouts list products and parts."""
    sanmar, transport = replay_client()
    transport.queue(_references("GetProductCloseOutResponse", "ProductCloseOutArray", "ProductCloseOut"))

    references = sanmar.promostandards.product_data.closeouts()

    assert sent(transport) == ("GetProductCloseOutRequest", LOGIN)
    assert [(reference.product_id, reference.part_id) for reference in references] == [
        ("PC61", "175762"),
        ("K500", None),
    ]


def test_modified_since_sends_the_timestamp() -> None:
    """Changes since a time send that time."""
    sanmar, transport = replay_client()
    transport.queue(_references("GetProductDateModifiedResponse", "ProductDateModifiedArray", "ProductDateModified"))

    references = sanmar.promostandards.product_data.modified_since(datetime(2026, 9, 1, tzinfo=UTC))

    assert sent(transport) == ("GetProductDateModifiedRequest", {**LOGIN, "changeTimeStamp": "2026-09-01T00:00:00Z"})
    assert len(references) == 2  # noqa: PLR2004


def test_sellable() -> None:
    """Sellable parts can be narrowed to a style, and flipped to what is not sellable."""
    sanmar, transport = replay_client()
    transport.queue(_references("GetProductSellableResponse", "ProductSellableArray", "ProductSellable"))
    transport.queue(_references("GetProductSellableResponse", "ProductSellableArray", "ProductSellable"))

    sanmar.promostandards.product_data.sellable("PC61", part_id="175762")
    sanmar.promostandards.product_data.sellable(is_sellable=False)

    assert sent(transport, 0) == (
        "GetProductSellableRequest",
        {**LOGIN, "productId": "PC61", "partId": "175762", "isSellable": "true"},
    )
    assert sent(transport, 1) == ("GetProductSellableRequest", {**LOGIN, "isSellable": "false"})


def test_no_results_is_an_empty_list() -> None:
    """SanMar's "No Results Found" is an empty list for a list method."""
    sanmar, transport = replay_client()
    transport.queue(
        envelope(
            f"""<ns2:GetProductDateModifiedResponse {NAMESPACES}>
              {service_message(160, "No Results Found")}
            </ns2:GetProductDateModifiedResponse>""",
        ),
    )

    assert sanmar.promostandards.product_data.modified_since(datetime(2026, 9, 1, tzinfo=UTC)) == []
