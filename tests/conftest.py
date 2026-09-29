"""Shared fixtures."""

from typing import TYPE_CHECKING

import pytest

from .sftp_server import SFTPServer

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

SFTP_USERNAME = "123456"
SFTP_PASSWORD = "ftp-password"  # noqa: S105 - a throwaway login for the in-process server


@pytest.fixture
def sftp_server(tmp_path: Path) -> Iterator[SFTPServer]:
    """Serve an empty folder over SFTP to customer 123456."""
    root = tmp_path / "sftp"
    root.mkdir()
    server = SFTPServer(root, SFTP_USERNAME, SFTP_PASSWORD)
    yield server
    server.close()
