"""SanMar's packing slip (license plate number) service.

Every box SanMar ships has a license plate number barcode at the bottom of its shipping
label. Scanning it and looking it up here says what is in the box, and which order it
belongs to. A decorator receiving boxes for someone else can look them up with its own
login as long as the box was shipped to the decorator's own address.
"""

import re
from typing import TYPE_CHECKING

from pydantic import AliasPath, Field

from sanmar_sdk._soap import PACKING_SLIP, Service
from sanmar_sdk.base import OneOrMany, Record, SanMarDate
from sanmar_sdk.exceptions import SoapFaultError

from ._common import raise_fault

if TYPE_CHECKING:
    from ._wire import PackingSlipRequest

WS_VERSION = "1.0.0"


class PackingSlipAddress(Record):
    """A postal address on a packing slip."""

    line1: str | None = Field(default=None, validation_alias="Line1")
    line2: str | None = Field(default=None, validation_alias="Line2")
    line3: str | None = Field(default=None, validation_alias="Line3")
    city: str | None = Field(default=None, validation_alias="CityName")
    state: str | None = Field(default=None, validation_alias="StateCode")
    postal_code: str | None = Field(default=None, validation_alias="PostalCode")
    country: str | None = Field(default=None, validation_alias="CountryCode")
    residential: bool | None = Field(default=None, validation_alias="IsResidential")


class PackingSlipParty(Record):
    """Who a box ships from, ships to, or is billed to."""

    name: str | None = Field(default=None, validation_alias="Name")
    address: PackingSlipAddress = Field(default_factory=PackingSlipAddress, validation_alias="Address")
    contact_name: str | None = Field(default=None, validation_alias="ContactName")


class PackingSlipItem(Record):
    """One item in a box."""

    unique_key: str | None = Field(default=None, validation_alias="SkuId")
    """SanMar's identifier for this style, color and size."""
    style: str | None = Field(default=None, validation_alias="StyleNo")
    catalog_color: str | None = Field(default=None, validation_alias="Color")
    """The color as SanMar's warehouse records it, which is the catalog (mainframe) color."""
    size: str | None = Field(default=None, validation_alias="Size")
    description: str | None = Field(default=None, validation_alias="Description")
    quantity: int = Field(validation_alias="Quantity")
    gtin: str | None = Field(default=None, validation_alias="GTIN")


def _header(name: str) -> AliasPath:
    return AliasPath("Header", name)


class PackingSlip(Record):
    """What is in one box SanMar shipped."""

    license_plate: str = Field(validation_alias="id")
    ship_date: SanMarDate | None = Field(default=None, validation_alias=_header("ShipmentDate"))
    box_number: int | None = Field(default=None, validation_alias=_header("ShipmentUnitIndex"))
    """Which box of the shipment this is."""
    box_count: int | None = Field(default=None, validation_alias=_header("ShipmentUnitQuantity"))
    """How many boxes the shipment has."""
    order_date: SanMarDate | None = Field(default=None, validation_alias=_header("OrderDate"))
    order_number: int | None = Field(default=None, validation_alias=_header("OrderNumber"))
    """SanMar's sales order number."""
    invoice_number: int | None = Field(default=None, validation_alias=_header("InvoiceNumber"))
    po_number: str | None = Field(default=None, validation_alias=_header("PurchaseOrderReference"))
    ship_from: PackingSlipParty | None = Field(default=None, validation_alias=_header("ShipFrom"))
    ship_to: PackingSlipParty | None = Field(default=None, validation_alias=_header("ShipTo"))
    bill_to: PackingSlipParty | None = Field(default=None, validation_alias=_header("BillTo"))
    weight: float | None = Field(default=None, validation_alias=AliasPath("Header", "Weight", "_value_1"))
    weight_unit: str | None = Field(default=None, validation_alias=AliasPath("Header", "Weight", "uom"))
    carrier: str | None = Field(default=None, validation_alias=AliasPath("Header", "Carrier", "Name"))
    shipping_method: str | None = Field(
        default=None,
        validation_alias=AliasPath("Header", "Carrier", "ShippingMethod"),
    )
    tracking_number: str | None = Field(default=None, validation_alias=AliasPath("Header", "Carrier", "TrackingId"))
    items: OneOrMany[PackingSlipItem] = Field(default_factory=list, validation_alias=AliasPath("Body", "Item"))


class PackingSlipService(Service):
    """SanMar's packing slip service."""

    def get(self, license_plate: str) -> PackingSlip:
        """Look up what is in the box with the given license plate number.

        License plate numbers start with LP, L, S or R, such as ``LP000123456789``.

        Raises
        ------
        ~sanmar_sdk.exceptions.NotFoundError
            If SanMar has no box with that number, or the box was shipped to someone else.
        """
        if not re.fullmatch(r"(LP|L|S|R)\w+", license_plate.strip(), flags=re.IGNORECASE):
            message = f"{license_plate!r} is not a license plate number; they start with LP, L, S or R."
            raise ValueError(message)
        request: PackingSlipRequest = {
            "wsVersion": WS_VERSION,
            "UserId": self._credentials.username,
            "Password": self._credentials.password,
            "PackingSlipId": license_plate.strip(),
        }
        try:
            result = self._soap.call(PACKING_SLIP, ("GetPackingSlip",), request)
        except SoapFaultError as fault:
            raise_fault(fault)
        return PackingSlip.model_validate(result)
