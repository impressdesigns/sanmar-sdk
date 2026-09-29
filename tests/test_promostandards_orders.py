"""Testing SanMar's PromoStandards Order Status and Invoice services against their recorded WSDLs."""

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from sanmar_sdk import NotFoundError
from sanmar_sdk.promostandards import IssueDetail, Status

from .replay import PASSWORD, USERNAME, envelope, replay_client, sent, service_message

STATUS = (
    'xmlns:ns2="http://www.promostandards.org/WSDL/OrderStatus/2.0.0/" '
    'xmlns="http://www.promostandards.org/WSDL/OrderStatus/2.0.0/SharedObjects/"'
)
INVOICES = (
    'xmlns:ns2="http://www.promostandards.org/WSDL/Invoice/1.0.0/" '
    'xmlns="http://www.promostandards.org/WSDL/Invoice/1.0.0/SharedObjects/"'
)


def _status(order: str, product_status: str) -> str:
    # Shaped like the Web Services Integration Guide's sample response.
    return f"""<OrderStatus>
      <purchaseOrderNumber>SS3820</purchaseOrderNumber>
      <OrderStatusDetailArray>
        <OrderStatusDetail>
          <salesOrderNumber>100267568</salesOrderNumber>
          <status>{order}</status>
          <issueCategory>generalHold</issueCategory>
          <OrderContactArray><Contact><contactType>Sales</contactType><ContactDetails /></Contact></OrderContactArray>
          <ProductArray>
            <Product>
              <productId>PC54</productId><partId>538612</partId><salesOrderLineNumber>1</salesOrderLineNumber>
              <QuantityOrdered><value>500</value><uom>EA</uom></QuantityOrdered>
              <QuantityShipped><value>0</value><uom>EA</uom></QuantityShipped>
              <status>{product_status}</status>
            </Product>
          </ProductArray>
          <IssueArray>
            <Issue>
              <issueStatus>Open</issueStatus><issueCategory>generalHold</issueCategory>
              <urgentResponseRequired>false</urgentResponseRequired>
              <productId>PC54</productId><partId>538612</partId>
            </Issue>
          </IssueArray>
          <validTimestamp>2026-09-07T16:11:10.497-08:00</validTimestamp>
        </OrderStatusDetail>
      </OrderStatusDetailArray>
    </OrderStatus>"""


def _statuses(*orders: str) -> str:
    return envelope(
        f"<ns2:GetOrderStatusResponse {STATUS}><OrderStatusArray>{''.join(orders)}</OrderStatusArray>"
        "</ns2:GetOrderStatusResponse>",
    )


def test_status_by_purchase_order() -> None:
    """A purchase order's status comes back per sales order, line and issue."""
    sanmar, transport = replay_client()
    transport.queue(_statuses(_status("received", "Partially Shipped")))

    [status] = sanmar.promostandards.order_status.by_purchase_order("SS3820", issues=IssueDetail.ALL)

    assert sent(transport) == (
        "GetOrderStatusRequest",
        {
            "wsVersion": "2.0.0",
            "id": USERNAME,
            "password": PASSWORD,
            "queryType": "poSearch",
            "referenceNumber": "SS3820",
            "returnIssueDetailType": "allIssues",
            "returnProductDetail": "true",
        },
    )
    [order] = status.sales_orders
    assert (order.sales_order_number, order.status, order.issue_category) == (
        "100267568",
        Status.RECEIVED,
        "generalHold",
    )
    [line] = order.lines
    assert (line.part_id, line.quantity_ordered, line.quantity_shipped, line.status) == (
        "538612",
        Decimal(500),
        Decimal(0),
        Status.PARTIALLY_SHIPPED,
    )
    assert (order.issues[0].status, order.contacts[0].contact_type) == ("Open", "Sales")
    assert not status.finished


