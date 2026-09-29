"""Purchase orders for SanMar's own order channels.

A :class:`PurchaseOrder` is placed through SanMar's standard purchase order web service or
uploaded as order files to SanMar's SFTP server; both take the same fields. PromoStandards
orders carry a different set of fields and are modelled separately.
"""

from collections.abc import Sequence
from typing import Annotated

from pydantic import Field

from .base import FROZEN, ORDER_TEXT, Model
from .common import ShipMethod, ShipTo, SkuKey, StyleColorSize, Warehouse, WillCall

type PONumber = Annotated[str, Field(min_length=1, max_length=28), ORDER_TEXT]
"""A purchase order number as SanMar takes it, up to 28 characters of printable ASCII without commas."""


class OrderLine(Model):
    """One item on a purchase order.

    Name the item by :class:`~sanmar_sdk.common.SkuKey` where you can. SanMar recommends it,
    and the SFTP order files accept nothing else. By
    :class:`~sanmar_sdk.common.StyleColorSize`, the color must be the catalog color.
    """

    item: SkuKey | StyleColorSize
    quantity: int = Field(gt=0, le=99_999)
    """How many pieces. The SFTP order files allow up to five digits."""
    warehouse: Warehouse | None = None
    """The warehouse to ship this line from.

    Leave it unset unless SanMar has set your account up for warehouse selection; otherwise
    SanMar picks warehouses according to the shipping option on your account.
    """


class PurchaseOrder(Model):
    """A purchase order for SanMar's standard order service or SFTP order files."""

    po_number: PONumber
    ship_to: ShipTo
    ship_method: ShipMethod | WillCall
    lines: Annotated[Sequence[OrderLine], Field(min_length=1), FROZEN]

    def merged_lines(self) -> list[OrderLine]:
        """Return the lines with duplicates combined, as SanMar asks.

        SanMar checks inventory line by line, so two lines for the same item and warehouse
        can each pass on their own while their total is short. Lines are combined on item
        and warehouse, keeping the order each first appeared in.
        """
        merged: dict[tuple[SkuKey | StyleColorSize, Warehouse | None], OrderLine] = {}
        for line in self.lines:
            key = (line.item, line.warehouse)
            if key in merged:
                total = merged[key].quantity + line.quantity
                merged[key] = OrderLine(item=line.item, quantity=total, warehouse=line.warehouse)
            else:
                merged[key] = line
        return list(merged.values())
