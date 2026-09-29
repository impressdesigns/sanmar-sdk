"""SanMar's SFTP server.

SanMar serves its data files over SFTP at ``ftp.sanmar.com``, port 2200. The username is the
SanMar customer number, and the password is the FTP password SanMar issues during
onboarding, which is not the SanMar.com password the web services use.

The server's host key is checked like any SSH server's. Either have it in a known_hosts
file, or pin it: get it once with ``ssh-keyscan -p 2200 ftp.sanmar.com``, check it, and pass
the key (``ecdsa-sha2-nistp256 AAAA...``) as ``host_key``. An unknown key is refused.

Everything is read as a stream: a product file is parsed row by row as it downloads, and
never held in memory or written to disk.
"""

import base64
import fnmatch
import io
import time
import zipfile
from contextlib import AbstractContextManager, contextmanager
from pathlib import PurePosixPath
from typing import IO, TYPE_CHECKING, Self, TextIO, cast

import paramiko
from paramiko.ssh_exception import IncompatiblePeer

from sanmar_sdk.exceptions import AuthenticationError, NotFoundError, SanMarConnectionError

from .catalog import read_catalog, read_extended_catalog, read_product_information
from .inventory import read_warehouse_inventory
from .orders import OrderFiles, read_holding, render_order_files, render_release_file

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence
    from pathlib import Path
    from types import TracebackType

    from paramiko.sftp_client import SFTPClient

    from sanmar_sdk.orders import PurchaseOrder

    from .catalog import CatalogProduct, ProductInformation
    from .inventory import WarehouseInventory
    from .orders import HoldingLine

HOST = "ftp.sanmar.com"
PORT = 2200

PRODUCT_FOLDER = "SanMarPDD"
"""Where SanMar keeps the product, inventory and pricing files, refreshed nightly by 6 AM
Pacific."""
PRODUCT_INFORMATION_FOLDER = "SanMarPDD/SanMarPI"
"""Where the product information web service writes the files it is asked for."""
ORDER_FOLDER = "In"
RELEASE_FOLDER = "Release"
ACKNOWLEDGEMENT_FOLDERS = ("Holding", "Done")
"""Where Holding files appear, and where SanMar moves them once an order is processed."""


def _parse_host_key(text: str) -> paramiko.PKey:
    """Read a host key as ``ssh-keyscan`` prints it, with or without the host in front."""
    parts = text.split()
    if len(parts) >= 3:  # noqa: PLR2004 - "host type key", as a known_hosts line has it
        parts = parts[1:]
    if len(parts) != 2:  # noqa: PLR2004 - "type key"
        message = f"Expected a host key like 'ecdsa-sha2-nistp256 AAAA...', not {text!r}."
        raise ValueError(message)
    key_type, key_data = parts
    return paramiko.PKey.from_type_string(key_type, base64.b64decode(key_data))


