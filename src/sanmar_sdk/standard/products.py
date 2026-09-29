"""SanMar's own product information service.

Looks up products by style, optionally narrowed to a catalog color, a size, or both, and
asks SanMar to write product files to the SFTP server. For frequent or whole-catalog pulls,
SanMar recommends its product files (:mod:`sanmar_sdk.ftp`) over this service.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import AliasPath, Field

from sanmar_sdk._soap import PRODUCT_INFO, Service
from sanmar_sdk.base import CommaSeparated, Price, Record, SanMarDate
from sanmar_sdk.common import StyleQuery

from ._common import raise_error, web_service_user

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ._wire import ProductQuery

PRODUCT_INFORMATION_FOLDER = "SanMarPDD/SanMarPI"


class ProductImages(Record):
    """Links to a product's images and documents."""

    product: str | None = Field(default=None, validation_alias="productImage")
    thumbnail: str | None = Field(default=None, validation_alias="thumbnailImage")
    color_product: str | None = Field(default=None, validation_alias="colorProductImage")
    color_product_thumbnail: str | None = Field(default=None, validation_alias="colorProductImageThumbnail")
    color_square: str | None = Field(default=None, validation_alias="colorSquareImage")
    color_swatch: str | None = Field(default=None, validation_alias="colorSwatchImage")
    brand_logo: str | None = Field(default=None, validation_alias="brandLogoImage")
    front_model: str | None = Field(default=None, validation_alias="frontModel")
    back_model: str | None = Field(default=None, validation_alias="backModel")
    side_model: str | None = Field(default=None, validation_alias="sideModel")
    three_quarter_model: str | None = Field(default=None, validation_alias="threeQModel")
    front_flat: str | None = Field(default=None, validation_alias="frontFlat")
    back_flat: str | None = Field(default=None, validation_alias="backFlat")
    spec_sheet: str | None = Field(default=None, validation_alias="specSheet")


class ProductPrices(Record):
    """A product's list and sale prices."""

    piece_price: Price = Field(default=None, validation_alias="piecePrice")
    """The price per piece for five pieces or fewer of one style and color."""
    case_price: Price = Field(default=None, validation_alias="casePrice")
    """The price per piece when buying by the case."""
    piece_sale_price: Price = Field(default=None, validation_alias="pieceSalePrice")
    case_sale_price: Price = Field(default=None, validation_alias="caseSalePrice")
    sale_start_date: SanMarDate | None = Field(default=None, validation_alias="saleStartDate")
    sale_end_date: SanMarDate | None = Field(default=None, validation_alias="saleEndDate")
    map_price: Price = Field(default=None, validation_alias="mapPrice")
    """The minimum advertised price."""
    price_code: str | None = Field(default=None, validation_alias="priceCode")
    """The suggested retail pricing code. A/P is 50%, B/Q 45%, C/R 40%, D/S 35%, E/T 30%."""
    price_text: str | None = Field(default=None, validation_alias="priceText")
    """Which sizes the price applies to."""


def _basic(name: str) -> AliasPath:
    return AliasPath("productBasicInfo", name)


class ProductInfo(Record):
    """One style, color and size, as SanMar's product information service describes it."""

    style: str = Field(validation_alias=_basic("style"))
    catalog_color: str = Field(validation_alias=_basic("catalogColor"))
    """The catalog (mainframe) color, which web services and orders expect."""
    size: str = Field(validation_alias=_basic("size"))
    unique_key: str = Field(validation_alias=_basic("uniqueKey"))
    """SanMar's identifier for this style, color and size, and the PromoStandards part id."""
    inventory_key: int = Field(validation_alias=_basic("inventoryKey"))
    size_index: int = Field(validation_alias=_basic("sizeIndex"))
    color_name: str | None = Field(default=None, validation_alias=_basic("color"))
    """The full color name, for display only."""
    title: str | None = Field(default=None, validation_alias=_basic("productTitle"))
    description: str | None = Field(default=None, validation_alias=_basic("productDescription"))
    brand: str | None = Field(default=None, validation_alias=_basic("brandName"))
    category: str | None = Field(default=None, validation_alias=_basic("category"))
    status: str | None = Field(default=None, validation_alias=_basic("productStatus"))
    """Coming Soon, New, Active, Regular, or Discontinued."""
    available_sizes: str | None = Field(default=None, validation_alias=_basic("availableSizes"))
    keywords: CommaSeparated = Field(default_factory=list, validation_alias=_basic("keywords"))
    case_size: int | None = Field(default=None, validation_alias=_basic("caseSize"))
    piece_weight: Decimal | None = Field(default=None, validation_alias=_basic("pieceWeight"))
    """Approximate weight per piece in pounds."""
    images: ProductImages = Field(default_factory=ProductImages, validation_alias="productImageInfo")
    prices: ProductPrices = Field(default_factory=ProductPrices, validation_alias="productPriceInfo")


