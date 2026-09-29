"""SanMar's PromoStandards Product Data service, version 2.0.0.

Describes a style and every color and size of it, and lists which parts are closed out,
changed or sellable. In PromoStandards terms a *product* is a SanMar style (``K500``) and a
*part* is one style, color and size, identified by SanMar's unique key.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from pydantic import AliasPath, Field

from sanmar_sdk._soap import PROMOSTANDARDS_PRODUCT_DATA
from sanmar_sdk.base import Record
from sanmar_sdk.common import WarehouseNumber
from sanmar_sdk.exceptions import NotFoundError

from ._common import PromoStandardsService, check, pluck

if TYPE_CHECKING:
    from ._wire import GetProductRequest, GetProductSellableRequest

COUNTRY = "US"
LANGUAGE = "en"


class Color(Record):
    """One of a part's colors."""

    catalog_color: str = Field(validation_alias="colorName")
    """The catalog (mainframe) color, which web services and orders expect."""
    color_name: str | None = Field(default=None, validation_alias="standardColorName")
    """The full color name, for display only."""
    hex: str | None = None
    approximate_pms: str | None = Field(default=None, validation_alias="approximatePms")
    """The nearest Pantone color, such as ``BLACK C``."""


class ApparelSize(Record):
    """A part's size."""

    apparel_style: str = Field(validation_alias="apparelStyle")
    """``Unisex``, ``Mens``, ``Womens``, ``Youth``, ``MensTall`` and so on."""
    label_size: str = Field(validation_alias="labelSize")
    """``XS`` through ``6XL``, ``OSFA``, or ``CUSTOM`` when :attr:`custom_size` holds it."""
    custom_size: str | None = Field(default=None, validation_alias="customSize")
    """The size when it is not a standard label size, such as a pant size (``2732``)."""

    @property
    def size(self) -> str:
        """The size as SanMar prints it, which is the custom size where there is one."""
        return self.custom_size or self.label_size


class Dimension(Record):
    """A part's measurements."""

    dimension_uom: str = Field(validation_alias="dimensionUom")
    depth: Decimal
    height: Decimal
    width: Decimal
    weight_uom: str = Field(validation_alias="weightUom")
    weight: Decimal


class Packaging(Record):
    """A way a part is packed: how many to a box, and how big and heavy the box is."""

    package_type: str = Field(validation_alias="packageType")
    quantity: Decimal
    description: str | None = None
    default: bool = False
    dimension_uom: str | None = Field(default=None, validation_alias="dimensionUom")
    depth: Decimal | None = None
    height: Decimal | None = None
    width: Decimal | None = None
    weight_uom: str | None = Field(default=None, validation_alias="weightUom")
    weight: Decimal | None = None


class Specification(Record):
    """A measurement of a part, such as its chest or inseam."""

    specification_type: str = Field(validation_alias="specificationType")
    uom: str = Field(validation_alias="SpecificationUom")
    value: str = Field(validation_alias="measurementValue")


class ProductPart(Record):
    """One color and size of a style."""

    part_id: str = Field(validation_alias="partId")
    """SanMar's unique key for this style, color and size."""
    primary_color: Color | None = Field(default=None, validation_alias=AliasPath("primaryColor", "Color"))
    colors: list[Color] = Field(default_factory=list, validation_alias=AliasPath("ColorArray", "Color"))
    descriptions: list[str] = Field(default_factory=list, validation_alias="description")
    apparel_size: ApparelSize | None = Field(default=None, validation_alias="ApparelSize")
    country_of_origin: str | None = Field(default=None, validation_alias="countryOfOrigin")
    primary_material: str | None = Field(default=None, validation_alias="primaryMaterial")
    specifications: list[Specification] = Field(
        default_factory=list,
        validation_alias=AliasPath("SpecificationArray", "Specification"),
    )
    dimension: Dimension | None = Field(default=None, validation_alias="Dimension")
    lead_time: int | None = Field(default=None, validation_alias="leadTime")
    gtin: str | None = None
    rush_service: bool = Field(default=False, validation_alias="isRushService")
    packaging: list[Packaging] = Field(
        default_factory=list,
        validation_alias=AliasPath("ProductPackagingArray", "ProductPackage"),
    )
    shipping_packages: list[Packaging] = Field(
        default_factory=list,
        validation_alias=AliasPath("ShippingPackageArray", "ShippingPackage"),
    )
    """How the part ships, as the case it comes in and how many pieces are in it."""
    effective_date: datetime | None = Field(default=None, validation_alias="effectiveDate")
    end_date: datetime | None = Field(default=None, validation_alias="endDate")
    closeout: bool = Field(default=False, validation_alias="isCloseout")
    caution: bool = Field(default=False, validation_alias="isCaution")
    caution_comment: str | None = Field(default=None, validation_alias="cautionComment")
    on_demand: bool = Field(default=False, validation_alias="isOnDemand")
    hazmat: bool = Field(default=False, validation_alias="isHazmat")

    @property
    def catalog_color(self) -> str | None:
        """The part's catalog (mainframe) color, which web services and orders expect."""
        color = self.primary_color or next(iter(self.colors), None)
        return None if color is None else color.catalog_color


