"""SanMar's product catalog files.

- ``SanMar_SDL_N.csv`` (the SanMar Data Library) has one row per style, color and size,
  with descriptions, prices, image links and GTINs, but no inventory. Its ``_DI`` variant
  has the same columns. SanMar's guides call SDL_N and EPDD its main product files, and
  point to SDL_N as the source of catalog colors for web services and orders.
- ``SanMar_EPDD.csv`` has the same columns plus ``QTY``, the stock across all warehouses.
  A style listed under several categories appears once per category, so unique keys repeat.
- The SanMarPI files (bulk, delta, brand and category) are written on request by the
  product information web service, with a slightly different set of columns.

All of them are comma-delimited with a header row, and all are read one row at a time.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import AliasChoices, Field

from sanmar_sdk.base import CommaSeparated, Price, Record, SanMarDate

from .readers import Source, read_delimited

if TYPE_CHECKING:
    from collections.abc import Iterator

SDL_COLUMNS = (
    "unique_key",
    "product_title",
    "product_description",
    "style#",
    "available_sizes",
    "brand_logo_image",
    "thumbnail_image",
    "color_swatch_image",
    "product_image",
    "spec_sheet",
    "price_text",
    "suggested_price",
    "category_name",
    "subcategory_name",
    "color_name",
    "color_square_image",
    "color_product_image",
    "color_product_image_thumbnail",
    "size",
    "piece_weight",
    "piece_price",
    "dozens_price",
    "case_price",
    "price_group",
    "case_size",
    "inventory_key",
    "size_index",
    "sanmar_mainframe_color",
    "mill",
    "product_status",
    "companion_style",
    "msrp",
    "map_pricing",
    "front_model_image_url",
    "back_model_image_url",
    "front_flat_image_url",
    "back_flat_image_url",
    "product_measurements",
    "pms_color",
    "gtin",
    "decoration_spec_sheet",
)
"""``SanMar_SDL_N.csv``, as SanMar's server writes it.

The FTP Integration Guide v23.6 spells a few of these differently (``COMPANION_STYLES``,
``PRODUCT_MEASUREMENT``); the file's own header is followed here.
"""

EPDD_COLUMNS = (
    "unique_key",
    "product_title",
    "product_description",
    "style#",
    "available_sizes",
    "brand_logo_image",
    "thumbnail_image",
    "color_swatch_image",
    "product_image",
    "spec_sheet",
    "price_text",
    "suggested_price",
    "category_name",
    "subcategory_name",
    "color_name",
    "color_square_image",
    "color_product_image",
    "color_product_image_thumbnail",
    "size",
    "qty",
    "piece_weight",
    "piece_price",
    "dozens_price",
    "case_price",
    "price_group",
    "case_size",
    "inventory_key",
    "size_index",
    "sanmar_mainframe_color",
    "mill",
    "product_status",
    "companion_styles",
    "msrp",
    "map_pricing",
    "front_model_image_url",
    "back_model_image",
    "front_flat_image",
    "back_flat_image",
    "product_measurements",
    "pms_color",
    "gtin",
    "decoration_spec_sheet",
)
"""``SanMar_EPDD.csv``, as SanMar's server writes it.

Like SDL_N with ``QTY`` after ``SIZE``, except that its model and flat image columns drop
the ``_URL`` suffix SDL_N's have.
"""

PRODUCT_INFORMATION_COLUMNS = (
    "unique_key",
    "product_title",
    "product_description",
    "style#",
    "available_sizes",
    "brand_logo_image",
    "thumbnail_image",
    "color_swatch_image",
    "product_image",
    "spec_sheet",
    "front_flat",
    "back_flat",
    "front_model",
    "back_model",
    "side_model",
    "three_q_model",
    "price_text",
    "color_name",
    "color_square_image",
    "color_product_image",
    "color_product_image_thumbnail",
    "size",
    "piece_weight",
    "piece_price",
    "dozen_price",
    "case_price",
    "piece_sale_price",
    "dozen_sale_price",
    "case_sale_price",
    "sale_start_date",
    "sale_end_date",
    "case_size",
    "inventory_key",
    "size_index",
    "catalog_color",
    "price_code",
    "product_status",
    "title_image",
    "brand_name",
    "keywords",
    "category",
    "map_price",
)
"""The SanMarPI bulk, delta, brand and category files, per the Web Services Integration
Guide v24.6 and as SanMar's server writes them."""


