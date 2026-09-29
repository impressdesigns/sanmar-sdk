"""SanMar's PromoStandards Inventory service, version 2.0.0.

Reports stock for a style, narrowed to some of its sizes and catalog colors, or for up to
200 parts from any styles at once, which suits checking a whole cart in one call. SanMar
does not implement ``getFilterValues``, and caps each warehouse's reported quantity at
3,000.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import AliasPath, Field

from sanmar_sdk._soap import PROMOSTANDARDS_INVENTORY
from sanmar_sdk.base import Record
from sanmar_sdk.common import WarehouseNumber

from ._common import PromoStandardsService, check

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ._wire import GetInventoryLevelsRequest, InventoryFilter

MAX_PART_IDS = 200


class FutureStock(Record):
    """Stock a warehouse expects to receive."""

    quantity: int = Field(validation_alias=AliasPath("Quantity", "value"))
    available_on: datetime = Field(validation_alias="availableOn")


class LocationStock(Record):
    """One part's stock at one warehouse."""

    warehouse: WarehouseNumber = Field(validation_alias="inventoryLocationId")
    quantity: int = Field(validation_alias=AliasPath("inventoryLocationQuantity", "Quantity", "value"))
    """Pieces available, up to SanMar's cap of 3,000."""
    name: str | None = Field(default=None, validation_alias="inventoryLocationName")
    postal_code: str | None = Field(default=None, validation_alias="postalCode")
    country: str | None = None
    future: list[FutureStock] = Field(
        default_factory=list,
        validation_alias=AliasPath("FutureAvailabilityArray", "FutureAvailability"),
    )


class PartStock(Record):
    """One part's stock across SanMar's warehouses."""

    part_id: str = Field(validation_alias="partId")
    """SanMar's unique key for this style, color and size."""
    catalog_color: str | None = Field(default=None, validation_alias="partColor")
    """The catalog (mainframe) color, which web services and orders expect."""
    size: str | None = Field(default=None, validation_alias="labelSize")
    description: str | None = Field(default=None, validation_alias="partDescription")
    quantity: int = Field(default=0, validation_alias=AliasPath("quantityAvailable", "Quantity", "value"))
    """Pieces available across every warehouse."""
    main_part: bool = Field(default=False, validation_alias="mainPart")
    manufactured_item: bool = Field(default=False, validation_alias="manufacturedItem")
    buy_to_order: bool = Field(default=False, validation_alias="buyToOrder")
    replenishment_lead_time: int | None = Field(default=None, validation_alias="replenishmentLeadTime")
    locations: list[LocationStock] = Field(
        default_factory=list,
        validation_alias=AliasPath("InventoryLocationArray", "InventoryLocation"),
    )
    last_modified: datetime | None = Field(default=None, validation_alias="lastModified")


class InventoryService(PromoStandardsService):
    """SanMar's PromoStandards Inventory service."""

    endpoint = PROMOSTANDARDS_INVENTORY
    version = "2.0.0"

    def get(
        self,
        product_id: str,
        *,
        part_ids: Sequence[str] = (),
        sizes: Sequence[str] = (),
        catalog_colors: Sequence[str] = (),
    ) -> list[PartStock]:
        """Report stock for a style, or for a set of parts.

        With no filter, every part of the style is reported. ``sizes`` and
        ``catalog_colors`` narrow the style down. ``part_ids`` asks for up to 200 parts
        from any styles instead; SanMar still needs a valid style in ``product_id``, but
        does not require the parts to belong to it.

        Raises
        ------
        TypeError
            If a filter is a single string rather than a list of them.
        ValueError
            If ``part_ids`` is combined with ``sizes`` or ``catalog_colors``, or lists more
            than 200 parts.
        """
        for name, values in (("part_ids", part_ids), ("sizes", sizes), ("catalog_colors", catalog_colors)):
            if isinstance(values, str):
                message = f"{name} takes a list of strings, not one string."
                raise TypeError(message)
        request: GetInventoryLevelsRequest = {"productId": product_id}
        search: InventoryFilter = {}
        if part_ids:
            if sizes or catalog_colors:
                message = "Filter by part ids, or by sizes and catalog colors, not both."
                raise ValueError(message)
            if len(part_ids) > MAX_PART_IDS:
                message = f"SanMar reports at most {MAX_PART_IDS} parts per call; {len(part_ids)} were given."
                raise ValueError(message)
            search["partIdArray"] = {"partId": list(part_ids)}
        if sizes:
            search["LabelSizeArray"] = {"labelSize": list(sizes)}
        if catalog_colors:
            search["PartColorArray"] = {"partColor": list(catalog_colors)}
        if search:
            request["Filter"] = search
        result = self._call("getInventoryLevels", request)
        if check(result, allow_empty=True):
            return []
        parts = (result.get("Inventory") or {}).get("PartInventoryArray") or {}
        return [PartStock.model_validate(part) for part in parts.get("PartInventory") or []]
