"""Testing SanMar's own invoicing service against its recorded WSDL."""

from datetime import date
from decimal import Decimal

import pytest

from sanmar_sdk import AuthenticationError, NotFoundError

from .replay import CUSTOMER_NUMBER, PASSWORD, USERNAME, envelope, fault, replay_client, sent

LOGIN = {"CustomerNo": str(CUSTOMER_NUMBER), "UserName": USERNAME, "Password": PASSWORD}

HEADER = """<Header>
  <InvoiceNo>58316700</InvoiceNo><SalesOrderNumber>71490386</SalesOrderNumber><InvoiceDate>2026-06-18</InvoiceDate>
  <InvoiceStatus>Unpaid</InvoiceStatus><CustomerNo>123456</CustomerNo>
  <SoldTo><Name>IMPRESS DESIGNS</Name><Address><Address1>1404 W MAIN ST</Address1><City>CARROLLTON</City>
    <State>TX</State><PostalCode>75006</PostalCode><Country>US</Country></Address></SoldTo>
  <PurchaseOrderNo>85496</PurchaseOrderNo><OrderDate>2026-06-16</OrderDate><DueDate>2026-07-18</DueDate>
  <ShipVia>UPS</ShipVia><FOB>IRVING TX</FOB><Terms>NET 30</Terms><TotalCases>1</TotalCases><TotalWeight>9</TotalWeight>
  <SubTotal>14.98</SubTotal><SalesTax>0</SalesTax><ShippingHandlingCharges>9.95</ShippingHandlingCharges>
  <TotalAmount>24.93</TotalAmount><Miscellaneous><FreightSavings>0</FreightSavings></Miscellaneous>
</Header>"""

LINE = """<LineItem><StyleNo>K500</StyleNo><StyleColor>Black</StyleColor>
  <StyleDescription>Silk Touch Polo</StyleDescription><StyleSize>L</StyleSize><Quantity>2</Quantity>
  <UnitPrice>7.49</UnitPrice><Amount>14.98</Amount><UniqueKey>208284</UniqueKey>
</LineItem>"""

NAMESPACE = 'xmlns="http://webservice.integration.sanmar.com/"'


def test_one_invoice_by_number() -> None:
    """An invoice comes back with its header and lines, typed."""
    sanmar, transport = replay_client()
    transport.queue(envelope(f"<Invoice {NAMESPACE}>{HEADER}{LINE}</Invoice>"))

    invoice = sanmar.invoices.get(58316700)

    assert sent(transport) == ("GetInvoiceByInvoiceNo", {**LOGIN, "InvoiceNo": "58316700"})
    header = invoice.header
    assert (header.invoice_number, header.sales_order_number, header.po_number, header.status) == (
        58316700,
        71490386,
        "85496",
        "Unpaid",
    )
    assert (header.invoice_date, header.total, header.freight_savings) == (
        date(2026, 6, 18),
        Decimal("24.93"),
        Decimal(0),
    )
    assert header.sold_to is not None
    assert header.sold_to.address.city == "CARROLLTON"
    [line] = invoice.lines
    assert (line.style, line.catalog_color, line.size, line.quantity, line.unit_price, line.unique_key) == (
        "K500",
        "Black",
        "L",
        2,
        Decimal("7.49"),
        "208284",
    )


def test_missing_invoice_is_not_found() -> None:
    """SanMar's "Data not found" fault for one invoice is a NotFoundError."""
    sanmar, transport = replay_client()
    transport.queue(fault("Data not found"), status=500)

    with pytest.raises(NotFoundError, match="58316700"):
        sanmar.invoices.get(58316700)


def test_invoices_by_purchase_order() -> None:
    """A PO's invoices come back as a list; none is an empty list, not an error."""
    sanmar, transport = replay_client()
    transport.queue(envelope(f"<Invoices {NAMESPACE}><Invoice>{HEADER}{LINE}</Invoice></Invoices>"))
    transport.queue(fault("Data not found"), status=500)

    assert [invoice.header.invoice_number for invoice in sanmar.invoices.by_purchase_order("85496")] == [58316700]
    assert sanmar.invoices.by_purchase_order("nothing") == []
    assert sent(transport, 0) == ("GetInvoicesByPurchaseOrderNo", {**LOGIN, "PurchaseOrderNo": "85496"})


def test_date_ranges_are_sent_as_dates_and_limited() -> None:
    """Date ranges go out as ISO dates, and ranges SanMar would refuse fail up front."""
    sanmar, transport = replay_client()
    transport.queue(
        envelope(f"<InvoicesHeader {NAMESPACE}><InvoiceHeader>{HEADER[8:-9]}</InvoiceHeader></InvoicesHeader>")
    )

    headers = sanmar.invoices.headers_by_invoice_date(date(2026, 1, 1), date(2026, 6, 30))

    assert [header.invoice_number for header in headers] == [58316700]
    assert sent(transport) == (
        "GetInvoicesHeaderByInvoiceDateRange",
        {**LOGIN, "StartDate": "2026-01-01", "EndDate": "2026-06-30"},
    )
    with pytest.raises(ValueError, match="at most 92 days"):
        sanmar.invoices.by_invoice_date(date(2026, 1, 1), date(2026, 6, 30))
    with pytest.raises(ValueError, match="before the start"):
        sanmar.invoices.by_invoice_date(date(2026, 6, 30), date(2026, 1, 1))


@pytest.mark.parametrize(
    ("method", "operation", "arguments", "extra"),
    [
        ("by_order_date", "GetInvoicesByOrderDate", (date(2026, 6, 16),), {"Date": "2026-06-16"}),
        ("unpaid", "GetUnpaidInvoices", (), {}),
        ("since_last_call", "GetInvoices", (), {}),
        ("headers_by_purchase_order", "GetInvoicesHeaderByPurchaseOrderNo", ("85496",), {"PurchaseOrderNo": "85496"}),
        ("headers_by_order_date", "GetInvoicesHeaderByOrderDate", (date(2026, 6, 16),), {"Date": "2026-06-16"}),
        ("unpaid_headers", "GetUnpaidInvoicesHeader", (), {}),
    ],
)
def test_every_lookup_calls_its_operation(
    method: str,
    operation: str,
    arguments: tuple[object, ...],
    extra: dict[str, str],
) -> None:
    """Each lookup calls the operation it is named for, with the login and its arguments."""
    sanmar, transport = replay_client()
    transport.queue(fault("Data not found"), status=500)

    assert getattr(sanmar.invoices, method)(*arguments) == []
    assert sent(transport) == (operation, {**LOGIN, **extra})


def test_rejected_login_is_an_authentication_error() -> None:
    """SanMar's "Unauthenticated request" fault is an AuthenticationError."""
    sanmar, transport = replay_client()
    transport.queue(fault("Unauthenticated request"), status=500)

    with pytest.raises(AuthenticationError):
        sanmar.invoices.unpaid()