class ProductRecord(Record):
    """The columns every SanMar product file shares."""

    unique_key: str
    """SanMar's identifier for this style, color and size, and the PromoStandards part id."""
    style: str = Field(validation_alias="style#")
    catalog_color: str = Field(validation_alias=AliasChoices("sanmar_mainframe_color", "catalog_color"))
    """The catalog (mainframe) color, which web services and orders expect."""
    color_name: str | None = None
    """The full color name, for display only."""
    size: str
    inventory_key: int
    size_index: int
    title: str | None = Field(default=None, validation_alias="product_title")
    description: str | None = Field(default=None, validation_alias="product_description")
    brand: str | None = Field(default=None, validation_alias=AliasChoices("mill", "brand_name"))
    status: str | None = Field(default=None, validation_alias="product_status")
    """Coming Soon, New, Regular, or Discontinued. Coming Soon rows may be incomplete."""
    available_sizes: str | None = None
    price_text: str | None = None
    piece_weight: Decimal | None = None
    """Approximate weight per piece in pounds."""
    piece_price: Price = None
    """The price per piece for five pieces or fewer of one style and color."""
    case_price: Price = None
    """The price per piece when buying by the case."""
    case_size: int | None = None
    map_price: Price = Field(default=None, validation_alias=AliasChoices("map_pricing", "map_price"))
    """The minimum advertised price."""
    brand_logo_image: str | None = None
    thumbnail_image: str | None = None
    color_swatch_image: str | None = None
    product_image: str | None = None
    spec_sheet: str | None = None
    color_square_image: str | None = None
    color_product_image: str | None = None
    color_product_image_thumbnail: str | None = None


class CatalogProduct(ProductRecord):
    """One style, color and size from ``SanMar_SDL_N.csv`` or ``SanMar_EPDD.csv``."""

    quantity: int | None = Field(default=None, validation_alias="qty")
    """Stock across all warehouses, capped by SanMar. Only the EPDD file has it."""
    category: str | None = Field(default=None, validation_alias="category_name")
    """The category. In SDL files this holds every category, separated by semicolons."""
    subcategory: str | None = Field(default=None, validation_alias="subcategory_name")
    suggested_price: Price = None
    msrp: Price = None
    companion_styles: str | None = Field(
        default=None,
        validation_alias=AliasChoices("companion_styles", "companion_style"),
    )
    front_model_image_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("front_model_image_url", "front_model_image"),
    )
    back_model_image_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("back_model_image_url", "back_model_image"),
    )
    front_flat_image_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("front_flat_image_url", "front_flat_image"),
    )
    back_flat_image_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("back_flat_image_url", "back_flat_image"),
    )
    product_measurements: str | None = Field(
        default=None,
        validation_alias=AliasChoices("product_measurements", "product_measurement"),
    )
    pms_color: str | None = None
    """The Pantone (PMS) color. SanMar says it does not stand in for the product color."""
    gtin: str | None = None
    decoration_spec_sheet: str | None = None


class ProductInformation(ProductRecord):
    """One style, color and size from a SanMarPI file."""

    category: str | None = None
    keywords: CommaSeparated = Field(default_factory=list)
    piece_sale_price: Price = None
    case_sale_price: Price = None
    sale_start_date: SanMarDate | None = None
    sale_end_date: SanMarDate | None = None
    price_code: str | None = None
    """The suggested retail pricing code. A/P is 50%, B/Q 45%, C/R 40%, D/S 35%, E/T 30%."""
    front_flat: str | None = None
    back_flat: str | None = None
    front_model: str | None = None
    back_model: str | None = None
    side_model: str | None = None
    three_q_model: str | None = None


def read_catalog(source: Source, *, encoding: str = "utf-8-sig") -> Iterator[CatalogProduct]:
    """Stream ``SanMar_SDL_N.csv`` (or ``SanMar_SDL_DI.csv``), one product at a time."""
    return read_delimited(source, CatalogProduct, columns=SDL_COLUMNS, encoding=encoding)


def read_extended_catalog(source: Source, *, encoding: str = "utf-8-sig") -> Iterator[CatalogProduct]:
    """Stream ``SanMar_EPDD.csv``, one product at a time, with total stock."""
    return read_delimited(source, CatalogProduct, columns=EPDD_COLUMNS, encoding=encoding)


def read_product_information(source: Source, *, encoding: str = "utf-8-sig") -> Iterator[ProductInformation]:
    """Stream a SanMarPI bulk, delta, brand or category file, one product at a time."""
    return read_delimited(source, ProductInformation, columns=PRODUCT_INFORMATION_COLUMNS, encoding=encoding)
