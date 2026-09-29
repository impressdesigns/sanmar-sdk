"""SanMar's own pricing service.

Prices a style (every size and color of it), a style narrowed to a catalog color or a size,
or one style, color and size by its inventory key and size index, including the price for
this account specifically.
"""

from typing import TYPE_CHECKING

from pydantic import Field

from sanmar_sdk._soap import PRICING, Service
from sanmar_sdk.base import Price, Record, SanMarDate
from sanmar_sdk.common import SkuKey, StyleQuery

from ._common import raise_error, web_service_user

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ._wire import PricingItem


class PriceQuote(Record):
    """The prices of one style, color and size."""

    style: str
    catalog_color: str = Field(validation_alias="color")
    """The catalog (mainframe) color, which web services and orders expect."""
    size: str
    inventory_key: int = Field(validation_alias="inventoryKey")
    size_index: int = Field(validation_alias="sizeIndex")
    piece_price: Price = Field(default=None, validation_alias="piecePrice")
    """The price per piece for five pieces or fewer of one style and color."""
    case_price: Price = Field(default=None, validation_alias="casePrice")
    """The price per piece when buying by the case."""
    sale_price: Price = Field(default=None, validation_alias="salePrice")
    sale_start_date: SanMarDate | None = Field(default=None, validation_alias="saleStartDate")
    sale_end_date: SanMarDate | None = Field(default=None, validation_alias="saleEndDate")
    my_price: Price = Field(default=None, validation_alias="myPrice")
    """This account's price."""
    incentive_price: Price = Field(default=None, validation_alias="incentivePrice")


def _item(query: StyleQuery | SkuKey) -> PricingItem:
    if isinstance(query, SkuKey):
        return {"inventoryKey": str(query.inventory_key), "sizeIndex": query.size_index}
    item: PricingItem = {"style": query.style}
    if query.catalog_color is not None:
        item["color"] = query.catalog_color
    if query.size is not None:
        item["size"] = query.size
    return item


class PricingService(Service):
    """SanMar's own pricing service."""

    def get(self, style: str, *, catalog_color: str | None = None, size: str | None = None) -> list[PriceQuote]:
        """Price a style, optionally narrowed to one catalog color, one size, or both."""
        return self.get_many([StyleQuery(style=style, catalog_color=catalog_color, size=size)])

    def get_by_key(self, key: SkuKey) -> list[PriceQuote]:
        """Price one style, color and size by its inventory key and size index."""
        return self.get_many([key])

    def get_many(self, queries: Sequence[StyleQuery | SkuKey]) -> list[PriceQuote]:
        """Price several lookups in one call."""
        if not queries:
            return []
        result = self._soap.call(
            PRICING,
            ("getPricing",),
            {"arg0": [_item(query) for query in queries], "arg1": web_service_user(self._credentials)},
        )
        if result.get("errorOccurred"):
            color_hint = any(isinstance(query, StyleQuery) and query.catalog_color for query in queries)
            raise_error(result.get("message"), color_hint=color_hint)
        return [PriceQuote.model_validate(item) for item in result.get("listResponse") or []]
