"""Testing SanMar's own purchase order service against its recorded WSDL."""

from typing import Any

import pytest
from pydantic import ValidationError

from sanmar_sdk import (
    AuthenticationError,
    ServiceError,
    ShipMethod,
    ShipTo,
    SkuKey,
    StyleColorSize,
    Warehouse,
    WillCall,
)
from sanmar_sdk.orders import OrderLine, PurchaseOrder
from sanmar_sdk.promostandards import PromoStandardsOrder, PromoStandardsOrderLine

from .replay import CUSTOMER_NUMBER, PASSWORD, USERNAME, envelope, replay_client, sent

LOGIN = {"sanMarCustomerNumber": str(CUSTOMER_NUMBER), "sanMarUserName": USERNAME, "sanMarUserPassword": PASSWORD}
K500_BLACK_L = SkuKey(inventory_key=20828, size_index=4)
K420_BLACK_S = StyleColorSize(style="K420", catalog_color="Black", size="S")

ORDER = PurchaseOrder(
    po_number="WEBSERVICES TEST",
    ship_to=ShipTo(
        company="SanMar Corporation",
        attention="SanMar Integrations",
        address1="22833 SE Black Nugget Rd",
        address2="STE 130",
        city="Issaquah",
        state="WA",
        zip_code="98029",
        email="sanmarintegrations@sanmar.com",
    ),
    ship_method=ShipMethod.UPS_GROUND,
    lines=[
        OrderLine(item=K500_BLACK_L, quantity=5),
        OrderLine(item=K420_BLACK_S, quantity=900),
        OrderLine(item=K500_BLACK_L, quantity=7),
    ],
)


def _response(operation: str, error: bool, message: str, po: str = "") -> str:  # noqa: FBT001
    response = f'<response xsi:type="ns2:webServicePO">{po}</response>' if po else ""
    return envelope(
        f"""<ns2:{operation}Response xmlns:ns2="http://webservice.integration.sanmar.com/">
          <return><errorOccurred>{str(error).lower()}</errorOccurred><message>{message}</message>{response}</return>
        </ns2:{operation}Response>""",
    )


CHECKED = """<poNum>WEBSERVICES TEST</poNum><residence>N</residence>
  <webServicePoDetailList><color>Black</color><errorOccured>false</errorOccured><inventoryKey>20828</inventoryKey>
    <message>Requested Quantity is confirmed and available in warehouse '1' to ship to your destination.</message>
    <quantity>12</quantity><size>L</size><sizeIndex>4</sizeIndex><style>K500</style><whseNo>1</whseNo>
  </webServicePoDetailList>
  <webServicePoDetailList><color>Black</color><errorOccured>true</errorOccured><inventoryKey>9203</inventoryKey>
    <message>Requested Quantity is not in stock from any warehouse or from requested warehouse</message>
    <quantity>900</quantity><size>S</size><sizeIndex>2</sizeIndex><style>K420</style>
  </webServicePoDetailList>"""


def test_orders_without_a_country_field_take_us_addresses_only() -> None:
    """SanMar's own channels would drop a foreign country; PromoStandards sends it."""
    abroad = ORDER.ship_to.model_copy(update={"country": "CA"})

    with pytest.raises(ValidationError, match="US addresses only, not CA"):
        PurchaseOrder(po_number="1", ship_to=abroad, ship_method=ShipMethod.UPS_GROUND, lines=ORDER.lines)
    order = PromoStandardsOrder(
        po_number="1",
        ship_to=abroad,
        ship_method=ShipMethod.UPS_GROUND,
        lines=[PromoStandardsOrderLine(part_id="208284", quantity=1)],
    )
    assert order.ship_to.country == "CA"


def test_order_lines_cannot_change_after_validation() -> None:
    """Lines passed as a list are kept as a tuple, so emptying them cannot bypass validation."""
    assert isinstance(ORDER.lines, tuple)
    with pytest.raises(AttributeError):
        ORDER.lines.clear()  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]