class FileRequest(Record):
    """SanMar's acknowledgement of a request for a product file.

    SanMar writes the file to its SFTP server about 20 minutes later. Brand and category
    file names end with the date SanMar wrote them, so they are matched by pattern; read
    one with :meth:`sanmar_sdk.ftp.SanMarFTP.find` and
    :meth:`~sanmar_sdk.ftp.SanMarFTP.product_information`.
    """

    folder: str
    file_pattern: str
    """The file's name, or a shell-style pattern where SanMar dates it."""
    message: str | None = None


class ProductInfoService(Service):
    """SanMar's own product information service."""

    def get(self, style: str, *, catalog_color: str | None = None, size: str | None = None) -> list[ProductInfo]:
        """Look up a style, optionally narrowed to one catalog color, one size, or both.

        Returns one entry per matching style, color and size. The color must be the catalog
        (mainframe) color.
        """
        return self.get_many([StyleQuery(style=style, catalog_color=catalog_color, size=size)])

    def get_many(self, queries: Sequence[StyleQuery]) -> list[ProductInfo]:
        """Look up several styles in one call."""
        if not queries:
            return []
        products: list[ProductQuery] = []
        for query in queries:
            product: ProductQuery = {"style": query.style}
            if query.catalog_color is not None:
                product["color"] = query.catalog_color
            if query.size is not None:
                product["size"] = query.size
            products.append(product)
        result = self._soap.call(
            PRODUCT_INFO,
            ("getProductInfoByStyleColorSize",),
            {"arg0": products, "arg1": web_service_user(self._credentials)},
        )
        if result.get("errorOccured") or result.get("errorOccurred"):
            raise_error(result.get("message"), color_hint=any(query.catalog_color for query in queries))
        return [ProductInfo.model_validate(product) for product in result.get("listResponse") or []]

    def request_bulk_file(self) -> FileRequest:
        """Ask SanMar to write a file of its whole catalog. SanMar allows this once a month."""
        result = self._soap.call(PRODUCT_INFO, ("getProductBulkInfo",), {"arg0": web_service_user(self._credentials)})
        return self._file_request(result, f"SanMarPI-Bulk-{self._credentials.customer_number}.csv")

    def request_delta_file(self) -> FileRequest:
        """Ask SanMar to write a file of what changed since the last bulk or delta file.

        SanMar allows this once a day. The next delta starts from this one, so calling it
        consumes the changes it reports.
        """
        result = self._soap.call(PRODUCT_INFO, ("getProductDeltaInfo",), {"arg0": web_service_user(self._credentials)})
        return self._file_request(result, f"SanMarPI-Delta-{self._credentials.customer_number}.csv")

    def request_brand_file(self, brand: str) -> FileRequest:
        """Ask SanMar to write a file of one brand's products, such as ``OGIO``."""
        result = self._soap.call(
            PRODUCT_INFO,
            ("getProductInfoByBrand",),
            {"arg0": {"brandName": brand}, "arg1": web_service_user(self._credentials)},
        )
        return self._file_request(result, f"Brand_{brand}_*.csv")

    def request_category_file(self, category: str) -> FileRequest:
        """Ask SanMar to write a file of one category's products, such as ``Caps``."""
        result = self._soap.call(
            PRODUCT_INFO,
            ("getProductInfoByCategory",),
            {"arg0": {"category": category}, "arg1": web_service_user(self._credentials)},
        )
        return self._file_request(result, f"Category_{category}_*.csv")

    @staticmethod
    def _file_request(result: dict[str, object], file_pattern: str) -> FileRequest:
        message = result.get("message")
        if result.get("errorOccured") or result.get("errorOccurred"):
            raise_error(str(message) if message is not None else None)
        return FileRequest.model_validate(
            {"folder": PRODUCT_INFORMATION_FOLDER, "file_pattern": file_pattern, "message": message},
        )
