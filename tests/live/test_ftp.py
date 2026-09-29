"""Reading SanMar's real SFTP server with the SDK's readers."""

import itertools
import os
from typing import TYPE_CHECKING

import pytest

from sanmar_sdk.ftp import SanMarFTP

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(scope="module")
def ftp() -> Iterator[SanMarFTP]:
    """Connect with SANMAR_CUSTOMER_NUMBER and SANMAR_FTP_PASSWORD, or skip."""
    customer_number = os.environ.get("SANMAR_CUSTOMER_NUMBER")
    password = os.environ.get("SANMAR_FTP_PASSWORD")
    if not customer_number or not password:
        pytest.skip("set SANMAR_CUSTOMER_NUMBER and SANMAR_FTP_PASSWORD to read the SFTP server")
    with SanMarFTP(customer_number, password, host_key=os.environ.get("SANMAR_SFTP_HOST_KEY")) as connection:
        yield connection


@pytest.mark.parametrize("shortcut", ["catalog", "extended_catalog", "warehouse_inventory"])
def test_product_files_parse(ftp: SanMarFTP, shortcut: str) -> None:
    """The first rows of each product file parse, and name a catalog color."""
    with getattr(ftp, shortcut)() as rows:
        first = list(itertools.islice(rows, 100))
    assert first
    assert all(row.catalog_color for row in first)
