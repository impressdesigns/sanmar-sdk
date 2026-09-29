"""Reading from SanMar's real web services, to check the SDK parses what SanMar sends.

Every call here only reads. The style, color and size are K500 Black L, one of the test
items the Purchase Order Integration Guide lists for EDEV, so these run on either
environment.
"""

from datetime import UTC, date, datetime, timedelta

from sanmar_sdk import SanMar, SkuKey
from sanmar_sdk.promostandards import IssueDetail

STYLE = "K500"
CATALOG_COLOR = "Black"
SIZE = "L"
PART_ID = "208284"


def test_standard_product_information(sanmar: SanMar) -> None:
    """SanMar's own product service describes the test item."""
    [product] = sanmar.products.get(STYLE, catalog_color=CATALOG_COLOR, size=SIZE)
    assert (product.style, product.catalog_color, product.size, product.unique_key) == (
        STYLE,
        CATALOG_COLOR,
        SIZE,
        PART_ID,
    )


def test_standard_inventory_and_pricing(sanmar: SanMar) -> None:
    """SanMar's own inventory and pricing services answer for the test item, by style and by key."""
    [stock] = sanmar.inventory.get(STYLE, catalog_color=CATALOG_COLOR, size=SIZE)
    assert stock.warehouses
    [quote] = sanmar.pricing.get(STYLE, catalog_color=CATALOG_COLOR, size=SIZE)
    assert sanmar.pricing.get_by_key(SkuKey(inventory_key=quote.inventory_key, size_index=quote.size_index))


def test_standard_invoice_headers(sanmar: SanMar) -> None:
    """SanMar's own invoicing service lists unpaid invoice headers, if there are any."""
    assert isinstance(sanmar.invoices.unpaid_headers(), list)


def test_promostandards_product_data_and_media(sanmar: SanMar) -> None:
    """PromoStandards describes the style and lists its images."""
    product = sanmar.promostandards.product_data.get(STYLE, part_id=PART_ID)
    assert [part.part_id for part in product.parts] == [PART_ID]
    assert sanmar.promostandards.product_data.sellable(STYLE)
    assert sanmar.promostandards.media_content.get(STYLE, part_id=PART_ID)


def test_promostandards_inventory_and_pricing(sanmar: SanMar) -> None:
    """PromoStandards reports stock and prices for the test item."""
    [stock] = sanmar.promostandards.inventory.get(STYLE, part_ids=[PART_ID])
    assert stock.part_id == PART_ID
    assert stock.locations
    assert sanmar.promostandards.pricing.get(STYLE, part_id=PART_ID)
    assert sanmar.promostandards.pricing.fob_points(STYLE)


def test_promostandards_orders_and_invoices(sanmar: SanMar) -> None:
    """PromoStandards order, shipment and invoice lookups answer, even when there is nothing to report."""
    assert sanmar.promostandards.order_status.service_methods()
    assert isinstance(sanmar.promostandards.order_status.open_orders(issues=IssueDetail.NONE, lines=False), list)
    assert isinstance(
        sanmar.promostandards.shipment_notifications.since(datetime.now(tz=UTC) - timedelta(days=1)),
        list,
    )
    assert isinstance(sanmar.promostandards.invoices.by_date(date.today() - timedelta(days=1)), list)  # noqa: DTZ011
    assert sanmar.promostandards.purchase_orders.supported_order_types() == ["Blank"]
