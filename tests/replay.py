"""Calling the SDK against SanMar's recorded WSDLs, with canned responses."""

from pathlib import Path
from typing import Any

from zeep.loader import parse_xml

from sanmar_sdk import Environment, SanMar
from sanmar_sdk._snapshots import ReplayTransport, WsdlSnapshot
from sanmar_sdk._soap import _element_data

SNAPSHOT = WsdlSnapshot.load(Path(__file__).parent / "wsdl")
CUSTOMER_NUMBER = 123456
USERNAME = "sanmar-user"
PASSWORD = "sanmar-password"  # noqa: S105 - a placeholder login


def replay_client(environment: Environment = Environment.PRODUCTION) -> tuple[SanMar, ReplayTransport]:
    """Build a client that loads SanMar's recorded WSDLs and answers from a queue."""
    transport = ReplayTransport(SNAPSHOT)
    return SanMar(CUSTOMER_NUMBER, USERNAME, PASSWORD, environment=environment, transport=transport), transport


def envelope(body: str) -> str:
    """Wrap a response body in a SOAP envelope."""
    return (
        '<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xs="http://www.w3.org/2001/XMLSchema">'
        f"<S:Body>{body}</S:Body></S:Envelope>"
    )


def fault(message: str) -> str:
    """Build a SOAP fault response."""
    return envelope(f"<S:Fault><faultcode>S:Server</faultcode><faultstring>{message}</faultstring></S:Fault>")


def sent(transport: ReplayTransport, index: int = -1) -> tuple[str, Any]:
    """Return the operation name and contents of a request the client sent, as plain data."""
    # zeep annotates its parser as taking text, but it reads bytes, which keep the encoding declaration valid.
    document = parse_xml(transport.sent[index][1], transport)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
    body = document.find("{http://schemas.xmlsoap.org/soap/envelope/}Body")
    operation = body[0]
    return operation.tag.rpartition("}")[2], _element_data(operation)
