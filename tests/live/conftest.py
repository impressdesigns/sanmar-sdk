"""Live tests call SanMar's real services, so they run only when asked to.

Set ``SANMAR_LIVE=1`` to run them, from a network that can reach port 8080:

    SANMAR_LIVE=1 uv run pytest tests/live

Tests that need more than network access skip unless their variables are set too:

- ``SANMAR_ENVIRONMENT``: ``production`` (the default) or ``edev``.
- ``SANMAR_CUSTOMER_NUMBER``, ``SANMAR_USERNAME``, ``SANMAR_PASSWORD``: a SanMar.com login
  with web service access, for the environment above.

Live tests only read. Nothing here places an order, and nothing calls the services that
change SanMar-side state (the bulk and delta product files, or incremental invoices).
"""

import os
from pathlib import Path

import pytest

from sanmar_sdk import Environment
from sanmar_sdk._snapshots import WsdlSnapshot

LIVE = Path(__file__).parent
SNAPSHOT = LIVE.parent / "wsdl"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:  # noqa: ARG001 - pytest's hook signature
    """Mark every live test, and skip them all unless SANMAR_LIVE=1."""
    skip = pytest.mark.skip(reason="set SANMAR_LIVE=1 to call SanMar's real services")
    for item in items:
        if LIVE in item.path.parents:
            item.add_marker(pytest.mark.live)
            if os.environ.get("SANMAR_LIVE") != "1":
                item.add_marker(skip)


@pytest.fixture(scope="session")
def environment() -> Environment:
    """Return the environment SANMAR_ENVIRONMENT names, production by default."""
    return Environment[os.environ.get("SANMAR_ENVIRONMENT", "production").upper()]


@pytest.fixture(scope="session")
def snapshot() -> WsdlSnapshot:
    """Load the committed WSDL snapshot, skipping the test when there is none yet."""
    if not (SNAPSHOT / "index.json").exists():
        pytest.skip("no WSDL snapshot yet; run scripts/snapshot_wsdls.py")
    return WsdlSnapshot.load(SNAPSHOT)
