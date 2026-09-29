"""Testing the SOAP plumbing against a small WSDL shaped like SanMar's."""

from pathlib import Path

import pytest
import requests

from sanmar_sdk import Environment, ResponseError, SanMarConnectionError, SoapFaultError
from sanmar_sdk._snapshots import ReplayTransport, WsdlSnapshot
from sanmar_sdk._soap import ENDPOINTS, Endpoint, SoapClient, resolve_operation

ECHO = Endpoint("Echo", "/echo/EchoService?wsdl")
ECHO_WSDL = (Path(__file__).parent / "fixtures" / "echo.wsdl").read_bytes()

ENVELOPE = """<?xml version="1.0" encoding="utf-8"?>
<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">
  <S:Body>{}</S:Body>
</S:Envelope>"""

THING = ENVELOPE.format(
    """<GetThingResponse xmlns="http://example.com/echo/">
      <productId>K500</productId>
      <PartArray>
        <Part><partId>208284</partId><quantity>12</quantity></Part>
        <Part><partId>208285</partId></Part>
      </PartArray>
    </GetThingResponse>""",
)


class CountingReplayTransport(ReplayTransport):
    """A replay transport that counts document loads."""

    def __init__(self, snapshot: WsdlSnapshot) -> None:
        """Serve ``snapshot`` and start counting."""
        super().__init__(snapshot)
        self.loads: list[str] = []

    def load(self, url: str) -> bytes:
        """Count, then serve."""
        self.loads.append(url)
        return super().load(url)


def _client(environment: Environment = Environment.PRODUCTION) -> tuple[SoapClient, CountingReplayTransport]:
    """Build a client that serves the echo WSDL."""
    transport = CountingReplayTransport(WsdlSnapshot({ECHO.path: ECHO_WSDL}))
    return SoapClient(environment, timeout=5, transport=transport), transport


def test_every_guide_service_has_one_endpoint() -> None:
    """The registry covers the 14 services in the Web Services and Purchase Order guides."""
    expected_endpoints = 14
    paths = [endpoint.path for endpoint in ENDPOINTS]
    assert len(ENDPOINTS) == expected_endpoints
    assert len(set(paths)) == expected_endpoints
    assert all(path.startswith(("/SanMarWebService/", "/promostandards/")) for path in paths)


@pytest.mark.parametrize(
    ("environment", "host"),
    [(Environment.PRODUCTION, "ws.sanmar.com:8080"), (Environment.EDEV, "edev-ws.sanmar.com:8080")],
)
def test_wsdl_urls_point_at_the_environment(environment: Environment, host: str) -> None:
    """A WSDL URL is the endpoint's path on the environment's host."""
    assert ECHO.wsdl_url(environment) == f"https://{host}/echo/EchoService?wsdl"


def test_wsdl_is_loaded_once_on_first_use() -> None:
    """Nothing is loaded until a call needs the service, and then only once."""
    client, transport = _client()
    assert transport.loads == []

    transport.queue(THING)
    transport.queue(THING)
    client.call(ECHO, ("getThing",), {"id": "user", "password": "secret"})
    client.call(ECHO, ("getThing",), {"id": "user", "password": "secret"})

    assert transport.loads == ["https://ws.sanmar.com:8080/echo/EchoService?wsdl"]


@pytest.mark.parametrize(
    ("environment", "address"),
    [
        (Environment.PRODUCTION, "https://ws.sanmar.com:8080/echo/EchoService"),
        (Environment.EDEV, "https://edev-ws.sanmar.com:8080/echo/EchoService"),
    ],
)
def test_calls_go_to_the_environment_not_the_wsdl_address(environment: Environment, address: str) -> None:
    """The address SanMar wrote into the WSDL is replaced with the environment's host."""
    client, transport = _client(environment)
    transport.queue(THING)

    client.call(ECHO, ("getThing",), {"id": "user", "password": "secret"})

    assert [sent_address for sent_address, _ in transport.sent] == [address]


