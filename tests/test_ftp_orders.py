"""Testing the order files uploaded to SanMar's SFTP server."""

from typing import Any

import pytest
from pydantic import ValidationError

from sanmar_sdk import ShipMethod, ShipTo, SkuKey, StyleColorSize, Warehouse, WillCall
from sanmar_sdk.ftp import render_order_files, render_release_file
from sanmar_sdk.orders import OrderLine, PurchaseOrder

GUIDE_SHIP_TO = ShipTo(
    company="My Decorator",
    attention="DANA",
    address1="123 GRIFFITH ST",
    address2="STE 202",
    city="CHARLOTTE",
    state="NC",
    zip_code="28217",
    email="sales@abco.com",
)
"""The ship-to in the Purchase Order Integration Guide's CustInfo.txt example."""


def _order(*lines: OrderLine, **changes: Any) -> PurchaseOrder:  # noqa: ANN401 - forwarded to the model
    """Build the guide's example order, with the given lines."""
    fields: dict[str, Any] = {
        "po_number": "FX34689",
        "ship_to": GUIDE_SHIP_TO,
        "ship_method": ShipMethod.UPS_GROUND,
        "lines": lines or (OrderLine(item=SkuKey(inventory_key=1003, size_index=3), quantity=10),),
    }
    return PurchaseOrder.model_validate({**fields, **changes})


def test_order_files_match_the_guide_examples() -> None:
    """The rendered rows are exactly the ones the guide shows."""
    files = render_order_files("06-07-2022-1", [_order()])

    assert (files.cust_info_name, files.details_name) == ("06-07-2022-1CustInfo.txt", "06-07-2022-1Details.txt")
    assert (
        files.cust_info
        == "FX34689,123 GRIFFITH ST,STE 202,CHARLOTTE,NC,28217,UPS,sales@abco.com,N,,,My Decorator,,DANA\r\n"
    )
    assert files.details == "FX34689,1003,10,3\r\n"


def test_duplicate_lines_are_combined() -> None:
    """Two lines for the same item become one, as the guide's consolidation example shows."""
    line = OrderLine(item=SkuKey(inventory_key=1003, size_index=3), quantity=10)
    assert render_order_files("b-1", [_order(line, line)]).details == "FX34689,1003,20,3\r\n"


def test_lines_keep_their_warehouses_apart() -> None:
    """The same item from two warehouses stays two lines, each naming its warehouse."""
    item = SkuKey(inventory_key=1003, size_index=3)
    files = render_order_files(
        "b-1",
        [
            _order(
                OrderLine(item=item, quantity=10, warehouse=Warehouse.SEATTLE),
                OrderLine(item=item, quantity=5, warehouse=Warehouse.RICHMOND),
                OrderLine(item=item, quantity=1, warehouse=Warehouse.SEATTLE),
            ),
        ],
    )
    assert files.details == "FX34689,1003,11,3,1\r\nFX34689,1003,5,3,31\r\n"


def test_combined_quantity_is_still_checked() -> None:
    """Combining lines cannot produce a quantity the order files cannot hold."""
    line = OrderLine(item=SkuKey(inventory_key=1003, size_index=3), quantity=60_000)
    with pytest.raises(ValidationError, match="less than or equal to 99999"):
        _order(line, line).merged_lines()


def test_will_call_uses_the_warehouse_code() -> None:
    """A will-call order ships to the warehouse code, flagged as the guide's example does."""
    files = render_order_files("b-1", [_order(ship_method=WillCall(warehouse=Warehouse.RENO))])
    assert files.cust_info.split(",")[6] == "REN"
    assert files.cust_info.split(",")[12] == "W"


def test_residential_addresses_are_flagged() -> None:
    """A residential ship-to sets RESIDENCE to Y."""
    ship_to = GUIDE_SHIP_TO.model_copy(update={"residential": True})
    assert render_order_files("b-1", [_order(ship_to=ship_to)]).cust_info.split(",")[8] == "Y"


def test_several_orders_share_a_batch() -> None:
    """Every order in a batch gets its own CustInfo row and its own Details rows."""
    second = _order(po_number="FX34690", lines=[OrderLine(item=SkuKey(inventory_key=9203, size_index=2), quantity=4)])
    files = render_order_files("b-1", [_order(), second])
    assert files.cust_info.count("\r\n") == 2  # noqa: PLR2004
    assert files.details == "FX34689,1003,10,3\r\nFX34690,9203,4,2\r\n"


@pytest.mark.parametrize(
    ("batch", "orders", "problem"),
    [
        ("06/07/2022", [_order()], "letters, digits and dashes"),
        ("b-1", [], "at least one purchase order"),
        ("b-1", [_order(), _order()], "its own PO number"),
        ("b-1", [_order(ship_to=GUIDE_SHIP_TO.model_copy(update={"email": None}))], "ship-to email"),
        ("b-1", [_order(OrderLine(item=SkuKey(inventory_key=1234567, size_index=1), quantity=1))], "too long"),
    ],
    ids=["batch-name", "no-orders", "duplicate-po", "no-email", "long-key"],
)
def test_order_files_refuse_what_sanmar_would(batch: str, orders: list[PurchaseOrder], problem: str) -> None:
    """Batches SanMar would reject fail before anything is uploaded."""
    with pytest.raises(ValueError, match=problem):
        render_order_files(batch, orders)


def test_order_files_need_inventory_keys() -> None:
    """Details.txt has no room for a style, color and size."""
    line = OrderLine(item=StyleColorSize(style="K500", catalog_color="Black", size="L"), quantity=1)
    with pytest.raises(TypeError, match="inventory key and size index only"):
        render_order_files("b-1", [_order(line)])


def test_release_files_are_numbered() -> None:
    """Each release of a batch names its PO numbers and carries its release number."""
    assert render_release_file("06-07-2022-1", ["FX34689"]) == ("06-07-2022-1Release1.txt", "FX34689\r\n")
    assert render_release_file("06-07-2022-1", ["A", "B"], release_number=2) == (
        "06-07-2022-1Release2.txt",
        "A\r\nB\r\n",
    )
    with pytest.raises(ValueError, match="at least one PO number"):
        render_release_file("b-1", [])
    with pytest.raises(ValueError, match="start at 1"):
        render_release_file("b-1", ["A"], release_number=0)
