"""Types shared across SanMar's services and files.

The identifiers here are the ones SanMar's services actually match on. SanMar has two color
names for every product, and only one of them works in a request:

- ``catalog_color`` is SanMar's *catalog* or *mainframe* color: the abbreviated name in the
  ``SANMAR_MAINFRAME_COLOR`` column of ``SanMar_SDL_N.csv`` (``CATALOG_COLOR`` in the
  SanMarPI files, ``colorName`` in PromoStandards). Every lookup and every order uses it.
- ``color_name`` is the full display name (``COLOR_NAME``, ``standardColorName``). It is
  for showing to people, and SanMar rejects it in requests: "Athletic Hthr" works where
  "Athletic Heather" does not.

The SDK never mixes the two: a field called ``catalog_color`` is always the catalog color.
"""

from enum import IntEnum, StrEnum
from typing import Annotated

from pydantic import Field

from .base import ORDER_TEXT, Model


class Environment(StrEnum):
    """Which of SanMar's two web service environments to call."""

    PRODUCTION = "https://ws.sanmar.com:8080"
    EDEV = "https://edev-ws.sanmar.com:8080"
    """SanMar's test environment. It needs its own credentials, requested from
    sanmarintegrations@sanmar.com, and its products, prices and inventory may not match
    production."""


class Warehouse(IntEnum):
    """A SanMar warehouse, numbered as SanMar numbers them.

    The number is also the warehouse's PromoStandards FOB id.
    """

    SEATTLE = 1
    CINCINNATI = 2
    DALLAS = 3
    RENO = 4
    ROBBINSVILLE = 5
    JACKSONVILLE = 6
    MINNEAPOLIS = 7
    PHOENIX = 12
    RICHMOND = 31

    @property
    def code(self) -> str:
        """The warehouse's will-call code, which goes in the ship method field."""
        return _WAREHOUSE_DETAILS[self][0]

    @property
    def city(self) -> str:
        """The city the warehouse is in."""
        return _WAREHOUSE_DETAILS[self][1]

    @property
    def state(self) -> str:
        """The two-letter state the warehouse is in."""
        return _WAREHOUSE_DETAILS[self][2]


_WAREHOUSE_DETAILS: dict[Warehouse, tuple[str, str, str]] = {
    Warehouse.SEATTLE: ("PRE", "Seattle", "WA"),
    Warehouse.CINCINNATI: ("CIN", "Cincinnati", "OH"),
    Warehouse.DALLAS: ("COP", "Dallas", "TX"),
    Warehouse.RENO: ("REN", "Reno", "NV"),
    Warehouse.ROBBINSVILLE: ("NJE", "Robbinsville", "NJ"),
    Warehouse.JACKSONVILLE: ("JAC", "Jacksonville", "FL"),
    Warehouse.MINNEAPOLIS: ("MSP", "Minneapolis", "MN"),
    Warehouse.PHOENIX: ("PHX", "Phoenix", "AZ"),
    Warehouse.RICHMOND: ("VA1", "Richmond", "VA"),
}

WarehouseNumber = Annotated[Warehouse | int, Field(union_mode="left_to_right")]
"""A warehouse number as SanMar reports it.

A known warehouse parses to :class:`Warehouse`. A number SanMar has added since this SDK
was released stays a plain ``int`` rather than failing the whole response.
"""


class ShipMethod(StrEnum):
    """How SanMar ships an order.

    The value is the ship method as SanMar's own order services and order files spell it.
    PromoStandards orders split it into a carrier and a service; see
    :meth:`promostandards_freight`.
    """

    UPS_GROUND = "UPS"
    UPS_2ND_DAY = "UPS 2ND DAY"
    UPS_2ND_DAY_AM = "UPS 2ND DAY AM"
    UPS_3RD_DAY = "UPS 3RD DAY"
    UPS_NEXT_DAY = "UPS NEXT DAY"
    UPS_NEXT_DAY_EARLY_AM = "UPS NEXT DAY EA"
    UPS_NEXT_DAY_SAVER = "UPS NEXT DAY SV"
    UPS_SATURDAY = "UPS SATURDAY"
    USPS_GROUND_ADVANTAGE = "USPS PP"
    USPS_PRIORITY_MAIL = "USPS APP"
    PSST = "PSST"
    """SanMar's Pack Separately, Ship Together program. The ship-to must exactly match the
    address SanMar has on file."""
    TRUCK = "TRUCK"
    """Truck freight, for orders over 500 pounds. Not available through PromoStandards."""

    def promostandards_freight(self) -> tuple[str, str]:
        """Return the PromoStandards ``(carrier, service)`` pair for this ship method.

        Raises
        ------
        ValueError
            If SanMar does not offer the ship method through PromoStandards.
        """
        try:
            return _PROMOSTANDARDS_FREIGHT[self]
        except KeyError:
            message = f"SanMar does not offer {self.name} through PromoStandards."
            raise ValueError(message) from None


