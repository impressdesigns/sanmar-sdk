"""Testing WSDL snapshots: recording, saving, loading, and replaying."""

from pathlib import Path

import pytest
from zeep import Client

from sanmar_sdk._snapshots import RecordingTransport, ReplayTransport, WsdlSnapshot, document_key

ECHO_WSDL = Path(__file__).parent / "fixtures" / "echo.wsdl"


def test_documents_are_keyed_without_the_host() -> None:
    """A document's key is its path and query, so it serves any environment."""
    assert document_key("https://ws.sanmar.com:8080/promostandards/POServiceBinding?WSDL") == (
        "/promostandards/POServiceBinding?WSDL"
    )
    assert document_key("http://internal:9999/schemas/shared.xsd") == "/schemas/shared.xsd"


def test_recording_keeps_every_loaded_document() -> None:
    """Loading a WSDL through the recording transport records it."""
    transport = RecordingTransport()
    Client(ECHO_WSDL.as_uri(), transport=transport)
    assert transport.snapshot.documents == {ECHO_WSDL.as_posix(): ECHO_WSDL.read_bytes()}


def test_snapshots_round_trip(tmp_path: Path) -> None:
    """A saved snapshot loads back identically, with metadata in its index."""
    snapshot = WsdlSnapshot({"/a?wsdl": b"<a/>", "/a?xsd=1": b"<b/>", "/a/xsd/1": b"<c/>"})
    snapshot.save(tmp_path, environment="PRODUCTION")

    assert WsdlSnapshot.load(tmp_path) == snapshot
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "a_wsdl.xml",
        "a_xsd_1.xml",
        "a_xsd_1_2.xml",
        "index.json",
    ]
    assert '"environment": "PRODUCTION"' in (tmp_path / "index.json").read_text()


def test_replay_refuses_unrecorded_documents_and_unqueued_calls() -> None:
    """Replaying never falls back to the network."""
    transport = ReplayTransport(WsdlSnapshot())
    with pytest.raises(LookupError, match=r"re-run scripts/snapshot_wsdls\.py"):
        transport.load("https://ws.sanmar.com:8080/missing?wsdl")

    client = Client(ECHO_WSDL.as_uri())
    envelope = client.create_message(client.service, "getThing", id="user", password="secret")  # noqa: S106
    with pytest.raises(LookupError, match="No response queued"):
        transport.post_xml("https://ws.sanmar.com:8080/echo", envelope, {})
