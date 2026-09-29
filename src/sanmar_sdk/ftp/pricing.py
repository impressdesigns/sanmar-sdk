"""SanMar's customer pricing files.

SanMar writes these on request, nightly after 2 AM Pacific, to the account's outbound
folder. ``my_price`` is the price for this account specifically.

- ``sanmar_dp.csv`` covers the whole catalog, with the lowest price available to the
  account in ``my_price``.
- ``sanmar_dpIncentive.csv`` covers the whole catalog, with any special pricing in
  ``my_price``, or 0 where there is none.
- ``sanmar_dpc.csv`` lists only what changed since the previous file (the first one has
  everything), with just ``unique_key`` and ``my_price``.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import AliasChoices, Field

from sanmar_sdk.base import Price, Record, SanMarDate

from .readers import Source, read_delimited

if TYPE_CHECKING:
    from collections.abc import Iterator

CUSTOMER_PRICE_COLUMNS = (
    "inventory_key",
    "size_index",
    "catalog_no",
    "catalog_color",
    "size",
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
    "my_price",
)
"""``sanmar_dp.csv`` and ``sanmar_dpIncentive.csv``, per the FTP Integration Guide v23.6."""

PRICE_CHANGE_COLUMNS = ("unique_key", "my_price")
"""``sanmar_dpc.csv``, per the FTP Integration Guide v23.6."""


class CustomerPrice(Record):
    """The account's price for one style, color and size."""

    unique_key: str
    inventory_key: int
    size_index: int
    style: str = Field(validation_alias="catalog_no")
    catalog_color: str
    """The catalog (mainframe) color, which web services and orders expect."""
    size: str
    my_price: Price
    """The account's price, which is the case or sale price where there is no special pricing."""
    piece_weight: Decimal | None = None
    piece_price: Price = None
    case_price: Price = None
    case_size: int | None = None
    piece_sale_price: Price = Field(default=None, validation_alias="each_sale_price")
    case_sale_price: Price = None
    sale_start_date: SanMarDate | None = Field(
        default=None,
        validation_alias=AliasChoices("sale_start_datetime", "sale_start_date"),
    )
    sale_end_date: SanMarDate | None = Field(
        default=None,
        validation_alias=AliasChoices("sale_end_datetime", "sale_end_date"),
    )
    discontinued_code: str | None = None
    """Who discontinued the product, ``S`` for SanMar or ``M`` for the mill."""


class PriceChange(Record):
    """A changed price from ``sanmar_dpc.csv``."""

    unique_key: str
    my_price: Price


def read_customer_prices(source: Source, *, encoding: str = "utf-8-sig") -> Iterator[CustomerPrice]:
    """Stream ``sanmar_dp.csv`` or ``sanmar_dpIncentive.csv``, one row at a time."""
    return read_delimited(source, CustomerPrice, columns=CUSTOMER_PRICE_COLUMNS, encoding=encoding)


def read_price_changes(source: Source, *, encoding: str = "utf-8-sig") -> Iterator[PriceChange]:
    """Stream ``sanmar_dpc.csv``, one changed price at a time."""
    return read_delimited(source, PriceChange, columns=PRICE_CHANGE_COLUMNS, encoding=encoding)
