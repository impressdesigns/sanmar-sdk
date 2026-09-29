"""Testing SanMar's PromoStandards Purchase Order service against its recorded WSDL."""

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from sanmar_sdk import AuthenticationError, ResponseError, ShipMethod, ShipTo, Warehouse
from sanmar_sdk.promostandards import PromoStandardsOrder, PromoStandardsOrderLine

from .replay import PASSWORD, USERNAME, envelope, replay_client, sent, service_message

NAMESPACES = (
    'xmlns:ns2="http://www.promostandards.org/WSDL/PO/1.0.0/" '
    'xmlns="http://www.promostandards.org/WSDL/PO/1.0.0/SharedObjects/"'
)
ACCEPTED = envelope(
    f"<ns2:SendPOResponse {NAMESPACES}>"
    "<ns2:transactionId>85496-p-5877-1679510682389</ns2:transactionId></ns2:SendPOResponse>",
)
SHIP_TO = ShipTo(
    address1="1404 W MAIN ST",
    city="CARROLLTON",
    state="TX",
    zip_code="75006",
    company="IMPRESS DESIGNS",
    attention="85496",
    address2="STE 100",
    email="orders@example.com",
    phone="9725550100",
)


def _order(**changes: Any) -> PromoStandardsOrder:  # noqa: ANN401
    fields: dict[str, Any] = {
        "po_number": "85496",
        "ship_to": SHIP_TO,
        "ship_method": ShipMethod.UPS_GROUND,
        "lines": [
            PromoStandardsOrderLine(part_id="92032", quantity=12),
            PromoStandardsOrderLine(part_id="92033", quantity=6, warehouse=Warehouse.DALLAS),
            PromoStandardsOrderLine(part_id="92032", quantity=3),
        ],
        "order_date": datetime(2026, 9, 29, 12, tzinfo=UTC),
    }
    return PromoStandardsOrder(**(fields | changes))


def _part(part_id: str, quantity: int) -> dict[str, object]:
    return {"partId": part_id, "customerSupplied": "false", "Quantity": {"uom": "EA", "value": str(quantity)}}


def _line(number: int, part_id: str, quantity: int, **extra: str) -> dict[str, object]:
    return {
        "lineNumber": str(number),
        "description": part_id,
        "lineType": "New",
        **extra,
        "ToleranceDetails": {"tolerance": "ExactOnly"},
        "allowPartialShipments": "false",
        "lineItemTotal": "0",
        "PartArray": {"Part": _part(part_id, quantity)},
    }


def test_order_is_shaped_with_every_required_field() -> None:
    """The order goes out merged, with every field PromoStandards requires filled in."""
    sanmar, transport = replay_client()
    transport.queue(ACCEPTED)

    transaction_id = sanmar.promostandards.purchase_orders.send(_order())

    assert transaction_id == "85496-p-5877-1679510682389"
    assert sent(transport) == (
        "SendPORequest",
        {
            "wsVersion": "1.0.0",
            "id": USERNAME,
            "password": PASSWORD,
            "PO": {
                "orderType": "Blank",
                "orderNumber": "85496",
                "orderDate": "2026-09-29T12:00:00Z",
                "totalAmount": "0",
                "rush": "false",
                "currency": "USD",
                "ShipmentArray": {
                    "Shipment": {
                        "shipReferences": "85496",
                        "allowConsolidation": "false",
                        "blindShip": "false",
                        "packingListRequired": "false",
                        "FreightDetails": {"carrier": "UPS", "service": "Ground"},
                        "ShipTo": {
                            "customerPickup": "false",
                            "ContactDetails": {
                                "attentionTo": "85496",
                                "companyName": "IMPRESS DESIGNS",
                                "address1": "1404 W MAIN ST",
                                "address2": "STE 100",
                                "city": "CARROLLTON",
                                "region": "TX",
                                "postalCode": "75006",
                                "country": "US",
                                "email": "orders@example.com",
                                "phone": "9725550100",
                            },
                            "shipmentId": "1",
                        },
                    },
                },
                "LineItemArray": {
                    "LineItem": [_line(1, "92032", 15), _line(2, "92033", 6, fobId="3")],
                },
                "termsAndConditions": "N/A",
            },
        },
    )


