"""Testing the types shared across SanMar's services and files."""

from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from sanmar_sdk import ShipMethod, ShipTo, SkuKey, StyleQuery, Warehouse, WarehouseNumber, WillCall

SHIP_TO: dict[str, Any] = {
    "address1": "1404 W Main St",
    "city": "Carrollton",
    "state": "TX",
    "zip_code": "75006",
}


def test_warehouses_carry_their_will_call_codes() -> None:
    """Every warehouse in the guides has a code, city and state."""
    assert [(warehouse.value, warehouse.code) for warehouse in Warehouse] == [
        (1, "PRE"),
        (2, "CIN"),
        (3, "COP"),
        (4, "REN"),
        (5, "NJE"),
        (6, "JAC"),
        (7, "MSP"),
        (12, "PHX"),
        (31, "VA1"),
    ]
    assert (Warehouse.RENO.city, Warehouse.RENO.state) == ("Reno", "NV")


@pytest.mark.parametrize(
    ("value", "expected"),
    [(1, Warehouse.SEATTLE), ("31", Warehouse.RICHMOND), (99, 99), ("99", 99)],
    ids=["known-int", "known-text", "new-int", "new-text"],
)
def test_warehouse_numbers_tolerate_new_warehouses(value: object, expected: Warehouse | int) -> None:
    """A known number parses to a Warehouse; an unknown one stays an int."""
    parsed: Warehouse | int = TypeAdapter(WarehouseNumber).validate_python(value)
    assert parsed == expected
    assert type(parsed) is type(expected)


def test_ship_methods_map_to_promostandards() -> None:
    """Every ship method but truck has a PromoStandards carrier and service."""
    assert ShipMethod.UPS_GROUND.promostandards_freight() == ("UPS", "Ground")
    assert ShipMethod.UPS_NEXT_DAY_SAVER.promostandards_freight() == ("UPS", "NEXT DAY SV")
    assert ShipMethod.USPS_PRIORITY_MAIL.promostandards_freight() == ("USPS", "APP")
    assert ShipMethod.PSST.promostandards_freight() == ("PSST", "PSST")
    with pytest.raises(ValueError, match="TRUCK through PromoStandards"):
        ShipMethod.TRUCK.promostandards_freight()


def test_will_call_uses_the_warehouse_code() -> None:
    """A will-call order puts the warehouse code in the ship method field."""
    assert WillCall(warehouse=Warehouse.RENO).ship_method == "REN"


def test_ship_to_defaults() -> None:
    """Only the street, city, state and ZIP are required."""
    ship_to = ShipTo.model_validate(SHIP_TO)
    assert (ship_to.country, ship_to.residential, ship_to.company) == ("US", False, None)


@pytest.mark.parametrize("zip_code", ["75006", "98007-1156", "980071156"])
def test_ship_to_accepts_sanmar_zip_formats(zip_code: str) -> None:
    """Five digits, or ZIP+4 with or without the dash."""
    assert ShipTo.model_validate({**SHIP_TO, "zip_code": zip_code}).zip_code == zip_code


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ({"zip_code": "7506"}, "should match pattern"),
        ({"state": "Texas"}, "should match pattern"),
        ({"company": "A" * 29}, "at most 28 characters"),
        ({"address1": "1404 W Main St, Suite 2"}, "cannot contain commas"),
        ({"attention": "Zoë"}, "must be ASCII"),
        ({"residential": "N"}, "valid boolean"),
    ],
)
def test_ship_to_enforces_sanmar_limits(change: dict[str, Any], problem: str) -> None:
    """Addresses SanMar would reject fail when they are built."""
    with pytest.raises(ValidationError, match=problem):
        ShipTo.model_validate({**SHIP_TO, **change})


def test_identities_are_strict() -> None:
    """Keys must be positive integers, and a lookup needs a style."""
    assert SkuKey(inventory_key=20828, size_index=4).inventory_key == 20828  # noqa: PLR2004
    with pytest.raises(ValidationError):
        SkuKey(inventory_key="20828", size_index=4)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValidationError):
        StyleQuery(style="")
    assert StyleQuery(style="K500", size="XL").catalog_color is None
