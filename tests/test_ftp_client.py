"""Testing the SFTP client against an in-process SFTP server."""

import shutil
import zipfile
from pathlib import Path

import pytest

from sanmar_sdk import AuthenticationError, NotFoundError, SanMarConnectionError, ShipMethod, ShipTo, SkuKey
from sanmar_sdk.ftp import SanMarFTP, read_price_changes
from sanmar_sdk.ftp.client import _parse_host_key
from sanmar_sdk.orders import OrderLine, PurchaseOrder

from .conftest import SFTP_PASSWORD, SFTP_USERNAME
from .sftp_server import SFTPServer

FILES = Path(__file__).parent / "fixtures" / "files"


def _connect(server: SFTPServer, tmp_path: Path, **overrides: object) -> SanMarFTP:
    """Build a client for the test server that trusts only its pinned key."""
    known_hosts = tmp_path / "known_hosts"
    known_hosts.touch()
    settings: dict[str, object] = {
        "host": "127.0.0.1",
        "port": server.port,
        "host_key": server.host_key_line,
        "known_hosts": known_hosts,
        "timeout": 5.0,
        **overrides,
    }
    return SanMarFTP(SFTP_USERNAME, SFTP_PASSWORD, **settings)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]


def _publish(server: SFTPServer, *names: str, folder: str = "SanMarPDD") -> Path:
    """Put fixture files where SanMar keeps them."""
    target = server.root / folder
    target.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy(FILES / name, target / name)
    return target


def test_pinned_host_key_is_trusted(sftp_server: SFTPServer, tmp_path: Path) -> None:
    """A server presenting the pinned key is accepted, and its folders listed."""
    _publish(sftp_server, "SanMar_SDL_N.csv")
    with _connect(sftp_server, tmp_path) as ftp:
        assert ftp.list_folder() == ["SanMarPDD"]
        assert ftp.list_folder("sanmarpdd") == ["SanMar_SDL_N.csv"]


def test_legacy_ssh_rsa_servers_are_supported(tmp_path: Path) -> None:
    """A server that signs only with SHA-1 ssh-rsa, as SanMar's does, can be connected to."""
    root = tmp_path / "legacy"
    root.mkdir()
    server = SFTPServer(root, SFTP_USERNAME, SFTP_PASSWORD, legacy_rsa=True)
    try:
        with _connect(server, tmp_path) as ftp:
            channel = ftp.sftp.get_channel()
            assert channel is not None
            assert channel.get_transport().host_key_type == "ssh-rsa"  # ty: ignore[unresolved-attribute]
    finally:
        server.close()


def test_unknown_host_key_is_refused(sftp_server: SFTPServer, tmp_path: Path) -> None:
    """Without the key pinned or in known_hosts, the connection is refused."""
    with pytest.raises(SanMarConnectionError, match=r"ssh-keyscan -p \d+ 127\.0\.0\.1"):
        _connect(sftp_server, tmp_path, host_key=None).connect()


def test_wrong_host_key_is_refused(sftp_server: SFTPServer, tmp_path: Path) -> None:
    """A server presenting a different key than the pinned one is refused."""
    impostor = SFTPServer(sftp_server.root, SFTP_USERNAME, SFTP_PASSWORD)
    try:
        with pytest.raises(SanMarConnectionError):
            _connect(sftp_server, tmp_path, host_key=impostor.host_key_line).connect()
    finally:
        impostor.close()


def test_wrong_password_is_an_authentication_error(sftp_server: SFTPServer, tmp_path: Path) -> None:
    """A rejected login explains which password SanMar expects."""
    known_hosts = tmp_path / "known_hosts"
    known_hosts.touch()
    client = SanMarFTP(
        SFTP_USERNAME,
        "sanmar.com-password",
        host="127.0.0.1",
        port=sftp_server.port,
        host_key=sftp_server.host_key_line,
        known_hosts=known_hosts,
        timeout=5.0,
    )
    with pytest.raises(AuthenticationError, match=r"not a SanMar\.com password"):
        client.connect()


def test_using_a_closed_connection_fails_clearly(sftp_server: SFTPServer, tmp_path: Path) -> None:
    """Reading outside the ``with`` block says so."""
    ftp = _connect(sftp_server, tmp_path)
    with pytest.raises(SanMarConnectionError, match="Not connected"):
        ftp.list_folder()


