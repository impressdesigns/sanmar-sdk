"""SanMar's PromoStandards Pricing and Configuration service, version 1.0.0.

Prices every part of a style at this account's net cost, SanMar's list price (MSRP), or
this account's special pricing. SanMar sells blank goods only, so it implements just
``getConfigurationAndPricing`` and ``getFobPoints``, and nothing about decoration.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import AliasPath, Field

from sanmar_sdk._soap import PROMOSTANDARDS_PRICING
from sanmar_sdk.base import Record
from sanmar_sdk.common import Warehouse

from ._common import PromoStandardsService, check
from .product_data import FobPoint

if TYPE_CHECKING:
    from ._wire import GetConfigurationAndPricingRequest, GetFobPointsRequest

COUNTRY = "US"
LANGUAGE = "EN"
CURRENCY = "USD"


class PriceType(StrEnum):
    """Which price to ask for."""

    NET = "Net"
    """This account's cost."""
    LIST = "List"
    """SanMar's suggested retail price (MSRP)."""
    CUSTOMER = "Customer"
    """This account's special pricing, where SanMar has set some up."""


class PriceBreak(Record):
    """The price per unit from a minimum quantity up."""

    min_quantity: int = Field(validation_alias="minQuantity")
    price: Decimal
    uom: str = Field(validation_alias="priceUom")
    """The unit the price is per, ``EA`` for each piece or ``CA`` for each piece by the case."""
    effective_date: datetime | None = Field(default=None, validation_alias="priceEffectiveDate")
    expiry_date: datetime | None = Field(default=None, validation_alias="priceExpiryDate")
    discount_code: str | None = Field(default=None, validation_alias="discountCode")


class PartPrice(Record):
    """The prices of one part."""

    part_id: str = Field(validation_alias="partId")
    """SanMar's unique key for this style, color and size."""
    description: str | None = Field(default=None, validation_alias="partDescription")
    prices: list[PriceBreak] = Field(default_factory=list, validation_alias=AliasPath("PartPriceArray", "PartPrice"))
    default_part: bool = Field(default=False, validation_alias="defaultPart")


class PricingService(PromoStandardsService):
    """SanMar's PromoStandards Pricing and Configuration service."""

    endpoint = PROMOSTANDARDS_PRICING
    version = "1.0.0"

    def get(
        self,
        product_id: str,
        *,
        part_id: str | None = None,
        price_type: PriceType = PriceType.NET,
        warehouse: Warehouse = Warehouse.SEATTLE,
    ) -> list[PartPrice]:
        """Price every part of a style, or one part.

        SanMar's prices do not vary by warehouse, but the service requires one, so any
        warehouse will do.
        """
        request: GetConfigurationAndPricingRequest = {
            "productId": product_id,
            "currency": CURRENCY,
            "fobId": str(int(warehouse)),
            "priceType": PriceType(price_type).value,
            "localizationCountry": COUNTRY,
            "localizationLanguage": LANGUAGE,
            "configurationType": "Blank",
        }
        if part_id is not None:
            request["partId"] = part_id
        result = self._call("getConfigurationAndPricing", request)
        if check(result, allow_empty=True):
            return []
        parts = (result.get("Configuration") or {}).get("PartArray") or {}
        return [PartPrice.model_validate(part) for part in parts.get("Part") or []]

    def fob_points(self, product_id: str) -> list[FobPoint]:
        """List SanMar's warehouses. The list is the same for every product.

        SanMar asks that this be called at most once a week.
        """
        request: GetFobPointsRequest = {
            "productId": product_id,
            "localizationCountry": COUNTRY,
            "localizationLanguage": LANGUAGE,
        }
        result = self._call("getFobPoints", request)
        if check(result, allow_empty=True):
            return []
        points = result.get("FobPointArray") or {}
        return [FobPoint.model_validate(point) for point in points.get("FobPoint") or []]
