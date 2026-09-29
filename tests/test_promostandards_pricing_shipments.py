"""Testing SanMar's PromoStandards Pricing and Shipment Notification services against their recorded WSDLs."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from sanmar_sdk import NotFoundError, RequestError, Warehouse
from sanmar_sdk.promostandards import PriceType

from .replay import PASSWORD, USERNAME, envelope, replay_client, sent

PRICING = (
    'xmlns:ns2="http://www.promostandards.org/WSDL/PricingAndConfiguration/1.0.0/" '
    'xmlns="http://www.promostandards.org/WSDL/PricingAndConfiguration/1.0.0/SharedObjects/"'
)
SHIPMENTS = (
    'xmlns:ns2="http://www.promostandards.org/WSDL/OrderShipmentNotificationService/1.0.0/" '
    'xmlns="http://www.promostandards.org/WSDL/OrderShipmentNotificationService/1.0.0/SharedObjects/"'
)


def test_prices_for_a_part() -> None:
    """A part's price breaks come back typed, and every required field is sent."""
    sanmar, transport = replay_client()
    transport.queue(
        envelope(
            f"""<ns2:GetConfigurationAndPricingResponse {PRICING}>
              <ns2:Configuration>
                <ns2:PartArray>
                  <ns2:Part>
                    <partId>240831</partId>
                    <ns2:PartPriceArray>
                      <ns2:PartPrice>
                        <ns2:minQuantity>1</ns2:minQuantity><ns2:price>8.99</ns2:price><ns2:priceUom>CA</ns2:priceUom>
                        <ns2:priceEffectiveDate>2026-05-19T12:51:32.780</ns2:priceEffectiveDate>
                        <ns2:priceExpiryDate>2026-05-19T23:59:59.000</ns2:priceExpiryDate>
                      </ns2:PartPrice>
                    </ns2:PartPriceArray>
                    <partGroup>1</partGroup><partGroupRequired>false</partGroupRequired>
                    <partGroupDescription>NA</partGroupDescription><ratio>1</ratio><defaultPart>false</defaultPart>
                  </ns2:Part>
                </ns2:PartArray>
                <productId>K500</productId><currency>USD</currency>
                <FobArray><Fob><fobId>6</fobId><fobPostalCode>32219</fobPostalCode></Fob></FobArray>
                <priceType>Net</priceType>
              </ns2:Configuration>
            </ns2:GetConfigurationAndPricingResponse>""",
        ),
    )

    [part] = sanmar.promostandards.pricing.get("K500", part_id="240831", price_type=PriceType.LIST)

    assert sent(transport) == (
        "GetConfigurationAndPricingRequest",
        {
            "wsVersion": "1.0.0",
            "id": USERNAME,
            "password": PASSWORD,
            "productId": "K500",
            "partId": "240831",
            "currency": "USD",
            "fobId": "1",
            "priceType": "List",
            "localizationCountry": "US",
            "localizationLanguage": "EN",
            "configurationType": "Blank",
        },
    )
    [price] = part.prices
    assert (part.part_id, price.min_quantity, price.price, price.uom) == ("240831", 1, Decimal("8.99"), "CA")


def test_pricing_error_message_is_raised() -> None:
    """Pricing reports errors as an upper-case ErrorMessage."""
    sanmar, transport = replay_client()
    transport.queue(
        envelope(
            f"""<ns2:GetConfigurationAndPricingResponse {PRICING}>
              <ErrorMessage>
                <code>120</code><description>The following field(s) are required [fobId]</description>
              </ErrorMessage>
            </ns2:GetConfigurationAndPricingResponse>""",
        ),
    )

    with pytest.raises(RequestError, match="fobId"):
        sanmar.promostandards.pricing.get("K500", warehouse=Warehouse.RICHMOND)
    assert sent(transport)[1]["fobId"] == "31"


def test_fob_points() -> None:
    """FOB points are SanMar's warehouses, with the currencies priced from them."""
    sanmar, transport = replay_client()
    transport.queue(
        envelope(
            f"""<ns2:GetFobPointsResponse {PRICING}>
              <ns2:FobPointArray>
                <ns2:FobPoint>
                  <fobId>1</fobId><ns2:fobCity>Seattle</ns2:fobCity><ns2:fobState>WA</ns2:fobState>
                  <fobPostalCode>98027</fobPostalCode><ns2:fobCountry>US</ns2:fobCountry>
                  <ns2:CurrencySupportedArray><ns2:CurrencySupported><currency>USD</currency></ns2:CurrencySupported></ns2:CurrencySupportedArray>
                  <ns2:ProductArray><ns2:Product><productId>k500</productId></ns2:Product></ns2:ProductArray>
                </ns2:FobPoint>
              </ns2:FobPointArray>
            </ns2:GetFobPointsResponse>""",
        ),
    )

    [point] = sanmar.promostandards.pricing.fob_points("K500")

    assert sent(transport)[0] == "GetFobPointsRequest"
    assert (point.warehouse, point.city, point.currencies) == (Warehouse.SEATTLE, "Seattle", ["USD"])


def _address(city: str) -> str:
    return (
        f"<address1>1 Main St</address1><city>{city}</city><region>TX</region>"
        "<postalCode>75038</postalCode><country>US</country>"
    )