def test_payload_is_sent_as_the_wsdl_describes() -> None:
    """The payload's keys become the request element's children, in schema order."""
    client, transport = _client()
    transport.queue(THING)

    client.call(ECHO, ("getThing",), {"productId": "K500", "password": "secret", "id": "user"})

    body = transport.sent[0][1].decode()
    assert body.index("<ns0:id>user</ns0:id>") < body.index("<ns0:password>secret</ns0:password>")
    assert body.index("<ns0:password>") < body.index("<ns0:productId>K500</ns0:productId>")


def test_response_is_plain_data() -> None:
    """Responses come back as dicts and lists, with absent elements as None."""
    client, transport = _client()
    transport.queue(THING)

    result = client.call(ECHO, ("getThing",), {"id": "user", "password": "secret"})

    assert result == {
        "productId": "K500",
        "note": None,
        "PartArray": {
            "Part": [
                {"partId": "208284", "quantity": 12},
                {"partId": "208285", "quantity": None},
            ],
        },
    }


@pytest.mark.parametrize(
    "candidates",
    [("getThing",), ("GetThing",), ("GetThings", "getthing")],
    ids=["exact", "case-insensitive", "later-candidate"],
)
def test_operations_resolve_by_candidate_names(candidates: tuple[str, ...]) -> None:
    """An operation is found by any of its names, exactly or ignoring case."""
    client, _ = _client()
    operation = resolve_operation(client.service(ECHO), candidates)
    assert operation._op_name == "getThing"  # noqa: SLF001 - zeep has no public name accessor


def test_unknown_operation_lists_what_the_wsdl_has() -> None:
    """A name the WSDL does not define fails with the names it does."""
    client, _ = _client()
    with pytest.raises(ResponseError, match=r"no operation named getOther or GetOther; it has getThing"):
        resolve_operation(client.service(ECHO), ("getOther", "GetOther"))


def test_soap_fault_is_raised_as_sdk_error() -> None:
    """A SOAP fault becomes a SoapFaultError carrying SanMar's fault string."""
    client, transport = _client()
    transport.queue(
        ENVELOPE.format(
            "<S:Fault><faultcode>S:Server</faultcode><faultstring>Invalid request</faultstring></S:Fault>",
        ),
        status=500,
    )

    with pytest.raises(SoapFaultError, match="Invalid request") as caught:
        client.call(ECHO, ("getThing",), {"id": "user", "password": "secret"})
    assert caught.value.code == "S:Server"


def test_http_error_is_raised_as_connection_error() -> None:
    """A non-SOAP HTTP error becomes a SanMarConnectionError."""
    client, transport = _client()
    transport.queue("Service Unavailable", status=503)

    with pytest.raises(SanMarConnectionError, match="HTTP 503"):
        client.call(ECHO, ("getThing",), {"id": "user", "password": "secret"})


def test_unreachable_host_is_raised_as_connection_error() -> None:
    """A network failure while loading a WSDL becomes a SanMarConnectionError."""

    class UnreachableTransport(ReplayTransport):
        def load(self, url: str) -> bytes:
            message = f"Connection refused: {url}"
            raise requests.ConnectionError(message)

    client = SoapClient(Environment.PRODUCTION, timeout=5, transport=UnreachableTransport(WsdlSnapshot()))

    with pytest.raises(SanMarConnectionError, match="Connection refused"):
        client.call(ECHO, ("getThing",), {"id": "user", "password": "secret"})


def test_invalid_xml_is_raised_as_response_error() -> None:
    """A successful response that is not XML becomes a ResponseError."""
    client, transport = _client()
    transport.queue(ENVELOPE.format('<GetThingResponse xmlns="http://example.com/echo/"><productId>'))

    with pytest.raises(ResponseError, match="not valid XML"):
        client.call(ECHO, ("getThing",), {"id": "user", "password": "secret"})


def test_response_out_of_schema_order_is_raised_as_response_error() -> None:
    """An element out of schema order fails loudly instead of dropping the fields after it."""
    client, transport = _client()
    transport.queue(
        ENVELOPE.format(
            """<GetThingResponse xmlns="http://example.com/echo/">
              <note>first</note><productId>K500</productId>
            </GetThingResponse>""",
        ),
    )

    with pytest.raises(ResponseError, match="Unexpected element"):
        client.call(ECHO, ("getThing",), {"id": "user", "password": "secret"})