class SanMarFTP:
    """A connection to SanMar's SFTP server.

    Use it as a context manager, and read files inside the ``with`` block::

        with SanMarFTP(123456, "ftp-password", host_key="ecdsa-sha2-nistp256 AAAA...") as ftp:
            with ftp.catalog() as products:
                for product in products:
                    ...

    Parameters
    ----------
    customer_number
        The SanMar customer number, which is the SFTP username.
    password
        The FTP password SanMar issued. SanMar.com logins do not work here.
    host, port
        SanMar's SFTP server.
    host_key
        The server's public key, to trust it without a known_hosts entry.
    known_hosts
        A known_hosts file to trust instead of the system's.
    timeout
        Seconds to wait for the connection.
    """

    def __init__(  # noqa: PLR0913 - every argument is a distinct connection setting
        self,
        customer_number: int | str,
        password: str,
        *,
        host: str = HOST,
        port: int = PORT,
        host_key: str | None = None,
        known_hosts: Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Prepare a connection; nothing connects until the ``with`` block starts."""
        self.host = host
        self.port = port
        self._username = str(customer_number)
        self._password = password
        self._host_key = None if host_key is None else _parse_host_key(host_key)
        self._known_hosts = known_hosts
        self._timeout = timeout
        self._ssh: paramiko.SSHClient | None = None
        self._sftp: SFTPClient | None = None

    def __enter__(self) -> Self:
        """Connect."""
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Disconnect."""
        self.close()

    def connect(self) -> None:
        """Connect and log in, verifying the server's host key."""
        ssh = paramiko.SSHClient()
        if self._known_hosts is None:
            ssh.load_system_host_keys()
        else:
            ssh.load_host_keys(str(self._known_hosts))
        if self._host_key is not None:
            name = self.host if self.port == 22 else f"[{self.host}]:{self.port}"  # noqa: PLR2004 - SSH's port
            ssh.get_host_keys().add(name, self._host_key.get_name(), self._host_key)
        ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
        try:
            ssh.connect(
                self.host,
                self.port,
                username=self._username,
                password=self._password,
                timeout=self._timeout,
                allow_agent=False,
                look_for_keys=False,
            )
            self._sftp = ssh.open_sftp()
        except paramiko.AuthenticationException as exc:
            ssh.close()
            message = (
                "SanMar refused the SFTP login. The username is the customer number, and the "
                "password is the FTP password SanMar issued, not a SanMar.com password."
            )
            raise AuthenticationError(message) from exc
        except IncompatiblePeer as exc:
            ssh.close()
            message = (
                f"Could not agree on encryption with {self.host}:{self.port}: {exc}. SanMar's server "
                f"only speaks older SSH algorithms; this SDK needs paramiko 4, not {paramiko.__version__}."
            )
            raise SanMarConnectionError(message) from exc
        except (paramiko.SSHException, OSError) as exc:
            ssh.close()
            message = f"Could not connect to {self.host}:{self.port}: {exc}"
            if "known_hosts" in str(exc):
                message += (
                    f". Its host key is not trusted; get it with `ssh-keyscan -p {self.port} {self.host}` "
                    "and pass it as host_key."
                )
            raise SanMarConnectionError(message) from exc
        self._ssh = ssh

    def close(self) -> None:
        """Disconnect. Safe to call more than once."""
        if self._sftp is not None:
            self._sftp.close()
            self._sftp = None
        if self._ssh is not None:
            self._ssh.close()
            self._ssh = None

    @property
    def sftp(self) -> SFTPClient:
        """The underlying paramiko SFTP session, for anything this class does not cover."""
        if self._sftp is None:
            message = "Not connected; use SanMarFTP as a context manager."
            raise SanMarConnectionError(message)
        return self._sftp

    def list_folder(self, folder: str = "") -> list[str]:
        """List a folder's entries by name, sorted. Folder names match case-insensitively."""
        return sorted(self.sftp.listdir(self.resolve(folder) if folder else "."))

    def find(self, folder: str, pattern: str) -> list[str]:
        """List the files in a folder whose names match a shell-style pattern, ignoring case.

        Names come back sorted. SanMar dates the brand and category files it writes on
        request as ``MM-DD-YYYY``, so compare those dates to find the newest::

            ftp.find("SanMarPDD/SanMarPI", "Brand_OGIO_*.csv")
        """
        return [name for name in self.list_folder(folder) if fnmatch.fnmatch(name.casefold(), pattern.casefold())]

    def resolve(self, path: str) -> str:
        """Find a path on the server, matching each part of it case-insensitively.

        SanMar's guides spell the same file ``SanMar_SDL_N.csv`` and ``Sanmar_SDL_N.csv``.
        An exact match wins over a case-insensitive one.

        Raises
        ------
        ~sanmar_sdk.exceptions.NotFoundError
            If some part of the path does not exist; the error lists what does.
        """
        resolved: list[str] = []
        for part in PurePosixPath(path).parts:
            if part == "/":
                continue
            names = self.sftp.listdir("/".join(resolved) or ".")
            if part in names:
                resolved.append(part)
                continue
            matches = [name for name in names if name.casefold() == part.casefold()]
            if not matches:
                where = "/".join(resolved) or "the top folder"
                message = f"{part} is not in {where}; it has {', '.join(sorted(names))}."
                raise NotFoundError(message)
            resolved.append(matches[0])
        return "/".join(resolved)

    @contextmanager
    def open(self, path: str, *, prefetch: bool = True) -> Iterator[IO[bytes]]:
        """Open a remote file for reading, as bytes.

        ``prefetch`` requests the whole file ahead of reading, which is much faster for
        reading straight through; turn it off for random access.
        """
        with self.sftp.open(self.resolve(path), "rb") as remote:
            if prefetch:
                remote.prefetch(max_concurrent_requests=64)
            # paramiko's file is a working binary stream (read, readinto, seek and tell are
            # all there), but its stubs do not declare it one.
            yield cast("IO[bytes]", remote)

    @contextmanager
    def open_text(self, path: str, *, member: str | None = None, encoding: str = "utf-8-sig") -> Iterator[TextIO]:
        """Open a remote text file, or a text file inside a remote zip archive.

        For a ``.zip`` path, ``member`` names the file inside it; it may be left out when the
        archive holds a single ``.csv`` or ``.txt`` file.
        """
        archive = path.casefold().endswith(".zip") or member is not None
        with self.open(path, prefetch=not archive) as remote:
            if not archive:
                yield io.TextIOWrapper(remote, encoding=encoding, newline="")
                return
            with zipfile.ZipFile(remote) as zip_file:
                name = member or _only_text_member(zip_file, path)
                with zip_file.open(name) as contents:
                    yield io.TextIOWrapper(contents, encoding=encoding, newline="")

    def download(self, path: str, destination: Path) -> Path:
        """Copy a remote file to ``destination`` (a file, or a folder to put it in)."""
        remote = self.resolve(path)
        if destination.is_dir():
            destination /= PurePosixPath(remote).name
        self.sftp.get(remote, str(destination))
        return destination

    @contextmanager
    def stream[R](
        self,
        path: str,
        reader: Callable[[TextIO], Iterator[R]],
        *,
        member: str | None = None,
        encoding: str = "utf-8-sig",
    ) -> Iterator[Iterator[R]]:
        """Stream a remote file through one of this package's readers.

        The rows are read as the file downloads, and only while the ``with`` block is open::

            with ftp.stream("SanMarPDD/sanmar_dpc.csv", read_price_changes) as changes:
                for change in changes:
                    ...
        """
        with self.open_text(path, member=member, encoding=encoding) as stream:
            yield reader(stream)

    def catalog(self) -> AbstractContextManager[Iterator[CatalogProduct]]:
        """Stream ``SanMar_SDL_N.csv``, SanMar's main product file."""
        return self.stream(f"{PRODUCT_FOLDER}/SanMar_SDL_N.csv", read_catalog)

    def extended_catalog(self) -> AbstractContextManager[Iterator[CatalogProduct]]:
        """Stream ``SanMar_EPDD.csv``: the product file, with stock across all warehouses."""
        return self.stream(f"{PRODUCT_FOLDER}/SanMar_EPDD.csv", read_extended_catalog)

    def warehouse_inventory(self) -> AbstractContextManager[Iterator[WarehouseInventory]]:
        """Stream ``sanmar_dip.txt``: stock by warehouse, with current prices, refreshed hourly."""
        return self.stream(f"{PRODUCT_FOLDER}/sanmar_dip.txt", read_warehouse_inventory)

    def product_information(self, file_name: str) -> AbstractContextManager[Iterator[ProductInformation]]:
        """Stream a file the product information web service wrote to ``SanMarPDD/SanMarPI``."""
        return self.stream(f"{PRODUCT_INFORMATION_FOLDER}/{file_name}", read_product_information)

    def upload_orders(self, batch: str, orders: Sequence[PurchaseOrder]) -> OrderFiles:
        """Upload a batch of orders, without releasing them for processing.

        SanMar acknowledges the batch with a Holding file (see :meth:`holding`) and holds
        the orders until :meth:`release_orders` releases them, for up to two weeks. These
        are production orders; SanMar has no test environment for SFTP ordering.
        """
        files = render_order_files(batch, orders)
        order_folder = self.resolve(ORDER_FOLDER)
        for name, contents in ((files.cust_info_name, files.cust_info), (files.details_name, files.details)):
            self.sftp.putfo(io.BytesIO(contents.encode("ascii")), f"{order_folder}/{name}")
        return files

    def release_orders(
        self,
        batch: str,
        po_numbers: Sequence[str],
        *,
        release_number: int = 1,
        delay: float = 5.0,
    ) -> str:
        """Release some or all of an uploaded batch's orders for processing.

        Each release of the same batch needs the next ``release_number``. SanMar asks for a
        pause of several seconds between uploading a batch and releasing it; ``delay``
        waits that long first. Returns the release file's name.
        """
        name, contents = render_release_file(batch, po_numbers, release_number)
        time.sleep(delay)
        self.sftp.putfo(io.BytesIO(contents.encode("ascii")), f"{self.resolve(RELEASE_FOLDER)}/{name}")
        return name

    @contextmanager
    def holding(self, batch: str) -> Iterator[Iterator[HoldingLine]]:
        """Stream SanMar's acknowledgement of an uploaded batch, once it exists.

        SanMar writes it to ``Holding`` within about 15 minutes of the upload, and moves it
        to ``Done`` once the orders are processed.

        Raises
        ------
        ~sanmar_sdk.exceptions.NotFoundError
            If there is no Holding file for the batch yet.
        """
        for folder in ACKNOWLEDGEMENT_FOLDERS:
            try:
                names = self.list_folder(folder)
            except NotFoundError:
                continue
            for name in names:
                if name.casefold().startswith(batch.casefold()) and "holding" in name.casefold():
                    with self.stream(f"{folder}/{name}", read_holding) as lines:
                        yield lines
                    return
        message = f"No Holding file for batch {batch} yet; SanMar writes one within about 15 minutes."
        raise NotFoundError(message)


def _only_text_member(zip_file: zipfile.ZipFile, path: str) -> str:
    """Name the one ``.csv`` or ``.txt`` file in an archive, when there is exactly one."""
    names = [name for name in zip_file.namelist() if name.casefold().endswith((".csv", ".txt"))]
    if len(names) != 1:
        message = f"{path} holds {len(names)} text files; name the one to read as member=."
        raise NotFoundError(message)
    return names[0]