def test_unknown_status_is_kept_as_text() -> None:
    """A status SanMar adds later is kept as text rather than failing the response."""
    sanmar, transport = replay_client()
    transport.queue(_statuses(_status("complete", "onTheMoon")))

    [status] = sanmar.promostandards.order_status.by_sales_order("100267568", lines=False)

    assert status.sales_orders[0].lines[0].status == "onTheMoon"
    assert status.finished
    assert sent(transport)[1]["returnProductDetail"] == "false"
    assert sent(transport)[1]["queryType"] == "soSearch"


@pytest.mark.parametrize(("method", "query_type"), [("open_orders", "allOpen"), ("open_issues", "allOpenIssues")])
def test_open_order_queries(method: str, query_type: str) -> None:
    """The open-order queries send no reference, and nothing found is an empty list."""
    sanmar, transport = replay_client()
    transport.queue(
        envelope(
            f"""<ns2:GetOrderStatusResponse {STATUS}>
              {service_message(160, "No Results Found")}
            </ns2:GetOrderStatusResponse>""",
        ),
    )

    assert getattr(sanmar.promostandards.order_status, method)() == []
    request = sent(transport)[1]
    assert (request["queryType"], "referenceNumber" in request) == (query_type, False)


def test_updated_since_is_limited_to_30_days() -> None:
    """Status changes go back at most 30 days."""
    sanmar, transport = replay_client()
    transport.queue(_statuses())
    since = datetime.now(tz=UTC).replace(microsecond=0) - timedelta(days=29)

    sanmar.promostandards.order_status.updated_since(since)

    assert sent(transport)[1]["statusTimeStamp"] == since.strftime("%Y-%m-%dT%H:%M:%SZ")
    with pytest.raises(ValueError, match="30 days"):
        sanmar.promostandards.order_status.updated_since(datetime.now(tz=UTC) - timedelta(days=31))
    with pytest.raises(ValueError, match="time zone"):
        sanmar.promostandards.order_status.updated_since(datetime(2026, 9, 28))  # noqa: DTZ001


def test_service_methods_log_information(caplog: pytest.LogCaptureFixture) -> None:
    """Service methods are listed, and SanMar's information message is logged, not raised."""
    sanmar, transport = replay_client()
    transport.queue(
        envelope(
            f"""<ns2:GetServiceMethodsResponse {STATUS}>
              <ServiceMethodArray><serviceMethod>GetOrderStatus</serviceMethod></ServiceMethodArray>
              <ServiceMessageArray>
                <ServiceMessage>
                  <code>0</code><description>Information returned successfully.</description>
                  <severity>Information</severity>
                </ServiceMessage>
                <ServiceMessage>
                  <code>999</code><description>Slow today.</description><severity>Warning</severity>
                </ServiceMessage>
              </ServiceMessageArray>
            </ns2:GetServiceMethodsResponse>""",
        ),
    )

    with caplog.at_level(logging.DEBUG, logger="sanmar_sdk"):
        assert sanmar.promostandards.order_status.service_methods() == ["GetOrderStatus"]

    assert [(record.levelname, record.getMessage()) for record in caplog.records] == [
        ("DEBUG", "SanMar: Information returned successfully. (0)"),
        ("WARNING", "SanMar: Slow today. (999)"),
    ]


