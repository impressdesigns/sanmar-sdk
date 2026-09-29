"""Ordering through order files on SanMar's SFTP server, and the files SanMar writes back.

An SFTP order is three comma-delimited ASCII files that share a batch name:

- ``<batch>CustInfo.txt`` ships each purchase order somewhere,
- ``<batch>Details.txt`` lists what each purchase order is for, by inventory key and size
  index only, and
- ``<batch>Release<n>.txt`` releases some or all of the batch's purchase orders for
  processing, any time up to two weeks after the other two were uploaded.

Within about 15 minutes SanMar acknowledges an uploaded batch with a Holding file that says,
line by line, which warehouse will ship it and whether the stock is there. Orders shipped
each day are listed in a tab-delimited daily status file, where SanMar has set one up.

SFTP orders go straight to SanMar's production system; there is no test environment.
"""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import AliasChoices, Field

from sanmar_sdk.base import Price, Record, SanMarDate
from sanmar_sdk.common import SkuKey, WarehouseNumber, WillCall

from .readers import Source, read_delimited

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from sanmar_sdk.orders import PurchaseOrder

LINE_ENDING = "\r\n"
MAX_INVENTORY_KEY = 999_999
"""The order files allow six digits for an inventory key."""

HOLDING_COLUMNS = ("ponum", "style", "color", "size", "qty", "whse_no", "availability")
"""A Holding file, per the example in the Purchase Order Integration Guide v24.5.

The guide's field table omits the size its example includes.
"""

SHIPMENT_STATUS_COLUMNS = (
    "customer_po",
    "salesorder#",
    "ship_from",
    "ship_date",
    "ship_to_name",
    "attention",
    "ship_to_address1",
    "ship_to_address2",
    "ship_to_city",
    "ship_to_state",
    "ship_to_zip",
    "ship_to_country",
    "sub_total",
    "freight",
    "handling_fee",
    "invoice_total",
    "track_num",
    "total_cases",
    "ship_via",
    "box_number",
    "style",
    "description",
    "color",
    "size",
    "qty",
    "inventory_key",
    "size_id",
    "invoice_attention",
    "lpn",
)
"""The daily shipment status file, per the FTP Integration Guide v23.6."""


@dataclass(frozen=True, slots=True)
class OrderFiles:
    """The two files that place a batch of orders: names and contents."""

    cust_info_name: str
    cust_info: str
    details_name: str
    details: str


def _check_batch(batch: str) -> str:
    """SanMar associates files by batch name, which may hold only letters, digits and dashes."""
    if not re.fullmatch(r"[A-Za-z0-9-]+", batch):
        message = f"A batch name may only contain letters, digits and dashes, not {batch!r}."
        raise ValueError(message)
    return batch


def _cust_info_row(order: PurchaseOrder) -> str:
    """One ``CustInfo.txt`` row, in the guide's 14-field order."""
    ship_to = order.ship_to
    if ship_to.email is None:
        message = f"PO {order.po_number}: SFTP orders need a ship-to email for SanMar's confirmation."
        raise ValueError(message)
    will_call = isinstance(order.ship_method, WillCall)
    ship_method = order.ship_method.ship_method if isinstance(order.ship_method, WillCall) else order.ship_method.value
    fields = [
        order.po_number,
        ship_to.address1,
        ship_to.address2 or "",
        ship_to.city,
        ship_to.state,
        ship_to.zip_code,
        ship_method,
        ship_to.email,
        "Y" if ship_to.residential else "N",
        "",  # DEPT: SanMar says to leave it blank.
        "",  # NOTES: SanMar says to leave it blank.
        ship_to.company or "",
        # INT_METHOD: blank, except that the guide's only will-call example puts W here.
        "W" if will_call else "",
        ship_to.attention or "",
    ]
    return ",".join(fields)


def _details_rows(order: PurchaseOrder) -> list[str]:
    """Build the ``Details.txt`` rows for one order, with duplicate lines combined."""
    rows = []
    for line in order.merged_lines():
        if not isinstance(line.item, SkuKey):
            message = f"PO {order.po_number}: SFTP orders name items by inventory key and size index only."
            raise TypeError(message)
        if line.item.inventory_key > MAX_INVENTORY_KEY:
            message = f"PO {order.po_number}: inventory key {line.item.inventory_key} is too long for an order file."
            raise ValueError(message)
        fields = [order.po_number, str(line.item.inventory_key), str(line.quantity), str(line.item.size_index)]
        if line.warehouse is not None:
            fields.append(str(line.warehouse.value))
        rows.append(",".join(fields))
    return rows


