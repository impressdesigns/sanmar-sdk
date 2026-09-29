"""SanMar's PromoStandards Purchase Order service, version 1.0.0.

Places orders by part: SanMar's unique key for each style, color and size. The
PromoStandards schema requires many fields SanMar ignores, such as totals, tolerances and
consolidation flags; the SDK fills those in, and leaves out everything SanMar says not to
send. Only blank goods can be ordered, and there is no will call or truck freight here; use
the standard purchase order service (:mod:`sanmar_sdk.standard.purchase_orders`) for those.

SanMar needs an account set up for integrated ordering before it accepts orders, and
tests new integrations on EDEV first; see the Purchase Order Integration Guide.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from pydantic import Field, field_validator

from sanmar_sdk._soap import PROMOSTANDARDS_PURCHASE_ORDER
from sanmar_sdk.base import FROZEN, ORDER_TEXT, Model
from sanmar_sdk.common import ShipMethod, ShipTo, Warehouse
from sanmar_sdk.exceptions import ResponseError

from ._common import PromoStandardsService, check

if TYPE_CHECKING:
    from ._wire import ContactDetails, LineItem
    from ._wire import PurchaseOrder as PurchaseOrderPayload

NOT_USED = "N/A"
"""What goes in the text fields PromoStandards requires and SanMar does not use."""


class PromoStandardsOrderLine(Model):
    """One part on a PromoStandards purchase order."""

    part_id: Annotated[str, Field(min_length=1, max_length=64), ORDER_TEXT]
    """SanMar's unique key for the style, color and size (``UNIQUE_KEY`` in its files)."""
    quantity: int = Field(gt=0, le=99_999)
    warehouse: Warehouse | None = None
    """The warehouse to ship this line from.

    Leave it unset unless SanMar has set your account up for warehouse selection; otherwise
    SanMar picks warehouses according to the shipping option on your account.
    """


class PromoStandardsOrder(Model):
    """A purchase order for SanMar's PromoStandards purchase order service."""

    po_number: Annotated[str, Field(min_length=1, max_length=28), ORDER_TEXT]
    ship_to: ShipTo
    ship_method: ShipMethod
    lines: Annotated[Sequence[PromoStandardsOrderLine], Field(min_length=1), FROZEN]
    order_date: datetime | None = None
    """When the order was placed. Defaults to the time it is sent."""
    ship_references: Annotated[
        Sequence[Annotated[str, Field(min_length=1, max_length=64), ORDER_TEXT]],
        Field(max_length=2),
        FROZEN,
    ] = ()
    """Up to two references for the shipping process. Defaults to the PO number."""

    @field_validator("ship_method")
    @classmethod
    def _offered_through_promostandards(cls, value: ShipMethod) -> ShipMethod:
        value.promostandards_freight()
        return value

    def merged_lines(self) -> list[PromoStandardsOrderLine]:
        """Return the lines with duplicates combined, keeping the order each first appeared in.

        SanMar checks inventory line by line, so two lines for the same part and warehouse
        can each pass on their own while their total is short.
        """
        merged: dict[tuple[str, Warehouse | None], PromoStandardsOrderLine] = {}
        for line in self.lines:
            key = (line.part_id, line.warehouse)
            if key in merged:
                total = merged[key].quantity + line.quantity
                merged[key] = PromoStandardsOrderLine(part_id=line.part_id, quantity=total, warehouse=line.warehouse)
            else:
                merged[key] = line
        return list(merged.values())


def _contact(ship_to: ShipTo) -> ContactDetails:
    contact: ContactDetails = {
        "address1": ship_to.address1,
        "city": ship_to.city,
        "region": ship_to.state,
        "postalCode": ship_to.zip_code,
        "country": ship_to.country,
    }
    if ship_to.attention is not None:
        contact["attentionTo"] = ship_to.attention
    if ship_to.company is not None:
        contact["companyName"] = ship_to.company
    if ship_to.address2 is not None:
        contact["address2"] = ship_to.address2
    if ship_to.email is not None:
        contact["email"] = ship_to.email
    if ship_to.phone is not None:
        contact["phone"] = ship_to.phone
    return contact


def _line_item(number: int, line: PromoStandardsOrderLine) -> LineItem:
    item: LineItem = {
        "lineNumber": number,
        "description": line.part_id,
        "lineType": "New",
        "ToleranceDetails": {"tolerance": "ExactOnly"},
        "allowPartialShipments": False,
        "lineItemTotal": Decimal(0),
        "PartArray": {
            "Part": [
                {"partId": line.part_id, "customerSupplied": False, "Quantity": {"uom": "EA", "value": line.quantity}},
            ],
        },
    }
    if line.warehouse is not None:
        item["fobId"] = str(int(line.warehouse))
    return item


def _shape_order(order: PromoStandardsOrder, *, sent_at: datetime) -> PurchaseOrderPayload:
    """Shape an order as SanMar's PromoStandards purchase order service takes it.

    Duplicate lines are combined, and each part becomes its own line item. Every field
    PromoStandards requires and SanMar ignores gets a neutral value: zero totals, no rush,
    no consolidation or blind shipping, exact quantities, and no partial shipments.
    """
    carrier, service = order.ship_method.promostandards_freight()
    return {
        "orderType": "Blank",
        "orderNumber": order.po_number,
        "orderDate": order.order_date or sent_at,
        "totalAmount": Decimal(0),
        "rush": False,
        "currency": "USD",
        "ShipmentArray": {
            "Shipment": [
                {
                    "shipReferences": list(order.ship_references) or [order.po_number],
                    "allowConsolidation": False,
                    "blindShip": False,
                    "packingListRequired": False,
                    "FreightDetails": {"carrier": carrier, "service": service},
                    "ShipTo": {"customerPickup": False, "ContactDetails": _contact(order.ship_to), "shipmentId": 1},
                },
            ],
        },
        "LineItemArray": {
            "LineItem": [_line_item(number, line) for number, line in enumerate(order.merged_lines(), start=1)],
        },
        "termsAndConditions": NOT_USED,
    }


class PurchaseOrderService(PromoStandardsService):
    """SanMar's PromoStandards Purchase Order service."""

    endpoint = PROMOSTANDARDS_PURCHASE_ORDER
    version = "1.0.0"

    def send(self, order: PromoStandardsOrder) -> str:
        """Place an order. Returns SanMar's transaction id, which starts with the PO number."""
        result = self._call("sendPO", {"PO": _shape_order(order, sent_at=datetime.now(tz=UTC))})
        check(result)
        transaction_id = result.get("transactionId")
        if not transaction_id:
            message = "SanMar returned neither a transaction id nor an error for the order."
            raise ResponseError(message)
        return str(transaction_id)

    def supported_order_types(self) -> list[str]:
        """List the order types SanMar accepts. SanMar sells blank goods only: ``Blank``."""
        result = self._call("getSupportedOrderTypes", {})
        check(result)
        return [str(order_type) for order_type in result.get("supportedOrderTypes") or []]
