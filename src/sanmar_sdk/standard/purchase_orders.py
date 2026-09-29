"""SanMar's own purchase order service.

:meth:`PurchaseOrderService.check` asks SanMar whether an order could ship, and from which
warehouses, without placing it. :meth:`PurchaseOrderService.submit` places it. Both take
the :class:`~sanmar_sdk.orders.PurchaseOrder` that SFTP ordering takes too.

SanMar needs an account set up for integrated ordering before it accepts orders here, and
tests new integrations on EDEV first; see the Purchase Order Integration Guide.
"""

from typing import TYPE_CHECKING

from pydantic import Field

from sanmar_sdk._soap import PURCHASE_ORDER, Service
from sanmar_sdk.base import OneOrMany, Record
from sanmar_sdk.common import SkuKey, StyleColorSize, WarehouseNumber, WillCall

from ._common import raise_error, web_service_user

if TYPE_CHECKING:
    from sanmar_sdk.orders import PurchaseOrder

    from ._wire import PurchaseOrder as PurchaseOrderPayload
    from ._wire import PurchaseOrderLine


class LineAvailability(Record):
    """Whether one line of an order could ship, and from where."""

    style: str | None = None
    catalog_color: str | None = Field(default=None, validation_alias="color")
    size: str | None = None
    inventory_key: int | None = Field(default=None, validation_alias="inventoryKey")
    size_index: int | None = Field(default=None, validation_alias="sizeIndex")
    quantity: int
    warehouse: WarehouseNumber | None = Field(default=None, validation_alias="whseNo")
    """The warehouse SanMar would ship this line from."""
    error: bool = Field(default=False, validation_alias="errorOccured")
    message: str | None = None
    """SanMar's explanation, such as which warehouse has the stock."""

    @property
    def available(self) -> bool:
        """Whether the requested quantity is in stock."""
        return not self.error

    def matches(self, item: SkuKey | StyleColorSize) -> bool:
        """Whether this line is for the given item."""
        if isinstance(item, SkuKey):
            return (self.inventory_key, self.size_index) == (item.inventory_key, item.size_index)
        mine = [(value or "").casefold() for value in (self.style, self.catalog_color, self.size)]
        return mine == [item.style.casefold(), item.catalog_color.casefold(), item.size.casefold()]


class OrderCheck(Record):
    """SanMar's answer to whether an order could ship as it stands."""

    available: bool
    """Whether every line is in stock."""
    message: str | None = None
    lines: OneOrMany[LineAvailability] = Field(default_factory=list)

    def line_for(self, item: SkuKey | StyleColorSize) -> LineAvailability | None:
        """Find the line for an item, or ``None`` if the order has no line for it."""
        return next((line for line in self.lines if line.matches(item)), None)


def _line(item: SkuKey | StyleColorSize, quantity: int, warehouse: int | None) -> PurchaseOrderLine:
    line: PurchaseOrderLine = {"quantity": quantity}
    if isinstance(item, SkuKey):
        line["inventoryKey"] = str(item.inventory_key)
        line["sizeIndex"] = item.size_index
    else:
        line["style"] = item.style
        line["color"] = item.catalog_color
        line["size"] = item.size
    if warehouse is not None:
        line["whseNo"] = warehouse
    return line


def _shape_purchase_order(order: PurchaseOrder) -> PurchaseOrderPayload:
    """Shape an order as SanMar's purchase order service takes it.

    Duplicate lines are combined, and the fields SanMar says to leave blank are left out.
    """
    ship_to = order.ship_to
    payload: PurchaseOrderPayload = {
        "poNum": order.po_number,
        "shipAddress1": ship_to.address1,
        "shipCity": ship_to.city,
        "shipState": ship_to.state,
        "shipZip": ship_to.zip_code,
        "shipMethod": order.ship_method.ship_method
        if isinstance(order.ship_method, WillCall)
        else order.ship_method.value,
        "residence": "Y" if ship_to.residential else "N",
        "webServicePoDetailList": [
            _line(line.item, line.quantity, None if line.warehouse is None else int(line.warehouse))
            for line in order.merged_lines()
        ],
    }
    if ship_to.attention is not None:
        payload["attention"] = ship_to.attention
    if ship_to.address2 is not None:
        payload["shipAddress2"] = ship_to.address2
    if ship_to.email is not None:
        payload["shipEmail"] = ship_to.email
    if ship_to.company is not None:
        payload["shipTo"] = ship_to.company
    return payload


class PurchaseOrderService(Service):
    """SanMar's own purchase order service."""

    def check(self, order: PurchaseOrder) -> OrderCheck:
        """Ask whether an order could ship, and from where, without placing it.

        Being out of stock is an answer, not an error: see :attr:`OrderCheck.available`
        and each line's message.
        """
        result = self._soap.call(
            PURCHASE_ORDER,
            ("getPreSubmitInfo",),
            {"arg0": _shape_purchase_order(order), "arg1": web_service_user(self._credentials)},
        )
        response = result.get("response")
        if response is None:
            if result.get("errorOccurred"):
                raise_error(result.get("message"))
            response = {}
        return OrderCheck.model_validate(
            {
                "available": not result.get("errorOccurred"),
                "message": result.get("message"),
                "lines": response.get("webServicePoDetailList") or [],
            },
        )

    def submit(self, order: PurchaseOrder) -> str:
        """Place an order. Returns SanMar's confirmation message.

        SanMar ships each line from the warehouses its shipping option for the account
        picks, unless a line names one. Check an order first with :meth:`check` if the
        account splits orders across warehouses.
        """
        result = self._soap.call(
            PURCHASE_ORDER,
            ("submitPO",),
            {"arg0": _shape_purchase_order(order), "arg1": web_service_user(self._credentials)},
        )
        message = result.get("message")
        if result.get("errorOccurred"):
            raise_error(message)
        return str(message or "")
