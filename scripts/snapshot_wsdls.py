"""Record SanMar's WSDLs, so the SDK's tests can run through zeep without SanMar.

SanMar's web services listen on port 8080, which CI and some sandboxes cannot reach. Run
this from a machine that can, then commit what it writes:

    uv run python scripts/snapshot_wsdls.py

It loads every web service in SanMar's integration guides, records each WSDL and schema
document zeep fetches into ``tests/wsdl/``, and writes a readable dump of each service's
operations and types to ``tests/wsdl/operations/``. SanMar serves its WSDLs without
authentication, so no credentials are needed.

With ``--ftp`` it also records the layout of the files on SanMar's SFTP server, into
``tests/fixtures/ftp_layout.json``: the top-level folder names, the files in the product
folders, and the header line of each product file. It records no data rows, and replaces
the customer number wherever it appears in a name. It needs ``SANMAR_CUSTOMER_NUMBER``,
``SANMAR_FTP_PASSWORD`` and, unless the host key is in known_hosts,
``SANMAR_SFTP_HOST_KEY`` (as ``ssh-keyscan -p 2200 ftp.sanmar.com`` prints it).
"""

import argparse
import contextlib
import io
import json
import os
import re
import stat
import sys
from datetime import UTC, datetime
from pathlib import Path

from zeep import Client

from sanmar_sdk._snapshots import RecordingTransport
from sanmar_sdk._soap import ENDPOINTS
from sanmar_sdk.common import Environment
from sanmar_sdk.ftp import SanMarFTP
from sanmar_sdk.ftp.client import PRODUCT_FOLDER, PRODUCT_INFORMATION_FOLDER

ROOT = Path(__file__).resolve().parent.parent


def _looks_like_header(line: str) -> bool:
    """Tell a header line from a data row, so no data row is ever recorded."""
    fields = [field.strip().strip('"') for field in re.split(r"[,|\t]", line)]
    return not any(re.fullmatch(r"[\d.$/: -]+", field) for field in fields if field)


def record_ftp_layout(output: Path) -> None:
    """Record folder names, product file names and product file headers from the SFTP server."""
    customer_number = os.environ["SANMAR_CUSTOMER_NUMBER"]

    def redact(text: str) -> str:
        # SanMarPI is shared by every customer, and its bulk and delta files are named for
        # the customer who asked for them; no customer's number belongs in the snapshot.
        text = re.sub(r"(SanMarPI-(?:Bulk|Delta)-)\d+", r"\g<1>{customer_number}", text, flags=re.IGNORECASE)
        return text.replace(customer_number, "{customer_number}")

    layout: dict[str, object] = {}
    with SanMarFTP(
        customer_number,
        os.environ["SANMAR_FTP_PASSWORD"],
        host_key=os.environ.get("SANMAR_SFTP_HOST_KEY"),
    ) as ftp:
        layout["folders"] = [
            redact(name) for name in ftp.list_folder() if stat.S_ISDIR(ftp.sftp.stat(name).st_mode or 0)
        ]
        headers: dict[str, str] = {}
        files: dict[str, list[str]] = {}
        # Redacting can give several files the same name; keep one of each.
        for folder in (PRODUCT_FOLDER, PRODUCT_INFORMATION_FOLDER):
            try:
                names = ftp.list_folder(folder)
            except Exception as exc:  # noqa: BLE001 - record what is missing, keep going
                files[folder] = [f"<{type(exc).__name__}: {exc}>"]
                continue
            files[folder] = list(dict.fromkeys(redact(name) for name in names))
            for name in names:
                if not name.casefold().endswith((".csv", ".txt")):
                    continue
                with ftp.open(f"{folder}/{name}", prefetch=False) as remote:
                    first = io.TextIOWrapper(remote, encoding="utf-8-sig", errors="replace").readline().rstrip("\r\n")
                headers.setdefault(
                    redact(f"{folder}/{name}"), first if _looks_like_header(first) else "<no header row>"
                )
        layout["files"] = files
        layout["headers"] = headers
    output.write_text(json.dumps(layout, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Recorded the SFTP layout to {output}")


def record_wsdls(environment: Environment, output: Path) -> list[str]:
    """Record every endpoint's WSDL and schema documents; return the URLs that failed."""
    transport = RecordingTransport(timeout=60)
    dumps: dict[str, str] = {}
    failures: list[str] = []
    for endpoint in ENDPOINTS:
        for path in (endpoint.path, *endpoint.alternate_paths):
            url = f"{environment.value}{path}"
            print(f"Loading {endpoint.name}: {url}")
            try:
                client = Client(url, transport=transport)
            except Exception as exc:  # noqa: BLE001 - report every failure, then keep going
                failures.append(f"{url}: {type(exc).__name__}: {exc}")
                continue
            dump = io.StringIO()
            with contextlib.redirect_stdout(dump):
                client.wsdl.dump()
            dumps[path] = dump.getvalue()

    transport.snapshot.save(
        output,
        environment=environment.name,
        recorded_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    operations = output / "operations"
    operations.mkdir(exist_ok=True)
    for path, dump_text in dumps.items():
        name = re.sub(r"[^A-Za-z0-9]+", "_", path).strip("_")
        (operations / f"{name}.txt").write_text(dump_text, encoding="utf-8")

    print(f"Recorded {len(transport.snapshot.documents)} documents to {output}")
    return failures


def main() -> int:
    """Record every endpoint's documents and report any that failed to load."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument(
        "--environment",
        choices=[environment.name.lower() for environment in Environment],
        default="production",
        help="which SanMar environment to record (default: production)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "tests" / "wsdl",
        help="where to write the snapshot (default: tests/wsdl)",
    )
    parser.add_argument(
        "--ftp",
        action="store_true",
        help="also record the SFTP server's folders and product file headers (needs SANMAR_* variables)",
    )
    parser.add_argument(
        "--skip-wsdls",
        action="store_true",
        help="record only what --ftp records, leaving the WSDL snapshot as it is",
    )
    arguments = parser.parse_args()
    environment = Environment[arguments.environment.upper()]
    output: Path = arguments.output

    failures = [] if arguments.skip_wsdls else record_wsdls(environment, output)
    if arguments.ftp:
        record_ftp_layout(ROOT / "tests" / "fixtures" / "ftp_layout.json")
    if failures:
        print("These could not be loaded:", *failures, sep="\n  ", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