def test_order_collections_cannot_change_after_validation() -> None:
    """Lines and references passed as lists are kept as tuples."""
    order = _order(ship_references=["85496"])

    assert (type(order.lines), type(order.ship_references)) == (tuple, tuple)


def test_minimal_address_and_references() -> None:
    """Blank address fields are left out, and shipping references can be set."""
    sanmar, transport = replay_client()
    transport.queue(ACCEPTED)
    ship_to = ShipTo(address1="1 MAIN ST", city="DALLAS", state="TX", zip_code="75201")

    sanmar.promostandards.purchase_orders.send(
        _order(ship_to=ship_to, ship_method=ShipMethod.USPS_PRIORITY_MAIL, ship_references=["85496", "Dock 4"]),
    )

    shipment = sent(transport)[1]["PO"]["ShipmentArray"]["Shipment"]
    assert shipment["shipReferences"] == ["85496", "Dock 4"]
    assert shipment["FreightDetails"] == {"carrier": "USPS", "service": "APP"}
    assert shipment["ShipTo"]["ContactDetails"] == {
        "address1": "1 MAIN ST",
        "city": "DALLAS",
        "region": "TX",
        "postalCode": "75201",
        "country": "US",
    }


def test_order_date_defaults_to_now() -> None:
    """Without an order date, the time the order is sent is used."""
    sanmar, transport = replay_client()
    transport.queue(ACCEPTED)

    sanmar.promostandards.purchase_orders.send(_order(order_date=None))

    sent_date = datetime.fromisoformat(sent(transport)[1]["PO"]["orderDate"])
    assert abs((datetime.now(tz=UTC) - sent_date).total_seconds()) < 60  # noqa: PLR2004


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"ship_method": ShipMethod.TRUCK}, "TRUCK"),
        ({"po_number": "85,496"}, "commas"),
        ({"po_number": "X" * 29}, "at most 28"),
        ({"ship_references": ["a", "b", "c"]}, "at most 2"),
        ({"lines": []}, "at least 1"),
    ],
)
def test_orders_sanmar_would_refuse_fail_when_built(changes: dict[str, Any], match: str) -> None:
    """Orders SanMar cannot take fail when they are built."""
    with pytest.raises(ValidationError, match=match):
        _order(**changes)


def test_merging_revalidates_the_total() -> None:
    """Lines that merge past the five-digit limit fail rather than go out wrong."""
    order = _order(
        lines=[
            PromoStandardsOrderLine(part_id="92032", quantity=60_000),
            PromoStandardsOrderLine(part_id="92032", quantity=60_000),
        ],
    )

    with pytest.raises(ValidationError, match="less than or equal to 99999"):
        order.merged_lines()


def test_rejected_order_raises() -> None:
    """An error in the response is raised, and a response with nothing in it is too."""
    sanmar, transport = replay_client()
    transport.queue(
        envelope(
            f"""<ns2:SendPOResponse {NAMESPACES}>
              {service_message(110, "Authentication Credentials required")}
            </ns2:SendPOResponse>""",
        ),
    )
    transport.queue(envelope(f"<ns2:SendPOResponse {NAMESPACES}/>"))

    with pytest.raises(AuthenticationError, match="110"):
        sanmar.promostandards.purchase_orders.send(_order())
    with pytest.raises(ResponseError, match="neither"):
        sanmar.promostandards.purchase_orders.send(_order())


def test_supported_order_types() -> None:
    """SanMar only takes blank orders."""
    sanmar, transport = replay_client()
    transport.queue(
        envelope(
            f"""<ns2:GetSupportedOrderTypesResponse {NAMESPACES}>
              <ns2:supportedOrderTypes>Blank</ns2:supportedOrderTypes>
            </ns2:GetSupportedOrderTypesResponse>""",
        ),
    )

    assert sanmar.promostandards.purchase_orders.supported_order_types() == ["Blank"]
    assert sent(transport) == (
        "GetSupportedOrderTypesRequest",
        {"wsVersion": "1.0.0", "id": USERNAME, "password": PASSWORD},
    )