INVOICE = """<ns2:Invoice>
  <invoiceNumber>123456798</invoiceNumber><invoiceType>Invoice</invoiceType><invoiceDate>2026-09-24</invoiceDate>
  <purchaseOrderNumber>112233445</purchaseOrderNumber>
  <ns2:BillTo>
    <AccountInfo><accountName>TestAccount</accountName><accountNumber>12345</accountNumber>
    <Address1>Testaddress</Address1><Address2>STE A</Address2><city>Seattle</city><region>WA</region></AccountInfo>
  </ns2:BillTo>
  <paymentDueDate>2026-10-24</paymentDueDate><currency>USD</currency>
  <salesAmount>15.67</salesAmount><shippingAmount>0.0</shippingAmount><handlingAmount>0.0</handlingAmount>
  <taxAmount>0.00</taxAmount><invoiceAmount>15.67</invoiceAmount><advancePaymentAmount>0.00</advancePaymentAmount>
  <invoiceAmountDue>15.67</invoiceAmountDue>
  <ns2:InvoiceLineItemsArray>
    <InvoiceLineItem>
      <productId>ST860</productId><partId>1019704</partId><invoiceQuantity>1</invoiceQuantity><quantityUOM>EA</quantityUOM>
      <lineItemDescription>ST Sport-Wick Textured 1/4-Zip</lineItemDescription>
      <unitPrice>15.67</unitPrice><extendedPrice>15.67</extendedPrice>
    </InvoiceLineItem>
  </ns2:InvoiceLineItemsArray>
  <ns2:SalesOrderNumbersArray><salesOrderNumber>12345123</salesOrderNumber></ns2:SalesOrderNumbersArray>
</ns2:Invoice>"""


def _invoices(*invoices: str) -> str:
    return envelope(
        f"<ns2:GetInvoicesResponse {INVOICES}><ns2:InvoiceArray>{''.join(invoices)}</ns2:InvoiceArray>"
        "</ns2:GetInvoicesResponse>",
    )


def test_one_invoice_by_number() -> None:
    """An invoice comes back with its amounts, lines and sales orders."""
    sanmar, transport = replay_client()
    transport.queue(_invoices(INVOICE))

    invoice = sanmar.promostandards.invoices.get("123456798")

    assert sent(transport) == (
        "GetInvoicesRequest",
        {"wsVersion": "1.0.0", "id": USERNAME, "password": PASSWORD, "queryType": "2", "referenceNumber": "123456798"},
    )
    assert (invoice.invoice_date, invoice.amount_due, invoice.sales_order_numbers) == (
        date(2026, 9, 24),
        Decimal("15.67"),
        ["12345123"],
    )
    assert invoice.bill_to is not None
    assert (invoice.bill_to.account_number, invoice.bill_to.address2) == ("12345", "STE A")
    assert invoice.sold_to is None
    [line] = invoice.lines
    assert (line.part_id, line.invoice_quantity, line.extended_price) == ("1019704", Decimal(1), Decimal("15.67"))


def test_missing_invoice_is_not_found() -> None:
    """An invoice number SanMar does not know is a NotFoundError, however SanMar says so."""
    sanmar, transport = replay_client()
    transport.queue(_invoices())
    transport.queue(
        envelope(
            f"""<ns2:GetInvoicesResponse {INVOICES}>
              {service_message(160, "No Results Found")}
            </ns2:GetInvoicesResponse>""",
        ),
    )

    with pytest.raises(NotFoundError, match="123456798"):
        sanmar.promostandards.invoices.get("123456798")
    with pytest.raises(NotFoundError, match="123456798"):
        sanmar.promostandards.invoices.get("123456798")


def test_invoice_queries() -> None:
    """Each invoice query sends its own query type and argument."""
    sanmar, transport = replay_client()
    for _ in range(3):
        transport.queue(_invoices(INVOICE))

    sanmar.promostandards.invoices.by_purchase_order("112233445")
    sanmar.promostandards.invoices.by_date(date(2026, 9, 24))
    sanmar.promostandards.invoices.available_since(datetime(2026, 9, 24, tzinfo=UTC))

    assert sent(transport, 0)[1] == {
        "wsVersion": "1.0.0",
        "id": USERNAME,
        "password": PASSWORD,
        "queryType": "1",
        "referenceNumber": "112233445",
    }
    assert (sent(transport, 1)[1]["queryType"], sent(transport, 1)[1]["requestedDate"]) == ("3", "2026-09-24")
    assert (sent(transport, 2)[1]["queryType"], sent(transport, 2)[1]["availableTimeStamp"]) == (
        "4",
        "2026-09-24T00:00:00Z",
    )