def test_order_is_shaped_as_sanmar_takes_it() -> None:
    """Lines are combined, keys and styles go in their own fields, and blank fields are left out."""
    sanmar, transport = replay_client()
    transport.queue(_response("submitPO", error=False, message="PO Submission successful"))

    assert sanmar.purchase_orders.submit(ORDER) == "PO Submission successful"

    assert sent(transport) == (
        "submitPO",
        {
            "arg0": {
                "attention": "SanMar Integrations",
                "poNum": "WEBSERVICES TEST",
                "residence": "N",
                "shipAddress1": "22833 SE Black Nugget Rd",
                "shipAddress2": "STE 130",
                "shipCity": "Issaquah",
                "shipEmail": "sanmarintegrations@sanmar.com",
                "shipMethod": "UPS",
                "shipState": "WA",
                "shipTo": "SanMar Corporation",
                "shipZip": "98029",
                "webServicePoDetailList": [
                    {"inventoryKey": "20828", "quantity": "12", "sizeIndex": "4"},
                    {"color": "Black", "quantity": "900", "size": "S", "style": "K420"},
                ],
            },
            "arg1": LOGIN,
        },
    )


def test_minimal_will_call_order() -> None:
    """A will-call order ships to the warehouse code; unset optional fields are not sent."""
    sanmar, transport = replay_client()
    transport.queue(_response("submitPO", error=False, message="PO Submission successful"))
    order = PurchaseOrder(
        po_number="PICKUP-1",
        ship_to=ShipTo(address1="1404 W Main St", city="Carrollton", state="TX", zip_code="75006", residential=True),
        ship_method=WillCall(warehouse=Warehouse.DALLAS),
        lines=[OrderLine(item=K500_BLACK_L, quantity=1, warehouse=Warehouse.DALLAS)],
    )

    sanmar.purchase_orders.submit(order)

    payload: dict[str, Any] = sent(transport)[1]["arg0"]
    assert (payload["shipMethod"], payload["residence"]) == ("COP", "Y")
    assert payload["webServicePoDetailList"] == {
        "inventoryKey": "20828",
        "quantity": "1",
        "sizeIndex": "4",
        "whseNo": "3",
    }
    assert not {"attention", "shipAddress2", "shipEmail", "shipTo", "notes", "department"} & payload.keys()


def test_check_reports_each_line() -> None:
    """A check says, line by line, where stock is and where it is not, without raising."""
    sanmar, transport = replay_client()
    transport.queue(
        _response(
            "getPreSubmitInfo",
            error=True,
            message="Requested Quantity is not in stock from any warehouse or from the requested warehouse",
            po=CHECKED,
        ),
    )

    check = sanmar.purchase_orders.check(ORDER)

    assert sent(transport)[0] == "getPreSubmitInfo"
    assert not check.available
    in_stock = check.line_for(K500_BLACK_L)
    short = check.line_for(K420_BLACK_S)
    assert in_stock is not None
    assert short is not None
    assert (in_stock.available, in_stock.warehouse, in_stock.quantity) == (True, Warehouse.SEATTLE, 12)
    assert (short.available, short.warehouse) == (False, None)
    assert check.line_for(SkuKey(inventory_key=1, size_index=1)) is None


def test_check_matches_style_lines_regardless_of_case() -> None:
    """SanMar echoes styles and colors in its own case."""
    sanmar, transport = replay_client()
    transport.queue(
        _response("getPreSubmitInfo", error=False, message="Information returned successfully", po=CHECKED),
    )

    check = sanmar.purchase_orders.check(ORDER)

    assert check.available
    assert check.line_for(StyleColorSize(style="k420", catalog_color="BLACK", size="s")) is not None


def test_check_with_a_rejected_login_raises() -> None:
    """A failure with no order echoed back is an error, not an availability answer."""
    sanmar, transport = replay_client()
    transport.queue(_response("getPreSubmitInfo", error=True, message="ERROR: User authenticating failed "))

    with pytest.raises(AuthenticationError):
        sanmar.purchase_orders.check(ORDER)


def test_submit_failure_raises() -> None:
    """A rejected order raises with SanMar's message."""
    sanmar, transport = replay_client()
    transport.queue(_response("submitPO", error=True, message="Error: PO number already exists"))

    with pytest.raises(ServiceError, match="PO number already exists"):
        sanmar.purchase_orders.submit(ORDER)
