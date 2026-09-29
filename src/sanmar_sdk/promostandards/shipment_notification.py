"""SanMar's PromoStandards Order Shipment Notification service, version 1.0.0.

Reports what shipped, from where, and under which tracking numbers, by purchase order, by
SanMar sales order, or for everything shipped since a point in the last seven days. SanMar
recommends its daily status file on the SFTP server instead, and asks that this service be
called no more than three times a day.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import AliasPath, Field

from sanmar_sdk._soap import PROMOSTANDARDS_SHIPMENT_NOTIFICATION
from sanmar_sdk.base import Record

from ._common import PromoStandardsService, check

if TYPE_CHECKING:
    from ._wire import GetOrderShipmentNotificationRequest

MAX_AGE = timedelta(days=7)


class ShipmentAddress(Record):
    """Where a shipment left from or went to."""

    address1: str | None = None
    address2: str | None = None
    address3: str | None = None
    address4: str | None = None
    city: str | None = None
    region: str | None = None
    """The state."""
    postal_code: str | None = Field(default=None, validation_alias="postalCode")
    country: str | None = None


class ShippedItem(Record):
    """What went into a package."""

    product_id: str | None = Field(default=None, validation_alias="supplierProductId")
    """The style."""
    part_id: str | None = Field(default=None, validation_alias="supplierPartId")
    """SanMar's unique key for the style, color and size."""
    quantity: Decimal | None = None
    po_line_number: str | None = Field(default=None, validation_alias="purchaseOrderLineNumber")
    distributor_product_id: str | None = Field(default=None, validation_alias="distributorProductId")
    distributor_part_id: str | None = Field(default=None, validation_alias="distributorPartId")


class ShipmentPackage(Record):
    """One box, and its tracking number."""

    tracking_number: str = Field(validation_alias="trackingNumber")
    shipment_date: datetime = Field(validation_alias="shipmentDate")
    id: int | None = None
    carrier: str | None = None
    shipment_method: str | None = Field(default=None, validation_alias="shipmentMethod")
    """The carrier's service, such as ``Ground``."""
    dimension_uom: str | None = Field(default=None, validation_alias="dimUOM")
    length: Decimal | None = None
    width: Decimal | None = None
    height: Decimal | None = None
    weight_uom: str | None = Field(default=None, validation_alias="weightUOM")
    weight: Decimal | None = None
    shipping_account: str | None = Field(default=None, validation_alias="shippingAccount")
    shipment_terms: str | None = Field(default=None, validation_alias="shipmentTerms")
    items: list[ShippedItem] = Field(default_factory=list, validation_alias=AliasPath("ItemArray", "Item"))


class ShipmentLocation(Record):
    """Everything that shipped from one warehouse to one address."""

    complete: bool
    ship_from: ShipmentAddress = Field(validation_alias="ShipFromAddress")
    ship_to: ShipmentAddress = Field(validation_alias="ShipToAddress")
    id: int | None = None
    destination_type: str | None = Field(default=None, validation_alias="shipmentDestinationType")
    """``Commercial`` or ``Residential``."""
    packages: list[ShipmentPackage] = Field(default_factory=list, validation_alias=AliasPath("PackageArray", "Package"))


class SalesOrderShipment(Record):
    """What shipped against one of SanMar's sales orders."""

    sales_order_number: str = Field(validation_alias="salesOrderNumber")
    complete: bool
    locations: list[ShipmentLocation] = Field(
        default_factory=list,
        validation_alias=AliasPath("ShipmentLocationArray", "ShipmentLocation"),
    )


class ShipmentNotification(Record):
    """What shipped against one purchase order."""

    po_number: str = Field(validation_alias="purchaseOrderNumber")
    complete: bool
    """Whether the whole purchase order has shipped."""
    sales_orders: list[SalesOrderShipment] = Field(
        default_factory=list,
        validation_alias=AliasPath("SalesOrderArray", "SalesOrder"),
    )

    @property
    def tracking_numbers(self) -> list[str]:
        """Every package's tracking number, in the order SanMar listed them."""
        return [
            package.tracking_number
            for sales_order in self.sales_orders
            for location in sales_order.locations
            for package in location.packages
        ]


class ShipmentNotificationService(PromoStandardsService):
    """SanMar's PromoStandards Order Shipment Notification service."""

    endpoint = PROMOSTANDARDS_SHIPMENT_NOTIFICATION
    version = "1.0.0"

    def by_purchase_order(self, po_number: str) -> list[ShipmentNotification]:
        """Report what has shipped against a purchase order."""
        return self._query({"queryType": "1", "referenceNumber": po_number})

    def by_sales_order(self, sales_order_number: str) -> list[ShipmentNotification]:
        """Report what has shipped against one of SanMar's sales orders."""
        return self._query({"queryType": "2", "referenceNumber": sales_order_number})

    def since(self, since: datetime) -> list[ShipmentNotification]:
        """Report everything shipped after a point in time, at most seven days ago.

        Raises
        ------
        ValueError
            If ``since`` has no time zone, or is more than seven days ago.
        """
        if since.tzinfo is None:
            message = "Give the time with a time zone; SanMar reads it as UTC."
            raise ValueError(message)
        if datetime.now(tz=UTC) - since > MAX_AGE:
            message = "SanMar reports shipments from at most 7 days back."
            raise ValueError(message)
        return self._query({"queryType": "3", "shipmentDateTimeStamp": since.astimezone(UTC)})

    def _query(self, request: GetOrderShipmentNotificationRequest) -> list[ShipmentNotification]:
        result = self._call("getOrderShipmentNotification", request)
        if check(result, allow_empty=True):
            return []
        notifications = result.get("OrderShipmentNotificationArray") or {}
        return [
            ShipmentNotification.model_validate(notification)
            for notification in notifications.get("OrderShipmentNotification") or []
        ]