def test_paths_resolve_case_insensitively(sftp_server: SFTPServer, tmp_path: Path) -> None:
    """SanMar's guides mix SanMar_ and Sanmar_; either finds the file."""
    _publish(sftp_server, "SanMar_SDL_N.csv")
    with _connect(sftp_server, tmp_path) as ftp:
        assert ftp.resolve("sanmarpdd/Sanmar_SDL_N.CSV") == "SanMarPDD/SanMar_SDL_N.csv"
        with pytest.raises(NotFoundError, match=r"SanMar_EPDD\.csv is not in SanMarPDD; it has SanMar_SDL_N\.csv"):
            ftp.resolve("SanMarPDD/SanMar_EPDD.csv")


def test_find_matches_patterns_regardless_of_case(sftp_server: SFTPServer, tmp_path: Path) -> None:
    """Dated files SanMar writes on request are found by pattern."""
    target = _publish(sftp_server, folder="SanMarPDD/SanMarPI")
    for name in ("Brand_OGIO_06-01-2026.csv", "brand_ogio_06-08-2026.csv", "Category_Caps_06-01-2026.csv"):
        (target / name).write_text("", encoding="utf-8")
    with _connect(sftp_server, tmp_path) as ftp:
        assert ftp.find("sanmarpdd/sanmarpi", "Brand_OGIO_*.csv") == [
            "Brand_OGIO_06-01-2026.csv",
            "brand_ogio_06-08-2026.csv",
        ]


def test_newest_compares_the_dates_in_file_names(sftp_server: SFTPServer, tmp_path: Path) -> None:
    """The newest file is found by the date in its name, which sorts wrong as text."""
    target = _publish(sftp_server, folder="SanMarPDD/SanMarPI")
    for name in ("Brand_OGIO_12-30-2025.csv", "Brand_OGIO_01-02-2026.csv", "Brand_OGIO_13-45-2026.csv"):
        (target / name).write_text("", encoding="utf-8")
    with _connect(sftp_server, tmp_path) as ftp:
        assert ftp.newest("SanMarPDD/SanMarPI", "Brand_OGIO_*.csv") == "Brand_OGIO_01-02-2026.csv"
        with pytest.raises(NotFoundError, match="Brand_Nope"):
            ftp.newest("SanMarPDD/SanMarPI", "Brand_Nope_*.csv")


def test_catalog_streams_from_the_server(sftp_server: SFTPServer, tmp_path: Path) -> None:
    """The product files are parsed straight off the server."""
    _publish(sftp_server, "SanMar_SDL_N.csv", "SanMar_EPDD.csv", "sanmar_dip.txt")
    with _connect(sftp_server, tmp_path) as ftp:
        with ftp.catalog() as products:
            assert [product.unique_key for product in products] == ["208284", "105661"]
        with ftp.extended_catalog() as products:
            assert [product.quantity for product in products] == [4500, 0]
        with ftp.warehouse_inventory() as rows:
            assert [row.quantity for row in rows] == [1500, 22, 0]


def test_product_information_files(sftp_server: SFTPServer, tmp_path: Path) -> None:
    """Files the product information service writes are read from SanMarPI."""
    target = _publish(sftp_server, folder="SanMarPDD/SanMarPI")
    (target / "SanMarPI-Delta-123456.csv").write_text(
        "UNIQUE_KEY,STYLE#,SIZE,INVENTORY_KEY,SIZE_INDEX,CATALOG_COLOR\n118032,PC61,S,11803,2,White\n",
        encoding="utf-8",
    )
    with _connect(sftp_server, tmp_path) as ftp, ftp.product_information("SanMarPI-Delta-123456.csv") as rows:
        assert [row.unique_key for row in rows] == ["118032"]


def test_any_file_streams_through_any_reader(sftp_server: SFTPServer, tmp_path: Path) -> None:
    """Files without a shortcut are read by path, with the matching reader."""
    _publish(sftp_server, "sanmar_dpc.csv", folder="Outbound")
    with _connect(sftp_server, tmp_path) as ftp, ftp.stream("outbound/SANMAR_DPC.csv", read_price_changes) as changes:
        assert [change.unique_key for change in changes] == ["208284", "105661"]