# Shaped like the Web Services Integration Guide's sample response.
SHIPPED = envelope(
    f"""<ns2:GetOrderShipmentNotificationResponse {SHIPMENTS}>
      <ns2:OrderShipmentNotificationArray>
        <ns2:OrderShipmentNotification>
          <ns2:purchaseOrderNumber>85496</ns2:purchaseOrderNumber>
          <ns2:complete>true</ns2:complete>
          <ns2:SalesOrderArray>
            <ns2:SalesOrder>
              <ns2:salesOrderNumber>1112223334</ns2:salesOrderNumber>
              <ns2:complete>true</ns2:complete>
              <ns2:ShipmentLocationArray>
                <ns2:ShipmentLocation>
                  <ns2:id>1</ns2:id><ns2:complete>true</ns2:complete>
                  <ns2:ShipFromAddress>{_address("IRVING")}</ns2:ShipFromAddress>
                  <ns2:ShipToAddress>{_address("CARROLLTON")}</ns2:ShipToAddress>
                  <ns2:shipmentDestinationType>Commercial</ns2:shipmentDestinationType>
                  <ns2:PackageArray>
                    <ns2:Package>
                      <ns2:id>1</ns2:id><ns2:trackingNumber>1Z999AA10123456784</ns2:trackingNumber>
                      <ns2:shipmentDate>2026-09-24T22:44:42.467-07:00</ns2:shipmentDate>
                      <ns2:carrier>UPS</ns2:carrier><ns2:shipmentMethod>Ground</ns2:shipmentMethod>
                      <ns2:ItemArray>
                        <ns2:Item>
                          <ns2:supplierProductId>PC55P</ns2:supplierProductId><ns2:supplierPartId>834732</ns2:supplierPartId>
                          <ns2:quantity>12</ns2:quantity>
                        </ns2:Item>
                      </ns2:ItemArray>
                    </ns2:Package>
                  </ns2:PackageArray>
                </ns2:ShipmentLocation>
              </ns2:ShipmentLocationArray>
            </ns2:SalesOrder>
          </ns2:SalesOrderArray>
        </ns2:OrderShipmentNotification>
      </ns2:OrderShipmentNotificationArray>
    </ns2:GetOrderShipmentNotificationResponse>""",
)


def test_shipments_by_purchase_order() -> None:
    """A purchase order's shipments come back with their packages and tracking numbers."""
    sanmar, transport = replay_client()
    transport.queue(SHIPPED)

    [notification] = sanmar.promostandards.shipment_notifications.by_purchase_order("85496")

    assert sent(transport) == (
        "GetOrderShipmentNotificationRequest",
        {"wsVersion": "1.0.0", "id": USERNAME, "password": PASSWORD, "queryType": "1", "referenceNumber": "85496"},
    )
    assert (notification.po_number, notification.complete) == ("85496", True)
    assert notification.tracking_numbers == ["1Z999AA10123456784"]
    location = notification.sales_orders[0].locations[0]
    assert (location.ship_from.city, location.ship_to.city, location.destination_type) == (
        "IRVING",
        "CARROLLTON",
        "Commercial",
    )
    [item] = location.packages[0].items
    assert (item.product_id, item.part_id, item.quantity) == ("PC55P", "834732", Decimal(12))


def test_shipments_by_sales_order_and_date() -> None:
    """Sales order and date queries send their own query types."""
    sanmar, transport = replay_client()
    transport.queue(SHIPPED)
    transport.queue(SHIPPED)
    since = datetime.now(tz=UTC).replace(microsecond=0) - timedelta(days=2)

    sanmar.promostandards.shipment_notifications.by_sales_order("1112223334")
    sanmar.promostandards.shipment_notifications.since(since)

    assert sent(transport, 0)[1]["queryType"] == "2"
    assert sent(transport, 1)[1]["queryType"] == "3"
    assert sent(transport, 1)[1]["shipmentDateTimeStamp"] == since.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert "referenceNumber" not in sent(transport, 1)[1]


@pytest.mark.parametrize(
    ("since", "match"),
    [
        (datetime.now(tz=UTC) - timedelta(days=8), "7 days"),
        (datetime(2026, 9, 28), "time zone"),  # noqa: DTZ001 - the mistake being tested
    ],
)
def test_shipment_dates_sanmar_would_refuse_fail_up_front(since: datetime, match: str) -> None:
    """Dates more than a week back, or without a time zone, fail before anything is sent."""
    sanmar, transport = replay_client()

    with pytest.raises(ValueError, match=match):
        sanmar.promostandards.shipment_notifications.since(since)
    assert transport.sent == []


def test_unshipped_order_explains_the_wait() -> None:
    """Code 301 is a NotFoundError that says how long SanMar can take."""
    sanmar, transport = replay_client()
    transport.queue(
        envelope(
            f"""<ns2:GetOrderShipmentNotificationResponse {SHIPMENTS}>
              <errorMessage><code>301</code><description>Reference Number not found</description></errorMessage>
            </ns2:GetOrderShipmentNotificationResponse>""",
        ),
    )

    with pytest.raises(NotFoundError, match="24 hours") as raised:
        sanmar.promostandards.shipment_notifications.by_purchase_order("85496")
    assert raised.value.code == 301  # noqa: PLR2004
