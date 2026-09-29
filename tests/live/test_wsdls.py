"""Checking that SanMar still serves the WSDLs the SDK was built against."""

from typing import TYPE_CHECKING

import pytest
from zeep import Client

from sanmar_sdk._snapshots import ReplayTransport
from sanmar_sdk._soap import ENDPOINTS, Endpoint

if TYPE_CHECKING:
    from sanmar_sdk import Environment
    from sanmar_sdk._snapshots import WsdlSnapshot


def _operations(client: Client) -> dict[str, str]:
    """Every operation in a WSDL, with its input signature."""
    return {name: str(operation._proxy._binding.get(name).input.signature()) for name, operation in client.service}  # noqa: SLF001 - zeep exposes signatures only here


@pytest.mark.parametrize("endpoint", ENDPOINTS, ids=lambda endpoint: endpoint.name)
def test_wsdl_loads(endpoint: Endpoint, environment: Environment) -> None:
    """Every service's WSDL loads and defines at least one operation."""
    client = Client(endpoint.wsdl_url(environment))
    assert _operations(client)


@pytest.mark.parametrize("endpoint", ENDPOINTS, ids=lambda endpoint: endpoint.name)
def test_snapshot_matches_sanmar(endpoint: Endpoint, environment: Environment, snapshot: WsdlSnapshot) -> None:
    """The committed snapshot defines the same operations, with the same inputs, as SanMar.

    A failure means SanMar changed a service: re-run scripts/snapshot_wsdls.py and check
    what the SDK needs to change with it.
    """
    live = Client(endpoint.wsdl_url(environment))
    recorded = Client(endpoint.wsdl_url(environment), transport=ReplayTransport(snapshot))
    assert _operations(recorded) == _operations(live)
