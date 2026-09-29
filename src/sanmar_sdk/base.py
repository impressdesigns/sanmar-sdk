"""Base classes and field types shared by every model in the SDK.

There are two kinds of model:

- :class:`Model` is anything a caller builds and hands to the SDK: a purchase order, a
  lookup. It is strict — a string is not coerced into a number, a float is not accepted as
  money — so a mistake fails when the model is built, before anything is sent to SanMar.
- :class:`Record` is anything the SDK parses out of a SanMar response or data file. SanMar
  types almost everything as text, so records coerce leniently, ignore fields they do not
  model, and treat a missing or blank value as absent.
"""

import re
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, model_validator


class Model(BaseModel):
    """A strict, immutable model that a caller builds."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


def _drop_empty(value: Any) -> Any:  # noqa: ANN401 - walks arbitrary parsed data
    """Drop ``None`` and blank strings from mappings, recursively.

    zeep reports every element a schema declares, with ``None`` for the ones SanMar left
    out, and SanMar's data files leave empty columns blank. Dropping both lets a record's
    defaults apply, and lets an empty array wrapper fall back to an empty list.
    """
    if isinstance(value, Mapping):
        return {
            key: _drop_empty(item)
            for key, item in value.items()
            if item is not None and not (isinstance(item, str) and not item.strip())
        }
    return value


class Record(BaseModel):
    """An immutable model parsed from something SanMar sent."""

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
        validate_by_name=True,
        validate_by_alias=True,
        str_strip_whitespace=True,
    )

    @model_validator(mode="before")
    @classmethod
    def _drop_empty_values(cls, data: Any) -> Any:  # noqa: ANN401 - runs before validation
        return _drop_empty(data)


def _parse_date(value: Any) -> Any:  # noqa: ANN401 - runs before validation
    """Accept the date formats SanMar uses, alongside ISO 8601.

    SanMar's data files write dates as ``MM/DD/YYYY`` (sometimes without leading zeros),
    while its web services use ISO dates and timestamps.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        text = value.strip()
        if match := re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text):
            month, day, year = (int(part) for part in match.groups())
            return date(year, month, day)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}[T ].*", text):
            return datetime.fromisoformat(text).date()
    return value


def _as_list(value: Any) -> Any:  # noqa: ANN401 - runs before validation
    """Wrap a single value in a list, for elements that repeat only sometimes."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _split_list(separator: str) -> BeforeValidator:
    """Split a delimited string into its non-blank, stripped parts."""

    def split(value: Any) -> Any:  # noqa: ANN401 - runs before validation
        if isinstance(value, str):
            return [part.strip() for part in value.split(separator) if part.strip()]
        return value

    return BeforeValidator(split)


def _parse_price(value: Any) -> Any:  # noqa: ANN401 - runs before validation
    """Read a price the way SanMar writes one, treating "not available" as no price."""
    if isinstance(value, str):
        text = value.strip().removeprefix("$").replace(",", "")
        return None if text.upper() in {"NA", "N/A", "NLA"} else text
    return value


SanMarDate = Annotated[date, BeforeValidator(_parse_date)]
"""A date in any of the formats SanMar sends."""

type OneOrMany[T] = Annotated[list[T], BeforeValidator(_as_list)]
"""A list that SanMar may send as a single item when there is only one."""

Price = Annotated[Decimal | None, BeforeValidator(_parse_price)]
"""A dollar amount, or ``None`` where SanMar has none (a blank, ``NA`` or ``NLA``)."""

CommaSeparated = Annotated[list[str], _split_list(",")]
"""A comma-separated list, split into its parts."""

SemicolonSeparated = Annotated[list[str], _split_list(";")]
"""A semicolon-separated list, split into its parts."""


def _check_order_text(value: str) -> str:
    """Reject characters SanMar cannot accept in an order.

    SanMar's order processor splits on commas, and its order files are ASCII.
    """
    if "," in value:
        message = "SanMar orders cannot contain commas."
        raise ValueError(message)
    if not value.isascii():
        message = "SanMar orders must be ASCII."
        raise ValueError(message)
    return value


ORDER_TEXT = AfterValidator(_check_order_text)
"""Marks a string as text that goes into a SanMar order, which allows no commas and only ASCII.

It goes after the field's length limits, so a too-long value is reported in characters::

    city: Annotated[str, Field(max_length=28), ORDER_TEXT]
"""
