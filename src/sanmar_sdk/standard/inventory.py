"""SanMar's own inventory service.

Reports stock by warehouse for a style, optionally narrowed to a catalog color or a size.
SanMar caps the quantity it reports per warehouse, and asks that this service be used for
a handful of items at a time; for anything more frequent than a live check at ordering
time, it recommends ``sanmar_dip.txt`` or the PromoStandards inventory service.

SanMar answers a lookup by style and color, style and size, or style alone with each size
and warehouse named, but answers a lookup by style, color *and* size with bare numbers in
an order it does not state. This service therefore never sends all three: given a color
and a size, it asks for the color and keeps the matching size itself.
"""

from typing import TYPE_CHECKING

from pydantic import Field

from sanmar_sdk._soap import INVENTORY, Service
from sanmar_sdk.base import OneOrMany, Record
from sanmar_sdk.common import Warehouse, WarehouseNumber

from ._common import raise_error

if TYPE_CHECKING:
    from ._wire import InventoryRequest, WarehouseInventoryRequest


class WarehouseStock(Record):
    """Stock of one style, color and size at one warehouse."""

    warehouse: WarehouseNumber = Field(validation_alias="whseID")
    quantity: int = Field(validation_alias="qty")
    """Stock at this warehouse, capped by SanMar."""
    name: str | None = Field(default=None, validation_alias="whseName")


class SkuStock(Record):
    """Stock of one style, color and size, warehouse by warehouse."""

    style: str
    catalog_color: str = Field(validation_alias="color")
    """The catalog (mainframe) color, which web services and orders expect."""
    size: str
    warehouses: OneOrMany[WarehouseStock] = Field(default_factory=list, validation_alias="whse")

    @property
    def total(self) -> int:
        """Stock across every warehouse."""
        return sum(stock.quantity for stock in self.warehouses)


class InventoryService(Service):
    """SanMar's own inventory service."""

    def _login(self, style: str) -> InventoryRequest:
        return {
            "arg0": str(self._credentials.customer_number),
            "arg1": self._credentials.username,
            "arg2": self._credentials.password,
            "arg3": style,
        }

    def get(self, style: str, *, catalog_color: str | None = None, size: str | None = None) -> list[SkuStock]:
        """Look up stock by warehouse for a style, one catalog color, one size, or both.

        The color must be the catalog (mainframe) color, not the display name.
        """
        request = self._login(style)
        if catalog_color is not None:
            request["arg4"] = catalog_color
        elif size is not None:
            request["arg5"] = size
        # SanMar's WSDL does not describe the type it answers with here, so zeep cannot
        # read it; the response is read as plain XML instead.
        body = self._soap.call_unparsed(INVENTORY, ("getInventoryQtyForStyleColorSize",), request)
        result = body.get("return") or {}
        if str(result.get("errorOccurred", "false")).casefold() == "true":
            raise_error(result.get("message"), color_hint=catalog_color is not None)
        response = result.get("response") or {}
        skus = (response.get("skus") or {}).get("sku") or []
        stock = [
            SkuStock.model_validate({**sku, "style": response.get("style", style)})
            for sku in (skus if isinstance(skus, list) else [skus])
        ]
        if size is not None:
            stock = [sku for sku in stock if sku.size.casefold() == size.casefold()]
        return stock

    def get_quantity(self, style: str, catalog_color: str, size: str, warehouse: Warehouse | int) -> int:
        """Look up the stock of one style, catalog color and size at one warehouse."""
        request: WarehouseInventoryRequest = {
            **self._login(style),
            "arg4": catalog_color,
            "arg5": size,
            "arg6": str(int(warehouse)),
        }
        result = self._soap.call(INVENTORY, ("getInventoryQtyForStyleColorSizeByWhse",), request)
        if result.get("errorOccurred"):
            raise_error(result.get("message"), color_hint=True)
        return int(result.get("response") or 0)
