"""Record SanMar's WSDLs, so the SDK's tests can run through zeep without SanMar.

SanMar's web services listen on port 8080, which CI and some sandboxes cannot reach. Run
this from a machine that can, then commit what it writes:

    uv run python scripts/snapshot_wsdls.py

It loads every web service in SanMar's integration guides, records each WSDL and schema
document zeep fetches into ``tests/wsdl/``, and writes a readable dump of each service's
operations and types to ``tests/wsdl/operations/``. SanMar serves its WSDLs without
authentication, so no credentials are needed.
"""

import argparse
import contextlib
import io
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from zeep import Client

from sanmar_sdk._snapshots import RecordingTransport
from sanmar_sdk._soap import ENDPOINTS, Environment

ROOT = Path(__file__).resolve().parent.parent


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
    arguments = parser.parse_args()
    environment = Environment[arguments.environment.upper()]
    output: Path = arguments.output

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
    if failures:
        print("These could not be loaded:", *failures, sep="\n  ", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
