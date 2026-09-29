"""Testing the model bases and the field types SanMar's data needs."""

from datetime import date
from decimal import Decimal
from typing import Annotated

import pytest
from pydantic import AliasChoices, AliasPath, Field, ValidationError

from sanmar_sdk.base import ORDER_TEXT, CommaSeparated, Model, Record, SanMarDate, SemicolonSeparated


class Line(Record):
    """A record shaped like a SanMar response line."""

    part_id: str = Field(validation_alias=AliasChoices("partId", "part_id"))
    price: Decimal | None = None
    error: bool = Field(default=False, validation_alias=AliasChoices("errorOccurred", "errorOccured", "error"))
    parts: list[str] = Field(
        default_factory=list, validation_alias=AliasChoices(AliasPath("PartArray", "Part"), "parts")
    )


class Order(Model):
    """A model shaped like something a caller builds."""

    quantity: int
    note: Annotated[str, ORDER_TEXT] | None = None


def test_record_treats_none_and_blank_as_absent() -> None:
    """A None from zeep and a blank column from a data file both fall back to the default."""
    line = Line.model_validate({"partId": "208284", "price": "  ", "errorOccurred": None, "PartArray": None})
    assert line == Line(part_id="208284")


def test_record_unwraps_array_wrappers() -> None:
    """A wrapped array is read through the wrapper; an empty one is an empty list."""
    assert Line.model_validate({"partId": "1", "PartArray": {"Part": ["a", "b"]}}).parts == ["a", "b"]
    assert Line.model_validate({"partId": "1", "PartArray": {"Part": None}}).parts == []


def test_record_accepts_either_spelling_and_lax_values() -> None:
    """SanMar's alternate spellings and text-typed values are accepted."""
    line = Line.model_validate({"partId": " 208284 ", "price": 2.59, "errorOccured": "true", "surprise": 1})
    assert line == Line(part_id="208284", price=Decimal("2.59"), error=True)


def test_record_is_immutable() -> None:
    """Records cannot be changed after parsing."""
    line = Line(part_id="1")
    with pytest.raises(ValidationError, match="frozen"):
        line.part_id = "2"  # type: ignore[misc]  # ty: ignore[invalid-assignment]


def test_model_is_strict() -> None:
    """A caller's model does not coerce text into numbers, and rejects unknown fields."""
    with pytest.raises(ValidationError, match="valid integer"):
        Order.model_validate({"quantity": "12"})
    with pytest.raises(ValidationError, match="Extra inputs"):
        Order.model_validate({"quantity": 12, "colour": "Black"})


@pytest.mark.parametrize("text", ["Rush, please", "Café"], ids=["comma", "non-ascii"])
def test_order_text_rejects_what_sanmar_cannot_take(text: str) -> None:
    """Commas split SanMar's order files, and those files are ASCII."""
    with pytest.raises(ValidationError, match="SanMar orders"):
        Order(quantity=1, note=text)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("06/18/2015", date(2015, 6, 18)),
        ("1/5/2016", date(2016, 1, 5)),
        ("2023-05-19", date(2023, 5, 19)),
        ("2023-05-19T12:51:32.780", date(2023, 5, 19)),
        ("2023-01-12T22:44:42.467-08:00", date(2023, 1, 12)),
    ],
)
def test_sanmar_dates(value: str, expected: date) -> None:
    """Dates parse from the US format SanMar's files use and from ISO timestamps."""

    class Dated(Record):
        when: SanMarDate

    assert Dated.model_validate({"when": value}).when == expected


def test_delimited_lists() -> None:
    """Delimited text splits into its non-blank parts."""

    class Lists(Record):
        categories: SemicolonSeparated
        keywords: CommaSeparated

    parsed = Lists.model_validate({"categories": "T-Shirts; Tall;", "keywords": "polo, polos,,xs"})
    assert parsed == Lists(categories=["T-Shirts", "Tall"], keywords=["polo", "polos", "xs"])