class MarketingPoint(Record):
    """A selling point from a product's description."""

    text: str = Field(validation_alias="pointCopy")
    point_type: str | None = Field(default=None, validation_alias="pointType")


class Category(Record):
    """A category a product is listed under."""

    category: str
    subcategory: str | None = Field(default=None, validation_alias="subCategory")


class RelatedProduct(Record):
    """Another product SanMar relates to this one."""

    relation_type: str = Field(validation_alias="relationType")
    """``Companion Sell``, ``Substitute`` or ``Common Grouping``."""
    product_id: str = Field(validation_alias="productId")
    part_id: str | None = Field(default=None, validation_alias="partId")


class ProductPrice(Record):
    """One price break."""

    quantity_min: int = Field(validation_alias="quantityMin")
    quantity_max: int | None = Field(default=None, validation_alias="quantityMax")
    price: Decimal
    discount_code: str | None = Field(default=None, validation_alias="discountCode")


class PriceGroup(Record):
    """A named set of price breaks, such as ``MSRP``."""

    name: str = Field(validation_alias="groupName")
    currency: str
    description: str | None = None
    prices: list[ProductPrice] = Field(
        default_factory=list,
        validation_alias=AliasPath("ProductPriceArray", "ProductPrice"),
    )


class FobPoint(Record):
    """A place SanMar ships from: one of its warehouses."""

    warehouse: WarehouseNumber = Field(validation_alias="fobId")
    city: str | None = Field(default=None, validation_alias="fobCity")
    state: str | None = Field(default=None, validation_alias="fobState")
    postal_code: str | None = Field(default=None, validation_alias="fobPostalCode")
    country: str | None = Field(default=None, validation_alias="fobCountry")
    currencies: Annotated[list[str], pluck("currency")] = Field(
        default_factory=list,
        validation_alias=AliasPath("CurrencySupportedArray", "CurrencySupported"),
    )
    """The currencies SanMar prices in from here. Only the pricing service reports them."""