def render_order_files(batch: str, orders: Sequence[PurchaseOrder]) -> OrderFiles:
    """Build the ``CustInfo.txt`` and ``Details.txt`` files for a batch of orders.

    Parameters
    ----------
    batch
        The batch name, unique for every batch ever sent. SanMar suggests the date and a
        running number for the day, such as ``06-07-2022-1``.
    orders
        The purchase orders in the batch. Items must be named by
        :class:`~sanmar_sdk.common.SkuKey`, and each order needs a ship-to email.
    """
    _check_batch(batch)
    if not orders:
        message = "A batch needs at least one purchase order."
        raise ValueError(message)
    po_numbers = [order.po_number for order in orders]
    if len(set(po_numbers)) != len(po_numbers):
        message = "Each purchase order in a batch needs its own PO number."
        raise ValueError(message)
    cust_info = [_cust_info_row(order) for order in orders]
    details = [row for order in orders for row in _details_rows(order)]
    return OrderFiles(
        cust_info_name=f"{batch}CustInfo.txt",
        cust_info=LINE_ENDING.join(cust_info) + LINE_ENDING,
        details_name=f"{batch}Details.txt",
        details=LINE_ENDING.join(details) + LINE_ENDING,
    )


def render_release_file(batch: str, po_numbers: Sequence[str], release_number: int = 1) -> tuple[str, str]:
    """Build the file that releases some or all of a batch's orders, as ``(name, contents)``.

    Each release of a batch gets the next ``release_number``, starting at 1.
    """
    _check_batch(batch)
    if not po_numbers:
        message = "A release needs at least one PO number."
        raise ValueError(message)
    if release_number < 1:
        message = "Release numbers start at 1."
        raise ValueError(message)
    return f"{batch}Release{release_number}.txt", LINE_ENDING.join(po_numbers) + LINE_ENDING


class HoldingLine(Record):
    """One line of SanMar's acknowledgement of an SFTP order."""

    po_number: str = Field(validation_alias="ponum")
    style: str
    catalog_color: str = Field(validation_alias="color")
    size: str
    quantity: int = Field(validation_alias="qty")
    warehouse: WarehouseNumber = Field(validation_alias="whse_no")
    """The warehouse SanMar will ship this line from."""
    available: bool = Field(validation_alias="availability")
    """Whether the stock is there. If not, SanMar's customer service calls about it."""


class ShipmentStatus(Record):
    """One line of one box in SanMar's daily shipment status file."""

    po_number: str = Field(validation_alias="customer_po")
    sales_order_number: str = Field(validation_alias="salesorder#")
    ship_date: SanMarDate
    style: str
    catalog_color: str = Field(validation_alias="color")
    size: str
    quantity: int = Field(validation_alias="qty")
    ship_from: str | None = None
    ship_to_name: str | None = None
    attention: str | None = None
    ship_to_address1: str | None = None
    ship_to_address2: str | None = None
    ship_to_city: str | None = None
    ship_to_state: str | None = None
    ship_to_zip: str | None = None
    ship_to_country: str | None = None
    sub_total: Price = None
    freight: Price = None
    handling_fee: Price = None
    invoice_total: Price = None
    tracking_number: str | None = Field(default=None, validation_alias="track_num")
    total_cases: int | None = None
    box_number: int | None = None
    description: str | None = None
    inventory_key: int | None = None
    size_index: int | None = Field(default=None, validation_alias="size_id")
    invoice_attention: str | None = None
    license_plate: str | None = Field(
        default=None,
        validation_alias=AliasChoices("lpn", "lpn_license_plate_number"),
    )
    """The license plate number on the box's label, for the packing slip service."""


def read_holding(source: Source, *, encoding: str = "utf-8-sig") -> Iterator[HoldingLine]:
    """Stream a Holding file, one order line at a time."""
    return read_delimited(source, HoldingLine, columns=HOLDING_COLUMNS, encoding=encoding)


def read_shipment_status(source: Source, *, encoding: str = "utf-8-sig") -> Iterator[ShipmentStatus]:
    """Stream a daily shipment status file, one line of one box at a time."""
    return read_delimited(source, ShipmentStatus, columns=SHIPMENT_STATUS_COLUMNS, delimiter="\t", encoding=encoding)