def test_zip_members_stream_without_a_download(sftp_server: SFTPServer, tmp_path: Path) -> None:
    """A zipped file is read from inside the archive, by name or as its only text file."""
    target = _publish(sftp_server)
    with zipfile.ZipFile(target / "SanMar_SDL_N.zip", "w") as archive:
        archive.write(FILES / "SanMar_SDL_N.csv", "SanMar_SDL_N.csv")
    with zipfile.ZipFile(target / "SanMar_SDL_DI.zip", "w") as archive:
        archive.write(FILES / "SanMar_SDL_N.csv", "SanMar_SDL_DI.csv")
        archive.write(FILES / "sanmar_dpc.csv", "notes.txt")

    with _connect(sftp_server, tmp_path) as ftp:
        with ftp.open_text("SanMarPDD/SanMar_SDL_N.zip") as text:
            assert text.readline().startswith('"UNIQUE_KEY"')
        with ftp.open_text("SanMarPDD/SanMar_SDL_DI.zip", member="SanMar_SDL_DI.csv") as text:
            assert text.readline().startswith('"UNIQUE_KEY"')
        with pytest.raises(NotFoundError, match="holds 2 text files"), ftp.open_text("SanMarPDD/SanMar_SDL_DI.zip"):
            pass


def test_download(sftp_server: SFTPServer, tmp_path: Path) -> None:
    """A file can be copied down whole, into a folder or to a path."""
    _publish(sftp_server, "sanmar_dpc.csv")
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    with _connect(sftp_server, tmp_path) as ftp:
        into_folder = ftp.download("SanMarPDD/sanmar_dpc.csv", downloads)
        to_path = ftp.download("SanMarPDD/sanmar_dpc.csv", downloads / "prices.csv")
    assert into_folder == downloads / "sanmar_dpc.csv"
    assert into_folder.read_bytes() == to_path.read_bytes() == (FILES / "sanmar_dpc.csv").read_bytes()


def test_orders_upload_then_release(sftp_server: SFTPServer, tmp_path: Path) -> None:
    """A batch's order files go to In, and its release file to Release."""
    for folder in ("In", "Release"):
        (sftp_server.root / folder).mkdir()
    order = PurchaseOrder(
        po_number="FX34689",
        ship_to=ShipTo(address1="123 MAIN ST", city="CHARLOTTE", state="NC", zip_code="28217", email="a@b.co"),
        ship_method=ShipMethod.UPS_GROUND,
        lines=[OrderLine(item=SkuKey(inventory_key=1003, size_index=3), quantity=10)],
    )

    with _connect(sftp_server, tmp_path) as ftp:
        files = ftp.upload_orders("06-07-2022-1", [order])
        release = ftp.release_orders("06-07-2022-1", ["FX34689"], delay=0)

    assert sorted(path.name for path in (sftp_server.root / "In").iterdir()) == [
        "06-07-2022-1CustInfo.txt",
        "06-07-2022-1Details.txt",
    ]
    assert (sftp_server.root / "In" / "06-07-2022-1Details.txt").read_bytes() == files.details.encode()
    assert release == "06-07-2022-1Release1.txt"
    assert (sftp_server.root / "Release" / release).read_bytes() == b"FX34689\r\n"


def test_holding_is_found_in_holding_then_done(sftp_server: SFTPServer, tmp_path: Path) -> None:
    """The acknowledgement is read from Holding, or from Done once processed."""
    _publish(sftp_server, "06-07-2022-1Holding.txt", folder="Done")
    with _connect(sftp_server, tmp_path) as ftp:
        with ftp.holding("06-07-2022-1") as lines:
            assert [line.available for line in lines] == [True, False]
        with pytest.raises(NotFoundError, match="No Holding file for batch 06-07-2022-2"), ftp.holding("06-07-2022-2"):
            pass


@pytest.mark.parametrize(
    "line",
    [
        "ecdsa-sha2-nistp256 {key}",
        "[ftp.sanmar.com]:2200 ecdsa-sha2-nistp256 {key}",
    ],
    ids=["key-only", "known-hosts-line"],
)
def test_host_keys_parse_as_ssh_keyscan_prints_them(sftp_server: SFTPServer, line: str) -> None:
    """A pinned key is accepted with or without the host in front."""
    key = _parse_host_key(line.format(key=sftp_server.host_key.get_base64()))
    assert key == sftp_server.host_key


def test_malformed_host_key_is_refused() -> None:
    """Anything that is not a key type and key is rejected up front."""
    with pytest.raises(ValueError, match="Expected a host key"):
        _parse_host_key("AAAAE2VjZHNh")