class Product(Record):
    """A style, and every color and size of it."""

    product_id: str = Field(validation_alias="productId")
    """The style number, such as ``K500``."""
    name: str = Field(validation_alias="productName")
    descriptions: list[str] = Field(default_factory=list, validation_alias="description")
    """The description, one paragraph or bullet point to an entry."""
    brand: str | None = Field(default=None, validation_alias="productBrand")
    line_name: str | None = Field(default=None, validation_alias="lineName")
    marketing_points: list[MarketingPoint] = Field(
        default_factory=list,
        validation_alias=AliasPath("ProductMarketingPointArray", "ProductMarketingPoint"),
    )
    keywords: Annotated[list[str], pluck("keyword")] = Field(
        default_factory=list,
        validation_alias=AliasPath("ProductKeywordArray", "ProductKeyword"),
    )
    categories: list[Category] = Field(
        default_factory=list,
        validation_alias=AliasPath("ProductCategoryArray", "ProductCategory"),
    )
    related_products: list[RelatedProduct] = Field(
        default_factory=list,
        validation_alias=AliasPath("RelatedProductArray", "RelatedProduct"),
    )
    primary_image_url: str | None = Field(default=None, validation_alias="primaryImageUrl")
    price_groups: list[PriceGroup] = Field(
        default_factory=list,
        validation_alias=AliasPath("ProductPriceGroupArray", "ProductPriceGroup"),
    )
    price_expires_date: datetime | None = Field(default=None, validation_alias="priceExpiresDate")
    parts: list[ProductPart] = Field(
        default_factory=list, validation_alias=AliasPath("ProductPartArray", "ProductPart")
    )
    fob_points: list[FobPoint] = Field(default_factory=list, validation_alias=AliasPath("FobPointArray", "FobPoint"))
    export: bool | None = None
    compliance_info_available: bool | None = Field(default=None, validation_alias="complianceInfoAvailable")
    unspsc_commodity_code: int | None = Field(default=None, validation_alias="unspscCommodityCode")
    last_change_date: datetime | None = Field(default=None, validation_alias="lastChangeDate")
    creation_date: datetime | None = Field(default=None, validation_alias="creationDate")
    effective_date: datetime | None = Field(default=None, validation_alias="effectiveDate")
    end_date: datetime | None = Field(default=None, validation_alias="endDate")
    closeout: bool = Field(default=False, validation_alias="isCloseout")
    caution: bool = Field(default=False, validation_alias="isCaution")
    caution_comment: str | None = Field(default=None, validation_alias="cautionComment")


class PartReference(Record):
    """A product, or one part of it, in a list of changed, closed-out or sellable items."""

    product_id: str = Field(validation_alias="productId")
    part_id: str | None = Field(default=None, validation_alias="partId")


class ProductDataService(PromoStandardsService):
    """SanMar's PromoStandards Product Data service."""

    endpoint = PROMOSTANDARDS_PRODUCT_DATA
    version = "2.0.0"

    def get(self, product_id: str, *, part_id: str | None = None, catalog_color: str | None = None) -> Product:
        """Describe a style, optionally narrowed to one part or one catalog color.

        SanMar recommends asking for whole styles rather than one part at a time.
        """
        request: GetProductRequest = {
            "localizationCountry": COUNTRY,
            "localizationLanguage": LANGUAGE,
            "productId": product_id,
        }
        if part_id is not None:
            request["partId"] = part_id
        if catalog_color is not None:
            request["colorName"] = catalog_color
        result = self._call("getProduct", request)
        check(result)
        if not result.get("Product"):
            message = f"SanMar has no product {product_id}."
            raise NotFoundError(message)
        return Product.model_validate(result["Product"])

    def closeouts(self) -> list[PartReference]:
        """List every part SanMar has discontinued."""
        result = self._call("getProductCloseOut", {})
        return self._references(result, "ProductCloseOutArray", "ProductCloseOut")

    def modified_since(self, since: datetime) -> list[PartReference]:
        """List every part that changed after a point in time."""
        result = self._call("getProductDateModified", {"changeTimeStamp": since})
        return self._references(result, "ProductDateModifiedArray", "ProductDateModified")

    def sellable(
        self,
        product_id: str | None = None,
        *,
        part_id: str | None = None,
        is_sellable: bool = True,
    ) -> list[PartReference]:
        """List the parts SanMar sells, across the catalog or within one style.

        With ``is_sellable=False``, list the parts SanMar no longer sells instead.
        """
        request: GetProductSellableRequest = {"isSellable": is_sellable}
        if product_id is not None:
            request["productId"] = product_id
        if part_id is not None:
            request["partId"] = part_id
        result = self._call("getProductSellable", request)
        return self._references(result, "ProductSellableArray", "ProductSellable")

    @staticmethod
    def _references(result: dict[str, object], array: str, item: str) -> list[PartReference]:
        if check(result, allow_empty=True):
            return []
        wrapper = result.get(array)
        items = wrapper.get(item) if isinstance(wrapper, dict) else None
        return [PartReference.model_validate(reference) for reference in items or []]
