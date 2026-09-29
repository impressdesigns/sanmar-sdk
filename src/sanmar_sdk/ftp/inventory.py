"""SanMar's inventory files.

- ``sanmar_dip.txt`` is refreshed hourly: one row per style, color, size and warehouse,
  with that warehouse's stock (capped by SanMar) and the current piece, case and sale
  prices. SanMar recommends it over its inventory web services for anything more frequent
  than a live check at ordering time. ``sanmar_closeouts_dip.txt`` has the same layout.
- ``sanmar_activeproductsexport.txt`` is the older per-warehouse export, with fewer columns.

Both are pipe-delimited.

Discontinued products stay in the file with a quantity of 0 while any size of that color
has at least 12 pieces left. SanMar suggests skipping rows whose ``discontinued_code`` is
``S`` and whose quantity is 0, and checking again later: returned stock can bring them back.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import AliasChoices, Field

from sanmar_sdk.base import Price, Record, SanMarDate
from sanmar_sdk.common import WarehouseNumber

from .readers import Source, read_delimited

if TYPE_CHECKING:
    from collections.abc import Iterator

WAREHOUSE_INVENTORY_COLUMNS = (
    "inventory_key",
    "size_index",
    "catalog_no",
    "catalog_color",
    "size",
    "whse_no",
    "quantity",
    "piece_weight",
    "piece_price",
    "dozens_price",
    "case_price",
    "case_size",
    "each_sale_price",
    "dozens_sale_price",
    "case_sale_price",
    "sale_start_datetime",
    "sale_end_datetime",
    "unique_key",
    "discontinued_code",
    "sale_start_date",
    "sale_end_date",
)
"""``sanmar_dip.txt``, per the FTP Integration Guide v23.6.

The guide numbers these columns 1 to 22 but skips 20; this is the 21 it names.
"""

ACTIVE_PRODUCTS_COLUMNS = (*WAREHOUSE_INVENTORY_COLUMNS[:12], "inventory_key")
"""``sanmar_activeproductsexport.txt``, which ends by repeating the inventory key."""


class WarehouseInventory(Record):
    """One style, color and size at one warehouse."""

    inventory_key: int
    size_index: int
    style: str = Field(validation_alias="catalog_no")
    catalog_color: str
    """The catalog (mainframe) color, which web services and orders expect."""
    size: str
    warehouse: WarehouseNumber = Field(validation_alias="whse_no")
    quantity: int
    """Stock at this warehouse, capped by SanMar."""
    unique_key: str | None = None
    """SanMar's identifier for this style, color and size. Not in the active products file."""
    piece_weight: Decimal | None = None
    piece_price: Price = None
    case_price: Price = None
    case_size: int | None = None
    piece_sale_price: Price = Field(default=None, validation_alias="each_sale_price")
    case_sale_price: Price = None
    sale_start_date: SanMarDate | None = Field(
        default=None,
        validation_alias=AliasChoices("sale_start_date", "sale_start_datetime"),
    )
    sale_end_date: SanMarDate | None = Field(
        default=None,
        validation_alias=AliasChoices("sale_end_date", "sale_end_datetime"),
    )
    discontinued_code: str | None = None
    """Who discontinued the product, ``S`` for SanMar or ``M`` for the mill."""

    @property
    def discontinued(self) -> bool:
        """Whether SanMar or the mill has discontinued the product."""
        return self.discontinued_code is not None


def read_warehouse_inventory(source: Source, *, encoding: str = "utf-8-sig") -> Iterator[WarehouseInventory]:
    """Stream ``sanmar_dip.txt`` (or ``sanmar_closeouts_dip.txt``), one row at a time."""
    return read_delimited(
        source,
        WarehouseInventory,
        columns=WAREHOUSE_INVENTORY_COLUMNS,
        delimiter="|",
        encoding=encoding,
    )


def read_active_products(source: Source, *, encoding: str = "utf-8-sig") -> Iterator[WarehouseInventory]:
    """Stream ``sanmar_activeproductsexport.txt``, one row at a time."""
    return read_delimited(source, WarehouseInventory, columns=ACTIVE_PRODUCTS_COLUMNS, delimiter="|", encoding=encoding)
