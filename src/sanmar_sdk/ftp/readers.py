"""Streaming SanMar's delimited data files into records, one row at a time.

SanMar's files are large (the extended product file runs to hundreds of thousands of rows),
so nothing here reads a whole file into memory: every reader is a generator over the lines
of an open text stream.

Column names are matched after normalizing them, because SanMar's spelling drifts between
files and guide revisions: ``STYLE#``, ``BACK_MODEL _IMAGE_URL``, ``CATALOG.COLOR`` and
``Whse_ No`` become ``style#``, ``back_model_image_url``, ``catalog_color`` and ``whse_no``.
Records declare their columns by those normalized names.
"""

import csv
import logging
import re
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from pydantic import AliasChoices, ValidationError

from sanmar_sdk.exceptions import FileFormatError

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from sanmar_sdk.base import Record

logger = logging.getLogger("sanmar_sdk")

Source = Path | TextIO
"""A file to read, as a path on disk or a text stream that is already open."""


def normalize_column(name: str) -> str:
    """Normalize a column name for matching: lowercase, with runs of punctuation as ``_``.

    ``#`` is kept, because SanMar uses it to mean "number" (``STYLE#``, ``SALESORDER#``).
    """
    return re.sub(r"[^0-9a-z#]+", "_", name.strip().casefold()).strip("_")


@contextmanager
def open_source(source: Source, encoding: str = "utf-8-sig") -> Iterator[TextIO]:
    """Open a path for reading, or pass an already-open stream through untouched.

    ``utf-8-sig`` reads plain UTF-8 too, and drops the byte-order mark SanMar's CSV files
    start with.
    """
    if isinstance(source, Path):
        with source.open(encoding=encoding, newline="") as stream:
            yield stream
    else:
        yield source


def _required_columns(record: type[Record]) -> list[tuple[str, ...]]:
    """For each column a record cannot do without, the names it may appear under."""
    required: list[tuple[str, ...]] = []
    for name, field in record.model_fields.items():
        if not field.is_required():
            continue
        alias = field.validation_alias
        if isinstance(alias, str):
            required.append((alias,))
        elif isinstance(alias, AliasChoices):
            required.append(tuple(choice for choice in alias.choices if isinstance(choice, str)))
        else:
            required.append((name,))
    return required


def read_delimited[R: Record](
    source: Source,
    record: type[R],
    *,
    columns: Sequence[str],
    delimiter: str = ",",
    encoding: str = "utf-8-sig",
) -> Iterator[R]:
    """Yield one record per row of a delimited SanMar file.

    ``columns`` is the file's layout as SanMar's guide gives it, already normalized. When the
    file starts with a header row, its own column names are used and the guide's order does
    not matter. When it does not, rows must have exactly as many fields as ``columns``.

    Raises
    ------
    ~sanmar_sdk.exceptions.FileFormatError
        If the header lacks a column the record requires, a headerless row has the wrong
        number of fields, or a row does not validate. The error names the line.
    """
    required = _required_columns(record)
    with open_source(source, encoding) as stream:
        reader = csv.reader(stream, delimiter=delimiter)
        names: list[str] | None = None
        headerless = False
        for row in reader:
            if not any(field.strip() for field in row):
                continue
            if names is None:
                normalized = [normalize_column(field) for field in row]
                if len(set(normalized) & set(columns)) >= min(2, len(columns)):
                    names = normalized
                    _check_header(names, columns, required, reader.line_num)
                    continue
                names = list(columns)
                headerless = True
            if headerless:
                _check_width(row, names, reader.line_num)
            values = dict(zip(names, row, strict=False))
            try:
                yield record.model_validate(values)
            except ValidationError as exc:
                raise FileFormatError(str(exc), reader.line_num) from exc


def _check_header(
    names: list[str],
    columns: Sequence[str],
    required: list[tuple[str, ...]],
    line_number: int,
) -> None:
    """Fail on a header without the required columns, and log any other drift."""
    if missing := [" or ".join(options) for options in required if not set(options) & set(names)]:
        message = f"the header has no {', '.join(missing)} column; it has {', '.join(names)}"
        raise FileFormatError(message, line_number)
    if unexpected := sorted(set(names) - set(columns)):
        logger.info("SanMar file has columns this SDK does not read: %s", ", ".join(unexpected))
    if absent := sorted(set(columns) - set(names)):
        logger.info("SanMar file lacks columns its guide lists: %s", ", ".join(absent))


def _check_width(row: list[str], names: Sequence[str], line_number: int) -> None:
    """Fail on a headerless row whose field count does not match the guide's layout."""
    if len(row) != len(names):
        message = f"expected {len(names)} fields, as SanMar's guide lays the file out, but found {len(row)}"
        raise FileFormatError(message, line_number)
