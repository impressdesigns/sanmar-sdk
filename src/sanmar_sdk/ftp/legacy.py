"""SanMar's older product text files.

These predate the SDL and EPDD files and carry less: no images, no display color names.
SanMar still refreshes them in ``SanMarPDD``, and they still carry GTINs.

- ``sanmar_pdd.txt`` (pipe-delimited) and ``Catalog.txt`` (tab-delimited) list the
  catalog, one row per style, color and size, with the same columns under different names.
- ``sanmar_saleItems.txt`` (pipe-delimited) lists what is on sale, with sale prices and
  dates.

SanMar no longer offers dozens pricing; its columns here show the piece price, and are not
read.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import AliasChoices, Field

from sanmar_sdk.base import Price, Record, SanMarDate

from .readers import Source, read_delimited

if TYPE_CHECKING:
    from collections.abc import Iterator

PDD_COLUMNS = (
    "inventory_key",
    "catalog_no",
    "mill",
    "mill_style_no",
    "colorcat",
    "catalog_color",
    "size",
    "description",
    "extended_description",
    "ea_price",
    "dz_price",
    "dz_qty",
    "case_price",
    "case_qty",
    "catalog_page",
    "weight",
    "size_type",
    "size_index",
    "steves_group",
    "gtin",
)
"""``sanmar_pdd.txt``, as SanMar's server writes it."""

CATALOG_TXT_COLUMNS = (
    *PDD_COLUMNS[:3],
    "mill_style#",
    *PDD_COLUMNS[4:17],
    "index",
    *PDD_COLUMNS[18:],
)
"""``Catalog.txt``: the pdd columns, with ``MILL STYLE#`` and ``INDEX`` for two of them."""

SALE_ITEM_COLUMNS = (
    *PDD_COLUMNS[:9],
    "ea_sale_price",
    "dz_sale_price",
    "dz_qty",
    "case_sale_price",
    *PDD_COLUMNS[13:],
    "sale_start_date",
    "sale_end_date",
)
"""``sanmar_saleItems.txt``, as SanMar's server writes it."""


class TextFileRecord(Record):
    """The columns SanMar's older product text files share."""

    inventory_key: int
    size_index: int = Field(validation_alias=AliasChoices("size_index", "index"))
    style: str = Field(validation_alias="catalog_no")
    """The style number, as printed in SanMar's catalog."""
    catalog_color: str
    """The catalog (mainframe) color, which web services and orders expect."""
    size: str
    brand: str | None = Field(default=None, validation_alias="mill")
    mill_style: str | None = Field(default=None, validation_alias=AliasChoices("mill_style_no", "mill_style#"))
    """The manufacturer's own style number."""
    description: str | None = None
    extended_description: str | None = None
    case_quantity: int | None = Field(default=None, validation_alias="case_qty")
    weight: Decimal | None = None
    """Approximate weight per piece in pounds."""
    size_type: str | None = None
    """SanMar's internal size code."""
    gtin: str | None = None


class TextFileProduct(TextFileRecord):
    """One style, color and size from ``sanmar_pdd.txt`` or ``Catalog.txt``."""

    piece_price: Price = Field(default=None, validation_alias="ea_price")
    case_price: Price = None


class SaleItem(TextFileRecord):
    """One style, color and size on sale, from ``sanmar_saleItems.txt``."""

    piece_sale_price: Price = Field(default=None, validation_alias="ea_sale_price")
    case_sale_price: Price = None
    sale_start_date: SanMarDate | None = None
    sale_end_date: SanMarDate | None = None


def read_pdd(source: Source, *, encoding: str = "utf-8-sig") -> Iterator[TextFileProduct]:
    """Stream ``sanmar_pdd.txt``, one product at a time."""
    return read_delimited(source, TextFileProduct, columns=PDD_COLUMNS, delimiter="|", encoding=encoding)


def read_catalog_txt(source: Source, *, encoding: str = "utf-8-sig") -> Iterator[TextFileProduct]:
    """Stream ``Catalog.txt``, one product at a time."""
    return read_delimited(source, TextFileProduct, columns=CATALOG_TXT_COLUMNS, delimiter="\t", encoding=encoding)


def read_sale_items(source: Source, *, encoding: str = "utf-8-sig") -> Iterator[SaleItem]:
    """Stream ``sanmar_saleItems.txt``, one sale item at a time."""
    return read_delimited(source, SaleItem, columns=SALE_ITEM_COLUMNS, delimiter="|", encoding=encoding)