_PROMOSTANDARDS_FREIGHT: dict[ShipMethod, tuple[str, str]] = {
    ShipMethod.UPS_GROUND: ("UPS", "Ground"),
    ShipMethod.UPS_2ND_DAY: ("UPS", "2ND DAY"),
    ShipMethod.UPS_2ND_DAY_AM: ("UPS", "2ND DAY AM"),
    ShipMethod.UPS_3RD_DAY: ("UPS", "3RD DAY"),
    ShipMethod.UPS_NEXT_DAY: ("UPS", "NEXT DAY"),
    ShipMethod.UPS_NEXT_DAY_EARLY_AM: ("UPS", "NEXT DAY EA"),
    ShipMethod.UPS_NEXT_DAY_SAVER: ("UPS", "NEXT DAY SV"),
    ShipMethod.UPS_SATURDAY: ("UPS", "SATURDAY"),
    ShipMethod.USPS_GROUND_ADVANTAGE: ("USPS", "PP"),
    ShipMethod.USPS_PRIORITY_MAIL: ("USPS", "APP"),
    ShipMethod.PSST: ("PSST", "PSST"),
}


class WillCall(Model):
    """Pick an order up from a warehouse instead of having it shipped.

    Only SanMar's own order services and order files support will call, and only for
    accounts SanMar has set up for warehouse selection.
    """

    warehouse: Warehouse

    @property
    def ship_method(self) -> str:
        """The value SanMar expects in the ship method field."""
        return self.warehouse.code


class ShipTo(Model):
    """Where an order ships.

    Field lengths are the tightest limits across SanMar's order services and order files.
    """

    address1: Annotated[str, Field(min_length=1, max_length=35), ORDER_TEXT]
    """The street address. SanMar asks for the abbreviations ST, AVE, RD, DR and BLVD."""
    city: Annotated[str, Field(min_length=1, max_length=28), ORDER_TEXT]
    state: str = Field(pattern=r"^[A-Z]{2}$")
    """The two-letter state abbreviation."""
    zip_code: str = Field(pattern=r"^\d{5}(-?\d{4})?$")
    """A five-digit ZIP code, or ZIP+4 with or without the dash."""
    company: Annotated[str, Field(min_length=1, max_length=28), ORDER_TEXT] | None = None
    attention: Annotated[str, Field(min_length=1, max_length=35), ORDER_TEXT] | None = None
    """The receiver's name, or the PO number."""
    address2: Annotated[str, Field(min_length=1, max_length=35), ORDER_TEXT] | None = None
    """The suite or apartment number."""
    email: Annotated[str, Field(min_length=3, max_length=105), ORDER_TEXT] | None = None
    """Where SanMar sends the order confirmation and shipping notification.

    When omitted, SanMar uses the default email on the account.
    """
    phone: Annotated[str, Field(min_length=1, max_length=32), ORDER_TEXT] | None = None
    """The receiver's phone number. Only PromoStandards orders carry it."""
    residential: bool = False
    country: str = Field(default="US", pattern=r"^[A-Z]{2}$")


class SkuKey(Model):
    """SanMar's own key for one style, color and size.

    ``INVENTORY_KEY`` and ``SIZE_INDEX`` are in every SanMar product file. The inventory key
    is not the style number. SanMar recommends ordering by key rather than by style, color
    and size, because it cannot be misspelled.
    """

    inventory_key: int = Field(gt=0)
    size_index: int = Field(gt=0)


class StyleColorSize(Model):
    """One style, color and size, named the way SanMar's order services expect."""

    style: str = Field(min_length=1, max_length=60)
    """The style number, as printed in SanMar's catalog (``K500``)."""
    catalog_color: str = Field(min_length=1, max_length=50)
    """The catalog (mainframe) color, not the display color name."""
    size: str = Field(min_length=1, max_length=50)


class StyleQuery(Model):
    """A style to look up, optionally narrowed to one catalog color, one size, or both."""

    style: str = Field(min_length=1, max_length=60)
    """The style number, as printed in SanMar's catalog (``K500``)."""
    catalog_color: Annotated[str, Field(min_length=1, max_length=50)] | None = None
    """The catalog (mainframe) color, not the display color name."""
    size: Annotated[str, Field(min_length=1, max_length=50)] | None = None
