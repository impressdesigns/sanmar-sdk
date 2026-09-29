"""Checking the recorded WSDLs cover every service the SDK calls."""

import pytest
from zeep import Client

from sanmar_sdk import Environment
from sanmar_sdk._snapshots import ReplayTransport
from sanmar_sdk._soap import ENDPOINTS, Endpoint

from .replay import SNAPSHOT


@pytest.mark.parametrize("endpoint", ENDPOINTS, ids=lambda endpoint: endpoint.name)
def test_every_endpoint_is_recorded(endpoint: Endpoint) -> None:
    """Every service's WSDL, and everything it imports, loads from the snapshot."""
    for path in (endpoint.path, *endpoint.alternate_paths):
        client = Client(f"{Environment.PRODUCTION.value}{path}", transport=ReplayTransport(SNAPSHOT))
        assert dict(iter(client.service))
